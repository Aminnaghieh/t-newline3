import { NextRequest } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import { mkdtemp, writeFile, rm } from "fs/promises";
import { tmpdir } from "os";
import path from "path";
import { recommendPlan } from "@/lib/liara/planner";
import { writeAudit } from "@/lib/liara/store";
import type { AnalysisResult } from "@/lib/liara/types";

export const runtime = "nodejs";
export const maxDuration = 60;

const exec = promisify(execFile);

// ─── Sample apps (شبیه‌ساز سورس‌های رایج) ─────────────────────
const SAMPLES: Record<
  string,
  { label: string; analysis: AnalysisResult }
> = {
  "next-shop": {
    label: "فروشگاه Next.js",
    analysis: {
      platform: "nodejs",
      framework: "next",
      port: 3000,
      startCmd: "npm start",
      buildCmd: "npm run build",
      dependencies: Array.from({ length: 46 }, (_, i) => `pkg-${i}`),
      envVarsNeeded: ["DATABASE_URL", "NEXT_PUBLIC_API_URL"],
      hasDockerfile: false,
      projectSizeMb: 84.2,
      notes: [],
    },
  },
  "fastapi-orders": {
    label: "سرویس FastAPI",
    analysis: {
      platform: "python",
      framework: "fastapi",
      port: 8000,
      startCmd: "uvicorn main:app --host 0.0.0.0 --port 8000",
      buildCmd: null,
      dependencies: Array.from({ length: 22 }, (_, i) => `py-pkg-${i}`),
      envVarsNeeded: ["DATABASE_URL", "REDIS_URL"],
      hasDockerfile: false,
      projectSizeMb: 12.6,
      notes: [],
    },
  },
  "laravel-blog": {
    label: "وبلاگ Laravel",
    analysis: {
      platform: "php",
      framework: "laravel",
      port: 80,
      startCmd: "php artisan serve --host 0.0.0.0 --port 80",
      buildCmd: "composer install --no-dev",
      dependencies: Array.from({ length: 38 }, (_, i) => `composer-${i}`),
      envVarsNeeded: ["APP_KEY", "DB_HOST", "DB_DATABASE"],
      hasDockerfile: false,
      projectSizeMb: 26.4,
      notes: [],
    },
  },
};

const PLATFORM_FROM_FILES: { files: string[]; platform: string }[] = [
  { files: ["package.json"], platform: "nodejs" },
  { files: ["requirements.txt", "pyproject.toml", "Pipfile"], platform: "python" },
  { files: ["go.mod"], platform: "go" },
  { files: ["composer.json", "artisan", "index.php"], platform: "php" },
  { files: ["Gemfile"], platform: "ruby" },
  { files: ["pom.xml", "build.gradle"], platform: "java" },
  { files: ["Cargo.toml"], platform: "rust" },
  { files: ["Dockerfile"], platform: "docker" },
  { files: ["index.html"], platform: "static" },
];

function detectFramework(files: string[], platform: string): string | null {
  const has = (f: string) => files.some((x) => x === f || x.endsWith("/" + f));
  if (platform === "nodejs") {
    if (has("next.config.js") || has("next.config.mjs") || has("next.config.ts")) return "next";
    if (has("nuxt.config.ts") || has("nuxt.config.js")) return "nuxt";
    if (has("nest-cli.json")) return "nest";
    return "node";
  }
  if (platform === "python") {
    if (has("manage.py")) return "django";
    return "python";
  }
  if (platform === "php" && has("artisan")) return "laravel";
  return null;
}

export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") ?? "";
    let analysis: AnalysisResult | null = null;
    let sourceLabel = "";
    let sampleKey: string | null = null;

    if (contentType.includes("multipart/form-data")) {
      const form = await req.formData();
      const file = form.get("file") as File | null;
      if (!file) return Response.json({ error: "فایلی ارسال نشده" }, { status: 400 });
      const buf = Buffer.from(await file.arrayBuffer());
      if (buf.length > 60 * 1024 * 1024) {
        return Response.json({ error: "حجم فایل بیش از ۶۰MB است" }, { status: 400 });
      }

      // Real analyzer: list archive contents via system tar
      const dir = await mkdtemp(path.join(tmpdir(), "liara-an-"));
      const fp = path.join(dir, "app.tar.gz");
      await writeFile(fp, buf);
      try {
        const { stdout } = await exec("tar", ["-tzf", fp], { timeout: 15000 });
        const files = stdout
          .split("\n")
          .map((s) => s.trim().replace(/^\.?\//, ""))
          .filter(Boolean)
          .slice(0, 3000);

        // platform detection
        let platform = "docker";
        for (const rule of PLATFORM_FROM_FILES) {
          if (rule.files.some((f) => files.some((x) => x === f || x.endsWith("/" + f)))) {
            platform = rule.platform;
            break;
          }
        }
        const framework = detectFramework(files, platform);
        const depCount =
          platform === "nodejs"
            ? Math.max(8, files.filter((f) => f.includes("node_modules")).length % 80)
            : platform === "python"
              ? Math.max(6, files.filter((f) => f.includes(".dist-info")).length)
              : platform === "php"
                ? Math.max(10, files.filter((f) => f.startsWith("vendor/")).length % 60)
                : 10;
        const sizeMb = Number((buf.length / 1024 / 1024).toFixed(1));
        const port = platform === "python" ? 8000 : platform === "php" ? 80 : 3000;

        analysis = {
          platform,
          framework,
          port,
          startCmd:
            platform === "python"
              ? "uvicorn main:app --host 0.0.0.0 --port 8000"
              : platform === "php"
                ? "php artisan serve --host 0.0.0.0 --port 80"
                : "npm start",
          buildCmd: platform === "nodejs" ? "npm run build" : null,
          dependencies: Array.from({ length: depCount }, (_, i) => `dep-${i}`),
          envVarsNeeded: [],
          hasDockerfile: files.some((f) => f === "Dockerfile" || f.endsWith("/Dockerfile")),
          projectSizeMb: sizeMb,
          notes: [],
        };
        analysis.notes.push(`${files.length} فایل در آرشیو شناسایی شد`);
        if (analysis.hasDockerfile) {
          analysis.notes.push("Dockerfile پیدا شد — استقرار با پلتفرم docker انجام می‌شود");
        }
        // env var heuristics from common filenames
        if (files.some((f) => f.endsWith(".env.example"))) {
          analysis.envVarsNeeded.push("متغیرهای .env.example را در پنل تنظیم کنید");
        }
      } catch {
        return Response.json(
          { error: "آرشیو معتبر tar.gz نیست یا قابل خواندن نیست" },
          { status: 400 }
        );
      } finally {
        await rm(dir, { recursive: true, force: true }).catch(() => {});
      }
      sourceLabel = file.name;
    } else {
      const body = (await req.json()) as { sampleApp?: string };
      sampleKey = body.sampleApp ?? "next-shop";
      const s = SAMPLES[sampleKey];
      if (!s) return Response.json({ error: "نمونه پیدا نشد" }, { status: 400 });
      analysis = { ...s.analysis, notes: [] };
      sourceLabel = s.label;
    }

    const recommendation = recommendPlan(analysis);
    analysis.notes.unshift(
      `پلتفرم «${analysis.platform}»${analysis.framework ? ` با فریم‌ورک «${analysis.framework}»` : ""} شناسایی شد`
    );
    analysis.notes.push(
      `وب‌سرور باید روی پورت ${analysis.port} و با آدرس 0.0.0.0 گوش دهد`
    );

    await writeAudit({
      action: "analyze_project",
      target: sourceLabel,
      riskLevel: "low",
      status: "success",
      source: "deploy-wizard",
      details: { platform: analysis.platform, framework: analysis.framework },
    });

    return Response.json({ analysis, recommendation, sourceLabel, sampleKey });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "خطا در تحلیل پروژه" },
      { status: 500 }
    );
  }
}

export async function GET() {
  return Response.json({
    samples: Object.entries(SAMPLES).map(([key, s]) => ({ key, label: s.label })),
  });
}
