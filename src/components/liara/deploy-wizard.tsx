"use client";
import { useRef, useState } from "react";
import type { AnalysisResult, PlanRecommendationResult } from "@/lib/liara/types";
import { SectionCard } from "./dashboard";
import { getAllPlans, planLabel } from "@/lib/liara/plans";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CloudUpload,
  Cpu,
  FileCode2,
  Loader2,
  MemoryStick,
  Rocket,
  Terminal,
} from "lucide-react";

type Step = 1 | 2 | 3;

interface AnalyzeResponse {
  analysis: AnalysisResult;
  recommendation: PlanRecommendationResult;
  sourceLabel: string;
  sampleKey: string | null;
  error?: string;
}

const SAMPLES = [
  { key: "next-shop", label: "فروشگاه Next.js", icon: "🛒" },
  { key: "fastapi-orders", label: "سرویس FastAPI", icon: "⚡" },
  { key: "laravel-blog", label: "وبلاگ Laravel", icon: "📝" },
];

export function DeployWizard() {
  const [step, setStep] = useState<Step>(1);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [pickedPlan, setPickedPlan] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [deployLog, setDeployLog] = useState<string[]>([]);
  const [deployDone, setDeployDone] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const analyzeSample = async (sampleKey: string) => {
    setBusy(true);
    try {
      const res = await fetch("/api/deploy/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sampleApp: sampleKey }),
      });
      const d: AnalyzeResponse = await res.json();
      if (d.analysis) {
        setAnalysis(d);
        setPickedPlan(d.recommendation.recommendedPlan);
        setProjectName(sampleKey.replace("/", "-"));
        setStep(2);
      } else {
        toast({ title: "خطا", description: "تحلیل ناموفق بود", variant: "destructive" });
      }
    } finally {
      setBusy(false);
    }
  };

  const analyzeFile = async (f: File) => {
    if (!f.name.endsWith(".tar.gz") && !f.name.endsWith(".tgz")) {
      toast({
        title: "فرمت نامعتبر",
        description: "فایل سورس باید .tar.gz باشد",
        variant: "destructive",
      });
      return;
    }
    setFile(f);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const res = await fetch("/api/deploy/analyze", { method: "POST", body: fd });
      const d: AnalyzeResponse = await res.json();
      if (d.analysis) {
        setAnalysis(d);
        setPickedPlan(d.recommendation.recommendedPlan);
        setProjectName(f.name.replace(/\.tar\.gz$|\.tgz$/, "").toLowerCase().replace(/[^a-z0-9-]/g, "-"));
        setStep(2);
      } else {
        toast({ title: "خطا", description: d.error ?? "تحلیل ناموفق بود", variant: "destructive" });
      }
    } finally {
      setBusy(false);
    }
  };

  const runDeploy = async () => {
    setBusy(true);
    setDeployLog([]);
    setDeployDone(false);
    setStep(3);
    const lines = [
      `📦 بسته‌بندی سورس (${analysis?.sourceLabel ?? "source"})`,
      "📤 آپلود به /v2/projects/" + projectName + "/sources …",
      "🏗 ساخت ایمیج با پلتفرم " + (analysis?.analysis.platform ?? "nodejs") + " …",
      "🚀 ثبت ریلیز با پورت " + (analysis?.analysis.port ?? 3000) + " …",
      "🩺 بررسی سلامت کانتینر …",
    ];
    for (const l of lines) {
      setDeployLog((cur) => [...cur, l]);
      await new Promise((r) => setTimeout(r, 850));
    }
    try {
      let res: Response;
      if (file) {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("projectName", projectName);
        fd.append("port", String(analysis?.analysis.port ?? 3000));
        fd.append("platform", analysis?.analysis.platform ?? "nodejs");
        res = await fetch("/api/deploy/execute", { method: "POST", body: fd });
      } else {
        res = await fetch("/api/deploy/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ projectName, sampleKey: analysis?.sampleKey }),
        });
      }
      const d = await res.json();
      setDeployLog((cur) => [...cur, d.ok ? `✅ ${d.message}` : `⚠️ ${d.message}`]);
      setDeployDone(d.ok);
      if (d.ok) toast({ title: "استقرار کامل شد 🎉", description: d.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Stepper */}
      <div className="flex items-center justify-center gap-2">
        {(["انتخاب سورس", "تحلیل و پلن", "استقرار"] as const).map((label, i) => {
          const n = (i + 1) as Step;
          return (
            <div key={label} className="flex items-center gap-2">
              <span
                className={cn(
                  "flex size-7 items-center justify-center rounded-full text-[12px] font-black",
                  step >= n ? "liara-gradient text-[#0e1512]" : "bg-white/6 text-muted-foreground"
                )}
              >
                {n}
              </span>
              <span className={cn("text-[12.5px] font-bold", step >= n ? "text-foreground" : "text-muted-foreground")}>
                {label}
              </span>
              {i < 2 && <span className="mx-1 h-px w-8 bg-white/12" />}
            </div>
          );
        })}
      </div>

      {step === 1 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard title="آپلود سورس (.tar.gz)" icon={<CloudUpload className="size-4" />}>
            <p className="mb-4 text-[12.5px] leading-6 text-muted-foreground">
              آرشیو سورس پروژه را بکشید و رها کنید. ایجنت به‌صورت خودکار زبان، فریم‌ورک، پورت و
              وابستگی‌ها را تحلیل می‌کند و بهترین پلن را پیشنهاد می‌دهد.
            </p>
            <button
              onClick={() => fileRef.current?.click()}
              className="flex w-full flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-white/12 bg-white/2 py-10 transition-all hover:border-[#87fcc4]/40 hover:bg-[#87fcc4]/4"
            >
              {busy ? (
                <Loader2 className="size-8 animate-spin text-[#87fcc4]" />
              ) : (
                <CloudUpload className="size-8 text-[#87fcc4]" />
              )}
              <span className="text-[13px] font-bold">
                {file ? file.name : "انتخاب یا رها کردن فایل archive.tar.gz"}
              </span>
              <span className="text-[11px] text-muted-foreground">حداکثر ۶۰ مگابایت — تحلیل واقعی محتویات آرشیو</span>
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".tar.gz,.tgz"
              hidden
              onChange={(e) => e.target.files?.[0] && analyzeFile(e.target.files[0])}
            />
          </SectionCard>

          <SectionCard title="یا یک نمونه آماده را امتحان کن" icon={<Rocket className="size-4" />}>
            <div className="space-y-2.5">
              {SAMPLES.map((s) => (
                <button
                  key={s.key}
                  disabled={busy}
                  onClick={() => analyzeSample(s.key)}
                  className="group flex w-full items-center gap-3 rounded-xl border border-white/8 bg-white/3 p-3.5 text-right transition-all hover:border-[#87fcc4]/35 hover:bg-[#87fcc4]/5 disabled:opacity-50"
                >
                  <span className="text-2xl">{s.icon}</span>
                  <span className="flex-1">
                    <span className="block text-[13px] font-extrabold">{s.label}</span>
                    <span className="block text-[11px] text-muted-foreground">
                      تحلیل خودکار + پیشنهاد پلن + شبیه‌سازی استقرار
                    </span>
                  </span>
                  <ArrowLeft className="size-4 text-muted-foreground transition-transform group-hover:-translate-x-1 group-hover:text-[#87fcc4]" />
                </button>
              ))}
            </div>
          </SectionCard>
        </div>
      )}

      {step === 2 && analysis && (
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard title="نتیجه تحلیل سورس" icon={<FileCode2 className="size-4" />} className="lg:col-span-2">
            <div className="mb-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <InfoTile label="پلتفرم" value={analysis.analysis.platform} />
              <InfoTile label="فریم‌ورک" value={analysis.analysis.framework ?? "—"} />
              <InfoTile label="پورت" value={String(analysis.analysis.port)} />
              <InfoTile label="حجم" value={`${analysis.analysis.projectSizeMb}MB`} />
            </div>
            <div className="mb-4 space-y-2">
              {analysis.analysis.notes.map((n, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg bg-white/3 px-3 py-2 text-[12px] leading-5">
                  <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-[#87fcc4]" />
                  {n}
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-white/8 bg-[#101512] p-3 text-[11.5px]" dir="ltr">
              <div className="mb-1 flex items-center gap-1.5 text-[#93a29a]">
                <Terminal className="size-3.5" /> start command
              </div>
              <code className="text-[#87fcc4]">$ {analysis.analysis.startCmd}</code>
            </div>
          </SectionCard>

          <div className="space-y-4">
            <SectionCard title="پلن پیشنهادی ایجنت" icon={<Cpu className="size-4" />}>
              <div className="rounded-xl border border-[#87fcc4]/35 bg-[#87fcc4]/6 p-3.5">
                <div className="text-lg font-black text-[#87fcc4]">
                  {planLabel(analysis.recommendation.recommendedPlan)}
                </div>
                <p className="mt-1 text-[11.5px] leading-5 text-muted-foreground">
                  {analysis.recommendation.reason}
                </p>
              </div>
              <div className="mt-3 flex items-center gap-3 text-[11.5px] text-muted-foreground latin-digits">
                <span className="flex items-center gap-1">
                  <Cpu className="size-3.5" /> {analysis.recommendation.estimatedRequirements.cpuCores} vCPU
                </span>
                <span className="flex items-center gap-1">
                  <MemoryStick className="size-3.5" /> {analysis.recommendation.estimatedRequirements.ramGb}GB رم
                </span>
              </div>
            </SectionCard>

            <SectionCard title="انتخاب پلن نهایی" icon={<Rocket className="size-4" />}>
              <div className="space-y-1.5">
                {getAllPlans().slice(0, 4).map((p) => (
                  <label
                    key={p.id}
                    className={cn(
                      "flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-[12px] transition-all",
                      pickedPlan === p.id
                        ? "border-[#87fcc4]/40 bg-[#87fcc4]/8 text-[#87fcc4]"
                        : "border-white/8 hover:bg-white/4"
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="plan"
                        checked={pickedPlan === p.id}
                        onChange={() => setPickedPlan(p.id)}
                        className="accent-[#87fcc4]"
                      />
                      {p.label}
                    </span>
                    <span className="text-[10.5px] latin-digits" dir="ltr">
                      {p.cpu}vCPU / {p.ramGb}GB
                    </span>
                  </label>
                ))}
              </div>
              <div className="mt-3.5 space-y-2.5">
                <Input
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value.toLowerCase())}
                  placeholder="نام سرویس (مثلاً my-app)"
                  dir="ltr"
                  className="border-white/10 bg-[#161b18] text-left text-[12.5px] focus-visible:ring-[#87fcc4]/40"
                />
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setStep(1)} className="border-white/12">
                    <ArrowRight className="size-4" /> بازگشت
                  </Button>
                  <Button
                    onClick={runDeploy}
                    disabled={busy || !projectName.trim()}
                    className="liara-gradient flex-1 font-extrabold text-[#0e1512] hover:opacity-90"
                  >
                    <Rocket className="size-4" /> شروع استقرار
                  </Button>
                </div>
              </div>
            </SectionCard>
          </div>
        </div>
      )}

      {step === 3 && (
        <SectionCard title="پایپ‌لاین استقرار" icon={<Rocket className="size-4" />}>
          <div className="terminal min-h-[260px] rounded-xl border border-white/8 p-4">
            {deployLog.map((l, i) => (
              <div key={i} className={cn("py-0.5", l.startsWith("✅") && "text-[#87fcc4]", l.startsWith("⚠️") && "text-[#ff6b6b]")}>
                {l}
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2 py-1 text-[#28c1f5]">
                <Loader2 className="size-3.5 animate-spin" />
                در حال اجرا…
              </div>
            )}
            {deployDone && (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <span className="rounded-lg bg-[#87fcc4]/10 px-3 py-1.5 text-[12.5px] font-bold text-[#87fcc4]" dir="ltr">
                  https://{projectName}.liara.run
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setStep(1);
                    setAnalysis(null);
                    setFile(null);
                    setDeployLog([]);
                    setDeployDone(false);
                  }}
                  className="border-white/12"
                >
                  استقرار جدید
                </Button>
              </div>
            )}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/3 p-3 text-center">
      <div className="mb-1 text-[10.5px] text-muted-foreground">{label}</div>
      <div className="text-[13.5px] font-extrabold" dir="ltr">
        {value}
      </div>
    </div>
  );
}
