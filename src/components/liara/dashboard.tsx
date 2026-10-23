"use client";
import { useCallback, useEffect, useState } from "react";
import type { AlertEvent, LiaraProject } from "@/lib/liara/types";
import { MetricBar, PlanBadge, StatusBadge } from "./badges";
import { MetricsChart } from "./metrics-chart";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Bot,
  CircleAlert,
  Cpu,
  MemoryStick,
  RefreshCw,
  Rocket,
  Server,
} from "lucide-react";
import { planLabel } from "@/lib/liara/plans";

interface DashData {
  projects: LiaraProject[];
  demo: boolean;
  alerts: AlertEvent[];
}

export function Dashboard() {
  const [data, setData] = useState<DashData | null>(null);
  const [loading, setLoading] = useState(true);
  const [cpuSnapshot, setCpuSnapshot] = useState<Record<string, number>>({});
  const [memSnapshot, setMemSnapshot] = useState<Record<string, number>>({});
  const navigate = useAppStore((s) => s.navigate);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/projects");
      const d: DashData = await res.json();
      setData(d);
      // metric snapshots per running project
      const cpu: Record<string, number> = {};
      const mem: Record<string, number> = {};
      await Promise.all(
        d.projects.map(async (p) => {
          if (p.status !== "running") {
            cpu[p.name] = 0;
            mem[p.name] = 0;
            return;
          }
          const [c, m] = await Promise.all([
            fetch(`/api/projects/${p.name}/metrics?metric=cpu&period=1h`).then((r) => r.json()),
            fetch(`/api/projects/${p.name}/metrics?metric=memory&period=1h`).then((r) => r.json()),
          ]);
          cpu[p.name] = c.report?.summary.avg ?? 0;
          mem[p.name] = m.report?.summary.avg ?? 0;
        })
      );
      setCpuSnapshot(cpu);
      setMemSnapshot(mem);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const projects = data?.projects ?? [];
  const running = projects.filter((p) => p.status === "running").length;
  const alerts = data?.alerts ?? [];
  const featured = projects.find((p) => p.status === "running") ?? projects[0];

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px] rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={<Server className="size-4" />} label="کل سرویس‌ها" value={projects.length} accent />
        <StatCard icon={<Rocket className="size-4" />} label="در حال اجرا" value={running} />
        <StatCard
          icon={<CircleAlert className="size-4" />}
          label="هشدار فعال"
          value={alerts.length}
          danger={alerts.length > 0}
        />
        <StatCard
          icon={<Bot className="size-4" />}
          label="حالت اتصال"
          value={data?.demo ? "دمو" : "زنده"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Projects list */}
        <div className="lg:col-span-2">
          <SectionCard
            title="سرویس‌های من"
            icon={<Server className="size-4" />}
            action={
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("projects")}
                className="text-[#87fcc4] hover:bg-[#87fcc4]/10"
              >
                مدیریت سرویس‌ها
                <ArrowLeft className="size-4" />
              </Button>
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              {projects.map((p) => (
                <ProjectCard
                  key={p.name}
                  project={p}
                  cpu={cpuSnapshot[p.name] ?? 0}
                  mem={memSnapshot[p.name] ?? 0}
                  onOpen={() => navigate("projects", p.name)}
                />
              ))}
            </div>
          </SectionCard>
        </div>

        {/* Alerts + quick agent */}
        <div className="space-y-4">
          <SectionCard title="هشدارهای زودهنگام" icon={<CircleAlert className="size-4" />}>
            {alerts.length === 0 ? (
              <div className="py-6 text-center text-[12.5px] text-muted-foreground">
                ✅ همه شاخص‌ها در محدوده سالم هستند
              </div>
            ) : (
              <div className="space-y-2.5">
                {alerts.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => navigate("projects", a.projectName)}
                    className={cn(
                      "w-full rounded-xl border p-3 text-right transition-transform hover:scale-[1.01]",
                      a.severity === "critical"
                        ? "border-[#ff6b6b]/35 bg-[#ff6b6b]/8"
                        : "border-[#ffc000]/30 bg-[#ffc000]/8"
                    )}
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-[12.5px] font-extrabold">{a.projectName}</span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-bold",
                          a.severity === "critical"
                            ? "bg-[#ff6b6b]/15 text-[#ff6b6b]"
                            : "bg-[#ffc000]/15 text-[#ffc000]"
                        )}
                      >
                        {a.severity === "critical" ? "بحرانی" : "هشدار"}
                      </span>
                    </div>
                    <div className="text-[11.5px] leading-5 text-muted-foreground">{a.message}</div>
                  </button>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="دستیار هوشمند" icon={<Bot className="size-4" />}>
            <p className="mb-3 text-[12.5px] leading-6 text-muted-foreground">
              سوال داری؟ عیب‌یابی، مقایسه پلن‌ها یا اجرای عملیات — سوپر ایجنت با تایید تو انجامش می‌ده.
            </p>
            <Button
              onClick={() => navigate("agent")}
              className="liara-gradient w-full font-extrabold text-[#0e1512] hover:opacity-90"
            >
              <Bot className="size-4" />
              گفتگو با سوپر ایجنت
            </Button>
          </SectionCard>
        </div>
      </div>

      {/* Featured chart */}
      {featured && cpuSnapshot[featured.name] !== undefined && (
        <SectionCard
          title={`نمای مصرف — ${featured.name}`}
          icon={<Cpu className="size-4" />}
          action={
            <Button variant="ghost" size="sm" onClick={load} className="text-muted-foreground hover:bg-white/5">
              <RefreshCw className="size-3.5" />
              بروزرسانی
            </Button>
          }
        >
          <CpuMemPeek project={featured.name} />
        </SectionCard>
      )}
    </div>
  );
}

function CpuMemPeek({ project }: { project: string }) {
  const [cpu, setCpu] = useState<ReturnType<typeof Object> | null>(null);
  useEffect(() => {
    fetch(`/api/projects/${project}/metrics?metric=cpu&period=1h`)
      .then((r) => r.json())
      .then((d) => setCpu(d.report))
      .catch(() => {});
  }, [project]);
  if (!cpu) return <Skeleton className="h-[230px] rounded-xl" />;
   
  const report = cpu as any;
  return (
    <MetricsChart points={report.points} unit={report.unit} metric="cpu" />
  );
}

function StatCard({
  icon,
  label,
  value,
  accent,
  danger,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  accent?: boolean;
  danger?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border p-4",
        danger
          ? "border-[#ff6b6b]/30 bg-[#ff6b6b]/6"
          : accent
            ? "border-[#87fcc4]/25 bg-[#87fcc4]/5 brand-ring"
            : "border-white/8 bg-[#1d231f]/60"
      )}
    >
      <div className="mb-2 flex items-center gap-2 text-muted-foreground">
        <span
          className={cn(
            "flex size-7 items-center justify-center rounded-lg",
            accent ? "liara-gradient text-[#0e1512]" : danger ? "bg-[#ff6b6b]/15 text-[#ff6b6b]" : "bg-white/6"
          )}
        >
          {icon}
        </span>
        <span className="text-[12px] font-bold">{label}</span>
      </div>
      <div className="text-2xl font-black latin-digits">{value}</div>
    </div>
  );
}

export function SectionCard({
  title,
  icon,
  action,
  children,
  className,
}: {
  title: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-2xl border border-white/8 bg-[#1d231f]/60 p-4", className)}>
      <div className="mb-3.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[14px] font-extrabold">
          {icon && <span className="text-[#87fcc4]">{icon}</span>}
          {title}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

function ProjectCard({
  project,
  cpu,
  mem,
  onOpen,
}: {
  project: LiaraProject;
  cpu: number;
  mem: number;
  onOpen: () => void;
}) {
  return (
    <button
      onClick={onOpen}
      className="group rounded-xl border border-white/8 bg-white/3 p-3.5 text-right transition-all hover:border-[#87fcc4]/30 hover:bg-[#87fcc4]/4"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[13.5px] font-extrabold" dir="ltr">
            {project.name}
          </div>
          <div className="text-[10.5px] text-muted-foreground" dir="ltr">
            {project.platform} • {project.defaultSubdomain}
          </div>
        </div>
        <StatusBadge status={project.status} pulse={project.status === "running"} />
      </div>
      <div className="mb-2 flex items-center justify-between">
        <PlanBadge plan={planLabel(project.planId)} />
        <span className="text-[10.5px] text-muted-foreground latin-digits">
          scale: {project.scale}
        </span>
      </div>
      {project.status === "running" ? (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Cpu className="size-3.5 shrink-0 text-[#87fcc4]" />
            <MetricBar value={cpu} />
            <span className="w-10 shrink-0 text-left text-[10.5px] latin-digits text-muted-foreground">
              {cpu.toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <MemoryStick className="size-3.5 shrink-0 text-[#28c1f5]" />
            <MetricBar value={mem} />
            <span className="w-10 shrink-0 text-left text-[10.5px] latin-digits text-muted-foreground">
              {mem.toFixed(0)}%
            </span>
          </div>
        </div>
      ) : (
        <div className="rounded-lg bg-white/4 px-2.5 py-1.5 text-[10.5px] text-muted-foreground">
          متریک‌ها در وضعیت فعلی غیرفعال‌اند
        </div>
      )}
    </button>
  );
}
