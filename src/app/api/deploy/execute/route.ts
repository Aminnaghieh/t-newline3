import { NextRequest } from "next/server";
import { isLiveMode } from "@/lib/liara/client";
import { writeAudit } from "@/lib/liara/store";

export const runtime = "nodejs";
export const maxDuration = 60;

// Deploy executor — demo mode simulates the staged pipeline
// (upload → build → release → health-check) of the Python agent's
// deployer. Live mode forwards the archive to the Liara v2 API.
export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get("content-type") ?? "";
    let projectName = "";
    let sourceLabel = "";

    if (contentType.includes("multipart/form-data")) {
      const form = await req.formData();
      projectName = String(form.get("projectName") ?? "my-app");
      const file = form.get("file") as File | null;
      sourceLabel = file?.name ?? "source.tar.gz";

      if (await isLiveMode()) {
        // Forward to Liara API (upload source → create release)
        const { getSettings } = await import("@/lib/liara/store");
        const s = await getSettings();
        const fd = new FormData();
        fd.append("file", file as File, sourceLabel);
        const up = await fetch(
          `https://api.liara.ir/v2/projects/${encodeURIComponent(projectName)}/sources`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${s.liaraToken}` },
            body: fd,
            signal: AbortSignal.timeout(55_000),
          }
        );
        const data = await up.json().catch(() => ({}));
        if (!up.ok) {
          await writeAudit({
            action: "deploy",
            target: projectName,
            riskLevel: "medium",
            status: "failed",
            source: "deploy-wizard",
            details: { message: JSON.stringify(data).slice(0, 300) },
          });
          return Response.json({ ok: false, message: `خطای آپلود: HTTP ${up.status}` });
        }
        const release = await fetch(
          `https://api.liara.ir/v2/projects/${encodeURIComponent(projectName)}/releases`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${s.liaraToken}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              sourceID: (data as { sourceID?: string }).sourceID,
              port: Number(form.get("port") ?? 3000),
              type: String(form.get("platform") ?? "nodejs"),
            }),
          }
        );
        const rel = await release.json().catch(() => ({}));
        await writeAudit({
          action: "deploy",
          target: projectName,
          riskLevel: "medium",
          status: release.ok ? "success" : "failed",
          source: "deploy-wizard",
          details: rel,
        });
        return Response.json({
          ok: release.ok,
          message: release.ok
            ? "ریلیز ثبت شد — وضعیت بیلد را در لاگ‌ها دنبال کنید"
            : "ثبت ریلیز ناموفق بود",
          releaseId: (rel as { releaseID?: string }).releaseID,
        });
      }
    } else {
      const body = (await req.json()) as { projectName?: string; sampleKey?: string };
      projectName = body.projectName ?? "demo-app";
      sourceLabel = body.sampleKey ?? "sample";
    }

    // Demo simulation
    await writeAudit({
      action: "deploy",
      target: projectName,
      riskLevel: "medium",
      status: "success",
      source: "deploy-wizard",
      details: { source: sourceLabel, mode: "demo" },
    });
    return Response.json({
      ok: true,
      demo: true,
      message: `استقرار «${projectName}» در حالت دمو شبیه‌سازی شد — آدرس: https://${projectName}.liara.run`,
      url: `https://${projectName}.liara.run`,
    });
  } catch (e) {
    return Response.json(
      { ok: false, message: e instanceof Error ? e.message : "خطای استقرار" },
      { status: 500 }
    );
  }
}
