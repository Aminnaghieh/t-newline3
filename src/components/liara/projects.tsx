"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { LiaraProject, LogEntry, MetricsReport, MetricType } from "@/lib/liara/types";
import { PlanBadge, StatusBadge } from "./badges";
import { MetricsChart } from "./metrics-chart";
import { SectionCard } from "./dashboard";
import { getAllPlans, planLabel } from "@/lib/liara/plans";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import {
  Activity,
  Globe,
  Info,
  Loader2,
  PauseCircle,
  PlayCircle,
  Power,
  RefreshCw,
  ScrollText,
  Zap,
} from "lucide-react";

interface PendingAction {
  action: string;
  title: string;
  description: string;
  risk: "medium" | "high" | "critical";
  params?: Record<string, string | number | boolean>;
  run: () => Promise<void>;
}

const LOG_COLORS: Record<string, string> = {
  info: "text-[#9fb0a6]",
  debug: "text-[#6d7d74]",
  warn: "text-[#ffc000]",
  error: "text-[#ff6b6b]",
};

export function ProjectsView({ selected }: { selected: string | null }) {
  const { toast } = useToast();
  const [projects, setProjects] = useState<LiaraProject[]>([]);
  const [active, setActive] = useState<string | null>(selected);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busyAction, setBusyAction] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch("/api/projects");
      const d = await res.json();
      setProjects(d.projects ?? []);
      setActive((cur) => cur ?? d.projects?.[0]?.name ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selected) setActive(selected);
  }, [selected]);

  const current = projects.find((p) => p.name === active) ?? null;

  const execute = async (a: PendingAction) => {
    setBusyAction(true);
    try {
      const res = await fetch("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: current?.name,
          action: a.action,
          parameters: a.params ?? {},
          confirmed: true,
        }),
      });
      const d = await res.json();
      toast({ title: d.ok ? "انجام شد" : "ناموفق", description: d.message });
      await loadProjects();
    } finally {
      setBusyAction(false);
      setPending(null);
    }
  };

  const askConfirm = (
    action: string,
    title: string,
    description: string,
    risk: PendingAction["risk"],
    params?: Record<string, string | number | boolean>
  ) => {
    setPending({
      action,
      title,
      description,
      risk,
      params,
      run: async () => undefined,
    });
  };

  if (loading) return <Skeleton className="h-96 rounded-2xl" />;

  if (!projects.length) {
    return (
      <SectionCard title="سرویس‌ها" icon={<Activity className="size-4" />}>
        <div className="py-10 text-center text-muted-foreground">هیچ سرویسی یافت نشد</div>
      </SectionCard>
    );
  }

  return (
    <div className="space-y-4">
      {/* Project selector */}
      <div className="flex flex-wrap gap-2">
        {projects.map((p) => (
          <button
            key={p.name}
            onClick={() => setActive(p.name)}
            className={cn(
              "flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[12.5px] font-bold transition-all",
              active === p.name
                ? "border-[#87fcc4]/40 bg-[#87fcc4]/10 text-[#87fcc4]"
                : "border-white/10 bg-white/3 text-muted-foreground hover:bg-white/6"
            )}
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                p.status === "running" ? "bg-[#87fcc4]" : p.status === "failed" ? "bg-[#ff6b6b]" : "bg-[#9fb0a6]"
              )}
            />
            <span dir="ltr">{p.name}</span>
          </button>
        ))}
      </div>

      {current && (
        <ProjectDetail
          key={current.name}
          project={current}
          onAction={(action, params) => {
            if (action === "restart") {
              askConfirm(
                "restart",
                `ری‌استارت «${current.name}»`,
                "کانتینر ری‌استارت می‌شود؛ حدود چند ثانیه قطعی موقت خدمات خواهیم داشت. این عملیات در گزارش ممیزی ثبت می‌شود.",
                "medium"
              );
            } else if (action === "scale") {
              const on = Number(params?.scale) === 1;
              askConfirm(
                "scale",
                `${on ? "روشن" : "خاموش"} کردن «${current.name}»`,
                on
                  ? "سرویس روشن می‌شود و ترافیک مجدداً سرو خواهد شد."
                  : "⚠️ سرویس کاملاً خاموش می‌شود و اپلیکیشن از دسترس خارج خواهد شد. مطمئن هستید؟",
                "high",
                params
              );
            } else if (action === "resize") {
              const target = String(params?.planID ?? "");
              const plan = getAllPlans().find((p) => p.id === target);
              askConfirm(
                "resize",
                `تغییر پلن «${current.name}» به ${planLabel(target)}`,
                `منابع سرویس به ${plan?.cpu} vCPU و ${plan?.ramGb}GB رم تغییر می‌کند. هزینه ماهانه جدید: ${plan ? plan.priceIRR.toLocaleString("fa-IR") + " ریال" : "—"}`,
                "high",
                params
              );
            }
          }}
          busy={busyAction}
        />
      )}

      {/* Confirmation dialog (HITL) */}
      <Dialog open={!!pending} onOpenChange={(o) => !o && setPending(null)}>
        <DialogContent className="border-white/12 bg-[#202723] sm:max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-[15px]">
              <Power className="size-4 text-[#ffc000]" />
              {pending?.title}
            </DialogTitle>
            <DialogDescription className="pt-1.5 text-[13px] leading-6 text-muted-foreground">
              {pending?.description}
            </DialogDescription>
          </DialogHeader>
          <Alert className="border-[#ffc000]/25 bg-[#ffc000]/6">
            <Info className="size-4 text-[#ffc000]" />
            <AlertTitle className="text-[12.5px] text-[#ffc000]">دروازه تایید انسانی</AlertTitle>
            <AlertDescription className="text-[11.5px] leading-5 text-muted-foreground">
              این عملیات با سطح ریسک{" "}
              <b>{pending?.risk === "medium" ? "متوسط" : pending?.risk === "high" ? "بالا" : "بحرانی"}</b>{" "}
              طبقه‌بندی شده و پس از اجرا در گزارش ممیزی ثبت می‌شود.
            </AlertDescription>
          </Alert>
          <DialogFooter className="flex-row justify-start gap-2">
            <Button
              disabled={busyAction}
              onClick={async () => {
                if (!pending) return;
                setBusyAction(true);
                try {
                  const res = await fetch("/api/actions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      project: current?.name,
                      action: pending.action,
                      parameters: pending.params ?? {},
                      confirmed: true,
                    }),
                  });
                  const d = await res.json();
                  toast({ title: d.ok ? "انجام شد ✅" : "ناموفق", description: d.message });
                  await loadProjects();
                } finally {
                  setBusyAction(false);
                  setPending(null);
                }
              }}
              className="liara-gradient font-extrabold text-[#0e1512] hover:opacity-90"
            >
              {busyAction && <Loader2 className="size-4 animate-spin" />}
              تایید و اجرا
            </Button>
            <Button variant="outline" onClick={() => setPending(null)} className="border-white/15">
              انصراف
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProjectDetail({
  project,
  onAction,
  busy,
}: {
  project: LiaraProject;
  onAction: (action: string, params?: Record<string, string | number | boolean>) => void;
  busy: boolean;
}) {
  const [detail, setDetail] = useState<LiaraProject & { envCount?: number; domains?: string[] }>(project);

  useEffect(() => {
    fetch(`/api/projects/${project.name}`)
      .then((r) => r.json())
      .then((d) => d.project && setDetail(d.project))
      .catch(() => {});
  }, [project.name]);

  return (
    <div className="space-y-4">
      {/* Header card */}
      <div className="rounded-2xl border border-white/8 bg-[#1d231f]/60 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex size-12 items-center justify-center rounded-2xl liara-gradient text-xl font-black text-[#0e1512]">
              {project.name.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-lg font-black" dir="ltr">
                  {project.name}
                </h2>
                <StatusBadge status={project.status} pulse={project.status === "running"} />
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-muted-foreground">
                <span dir="ltr" className="flex items-center gap-1">
                  <Globe className="size-3.5" />
                  {detail.domains?.[0] ?? project.defaultSubdomain}
                </span>
                <span>پلتفرم: {project.platform}</span>
                <span className="latin-digits">scale: {project.scale}</span>
                <span>Zero-Downtime: {project.zeroDowntime ? "فعال" : "غیرفعال"}</span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <PlanBadge plan={planLabel(project.planId)} />
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onAction("restart")}
              className="border-[#ffc000]/30 bg-[#ffc000]/8 text-[#ffc000] hover:bg-[#ffc000]/15"
            >
              <RefreshCw className="size-3.5" />
              ری‌استارت
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() =>
                onAction("scale", { scale: project.status === "running" ? 0 : 1 })
              }
              className="border-white/12 hover:bg-white/6"
            >
              {project.status === "running" ? (
                <>
                  <PauseCircle className="size-3.5" /> خاموش کردن
                </>
              ) : (
                <>
                  <PlayCircle className="size-3.5" /> روشن کردن
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      <Tabs defaultValue="metrics" className="w-full">
        <TabsList className="bg-white/4 p-1">
          <TabsTrigger value="metrics" className="gap-1.5 data-[state=active]:bg-[#87fcc4]/12 data-[state=active]:text-[#87fcc4]">
            <Activity className="size-3.5" /> مانیتورینگ
          </TabsTrigger>
          <TabsTrigger value="logs" className="gap-1.5 data-[state=active]:bg-[#87fcc4]/12 data-[state=active]:text-[#87fcc4]">
            <ScrollText className="size-3.5" /> لاگ‌ها
          </TabsTrigger>
          <TabsTrigger value="releases" className="gap-1.5 data-[state=active]:bg-[#87fcc4]/12 data-[state=active]:text-[#87fcc4]">
            <Zap className="size-3.5" /> ریلیزها و رخدادها
          </TabsTrigger>
          <TabsTrigger value="plan" className="gap-1.5 data-[state=active]:bg-[#87fcc4]/12 data-[state=active]:text-[#87fcc4]">
            <Power className="size-3.5" /> تغییر پلن
          </TabsTrigger>
        </TabsList>

        <TabsContent value="metrics" className="mt-3">
          <MetricsTabs project={project.name} />
        </TabsContent>
        <TabsContent value="logs" className="mt-3">
          <LogsView project={project.name} paused={project.status === "stopped"} />
        </TabsContent>
        <TabsContent value="releases" className="mt-3">
          <ReleasesView project={project.name} />
        </TabsContent>
        <TabsContent value="plan" className="mt-3">
          <PlanPicker
            current={project.planId}
            onPick={(planId) => onAction("resize", { planID: planId })}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MetricsTabs({ project }: { project: string }) {
  const [metric, setMetric] = useState<MetricType>("cpu");
  const [period, setPeriod] = useState("1h");
  const [report, setReport] = useState<MetricsReport | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/projects/${project}/metrics?metric=${metric}&period=${period}`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setReport(d.report);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [project, metric, period]);

  return (
    <SectionCard
      title="شاخص‌های مصرف"
      icon={<Activity className="size-4" />}
      action={
        <div className="flex gap-1.5">
          {(["cpu", "memory", "network"] as MetricType[]).map((m) => (
            <button
              key={m}
              onClick={() => setMetric(m)}
              className={cn(
                "rounded-lg px-2.5 py-1 text-[11.5px] font-bold transition-all",
                metric === m ? "liara-gradient text-[#0e1512]" : "bg-white/5 text-muted-foreground hover:bg-white/10"
              )}
            >
              {m === "cpu" ? "پردازنده" : m === "memory" ? "حافظه" : "شبکه"}
            </button>
          ))}
          <span className="mx-1 w-px bg-white/10" />
          {(["1h", "24h", "7d"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                "rounded-lg px-2.5 py-1 text-[11.5px] font-bold transition-all latin-digits",
                period === p ? "bg-[#28c1f5]/15 text-[#28c1f5]" : "bg-white/5 text-muted-foreground hover:bg-white/10"
              )}
            >
              {p === "1h" ? "۱ ساعت" : p === "24h" ? "۲۴ ساعت" : "۷ روز"}
            </button>
          ))}
        </div>
      }
    >
      {report && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {(
              [
                ["میانگین", report.summary.avg],
                ["بیشینه", report.summary.max],
                ["کمینه", report.summary.min],
                ["P95", report.summary.p95],
              ] as const
            ).map(([label, v]) => (
              <div key={label} className="rounded-xl border border-white/8 bg-white/3 p-2.5 text-center">
                <div className="text-[10.5px] text-muted-foreground">{label}</div>
                <div
                  className={cn(
                    "text-lg font-black latin-digits",
                    v > 85 && metric !== "network" ? "text-[#ff6b6b]" : v > 70 && metric !== "network" ? "text-[#ffc000]" : "text-[#87fcc4]"
                  )}
                  dir="ltr"
                >
                  {v}
                  {report.unit === "%" ? "٪" : ""}
                </div>
              </div>
            ))}
          </div>
          <MetricsChart points={report.points} unit={report.unit} metric={metric} />
          {metric === "memory" && report.summary.avg > 85 && (
            <Alert className="mt-3 border-[#ff6b6b]/30 bg-[#ff6b6b]/6">
              <Info className="size-4 text-[#ff6b6b]" />
              <AlertTitle className="text-[13px] text-[#ff6b6b]">خطر OOM</AlertTitle>
              <AlertDescription className="text-[12px] leading-6 text-muted-foreground">
                میانگین مصرف رم بالای ۸۵٪ است — توصیه می‌شود از تب «تغییر پلن» منابع را ارتقا دهید یا
                از سوپر ایجنت تحلیل بخواهید.
              </AlertDescription>
            </Alert>
          )}
        </>
      )}
    </SectionCard>
  );
}

function LogsView({ project, paused }: { project: string; paused: boolean }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [live, setLive] = useState(!paused);
  const [filter, setFilter] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);
  const sinceRef = useRef(Math.floor(Date.now() / 1000) - 1800);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const res = await fetch(`/api/projects/${project}/logs?since=${sinceRef.current}`);
        const d = await res.json();
        if (!stop && d.logs?.length) {
          setLogs((cur) => {
            const merged = [...cur, ...d.logs.filter((l: LogEntry) => !cur.some((x) => x.t === l.t && x.message === l.message))];
            return merged.slice(-300);
          });
          const last = d.logs[d.logs.length - 1];
          if (last) sinceRef.current = Math.max(sinceRef.current, last.t);
        }
      } catch {
        /* ignore */
      }
    };
    tick();
    if (live) {
      const iv = setInterval(tick, 5000);
      return () => {
        stop = true;
        clearInterval(iv);
      };
    }
    return () => {
      stop = true;
    };
  }, [project, live]);

  useEffect(() => {
    const el = boxRef.current;
    if (el && live) el.scrollTop = el.scrollHeight;
  }, [logs, live]);

  const shown = filter
    ? logs.filter((l) => l.message.toLowerCase().includes(filter.toLowerCase()))
    : logs;

  return (
    <SectionCard
      title="لاگ زنده اپلیکیشن"
      icon={<ScrollText className="size-4" />}
      action={
        <div className="flex items-center gap-2">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="فیلتر…"
            className="h-8 w-36 rounded-lg border border-white/10 bg-[#161b18] px-2.5 text-[11.5px] outline-none placeholder:text-muted-foreground/60 focus-visible:ring-1 focus-visible:ring-[#87fcc4]/40"
            dir="ltr"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => setLive((v) => !v)}
            className={cn(
              "border-white/12",
              live ? "text-[#87fcc4]" : "text-muted-foreground"
            )}
          >
            <span className={cn("size-1.5 rounded-full", live ? "bg-[#87fcc4] pulse-dot" : "bg-[#9fb0a6]")} />
            {live ? "زنده" : "متوقف"}
          </Button>
        </div>
      }
    >
      <div
        ref={boxRef}
        className="terminal max-h-[420px] overflow-y-auto rounded-xl border border-white/8 p-3.5"
      >
        {shown.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">لاگی برای نمایش نیست</div>
        ) : (
          shown.map((l, i) => (
            <div key={`${l.t}-${i}`} className="flex gap-2.5 py-0.5">
              <span className="shrink-0 text-[#4d5b53]">
                {new Date(l.t * 1000).toLocaleTimeString("en-GB", { hour12: false })}
              </span>
              <span className={cn("w-11 shrink-0 font-bold uppercase", LOG_COLORS[l.level])}>{l.level}</span>
              <span className="min-w-0 flex-1 break-all text-[#c4d2c9]">{l.message}</span>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  );
}

function ReleasesView({ project }: { project: string }) {
  const [data, setData] = useState<{
    releases: { id: string; state: string; port: number; createdAt: string; message?: string }[];
    events: { id: string; type: string; message: string; createdAt: string }[];
  } | null>(null);

  useEffect(() => {
    fetch(`/api/projects/${project}`)
      .then((r) => r.json())
      .then((d) => setData({ releases: d.project?.releases ?? [], events: d.project?.events ?? [] }))
      .catch(() => {});
  }, [project]);

  if (!data) return <Skeleton className="h-64 rounded-2xl" />;

  const STATE_CLS: Record<string, string> = {
    running: "bg-[#87fcc4]/12 text-[#87fcc4]",
    building: "bg-[#28c1f5]/12 text-[#28c1f5]",
    failed: "bg-[#ff6b6b]/12 text-[#ff6b6b]",
    cancelled: "bg-white/8 text-muted-foreground",
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SectionCard title="ریلیزهای اخیر" icon={<Zap className="size-4" />}>
        <div className="space-y-2">
          {data.releases.map((r, i) => (
            <div key={r.id} className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/3 p-3">
              <span
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-[10.5px] font-bold",
                  STATE_CLS[r.state] ?? STATE_CLS.cancelled
                )}
              >
                {r.state}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] font-bold latin-digits" dir="ltr">
                  {r.id}
                </div>
                {r.message && <div className="truncate text-[10.5px] text-[#ff6b6b]">{r.message}</div>}
              </div>
              <span className="shrink-0 text-[10.5px] text-muted-foreground latin-digits" dir="ltr">
                {new Date(r.createdAt).toLocaleDateString("fa-IR")}
              </span>
              {i === 0 && r.state === "running" && (
                <span className="shrink-0 rounded-md bg-[#87fcc4]/10 px-1.5 py-0.5 text-[9.5px] font-bold text-[#87fcc4]">
                  فعال
                </span>
              )}
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="رخدادهای استقرار" icon={<Activity className="size-4" />}>
        <div className="relative space-y-4 pr-3">
          {data.events.map((e) => (
            <div key={e.id} className="relative border-r border-white/10 pr-4">
              <span className="absolute -right-[5px] top-1.5 size-2 rounded-full bg-[#28c1f5]" />
              <div className="text-[12px] font-bold">
                {e.type} — {e.message}
              </div>
              <div className="mt-0.5 text-[10.5px] text-muted-foreground latin-digits" dir="ltr">
                {new Date(e.createdAt).toLocaleString("fa-IR")}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

function PlanPicker({ current, onPick }: { current: string; onPick: (planId: string) => void }) {
  return (
    <SectionCard title="ارتقا / تغییر پلن" icon={<Power className="size-4" />}>
      <p className="mb-4 text-[12.5px] leading-6 text-muted-foreground">
        تغییر پلن یک عملیات <b className="text-[#ff9a4d]">پرریسک</b> است؛ قبل از اجرا، خلاصه اثرات و
        هزینه جدید نمایش داده می‌شود و نیازمند تایید شماست.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {getAllPlans().map((p) => {
          const isCurrent = p.id === current;
          return (
            <div
              key={p.id}
              className={cn(
                "rounded-xl border p-4 transition-all",
                isCurrent
                  ? "border-[#87fcc4]/45 bg-[#87fcc4]/6 brand-ring"
                  : "border-white/8 bg-white/3 hover:border-white/20"
              )}
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[13.5px] font-extrabold">{p.label}</span>
                {isCurrent ? (
                  <span className="rounded-full bg-[#87fcc4]/12 px-2 py-0.5 text-[10px] font-bold text-[#87fcc4]">
                    پلن فعلی
                  </span>
                ) : (
                  <span className="text-[11px] font-bold text-[#28c1f5] latin-digits">
                    {p.priceIRR ? `${(p.priceIRR / 1_000_000).toFixed(2)}M ریال` : "—"}
                  </span>
                )}
              </div>
              <div className="mb-3 space-y-1 text-[11.5px] text-muted-foreground latin-digits" dir="ltr">
                <div>⚙ {p.cpu} vCPU</div>
                <div>🧠 {p.ramGb} GB RAM</div>
                <div>💾 {p.diskGb} GB Disk</div>
                <div>🌐 {p.bandwidthGb} GB Traffic</div>
              </div>
              <p className="mb-3 min-h-[32px] text-[10.5px] leading-5 text-muted-foreground">{p.description}</p>
              {!isCurrent && (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full border-[#87fcc4]/30 text-[#87fcc4] hover:bg-[#87fcc4]/10"
                  onClick={() => onPick(p.id)}
                >
                  ارتقا به این پلن
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
