"use client";
import type { AppStatus, RiskLevel } from "@/lib/liara/types";
import { cn } from "@/lib/utils";

export function LiaraLogo({ size = 34 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5 select-none" dir="ltr">
      <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
        <defs>
          <linearGradient id="liara-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#87fcc4" />
            <stop offset="1" stopColor="#28c1f5" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="11" fill="#10150f" stroke="url(#liara-g)" strokeOpacity="0.5" />
        <path d="M12 10h5.4v14.6H29V30H12z" fill="url(#liara-g)" />
        <circle cx="27.5" cy="13.5" r="3.2" fill="url(#liara-g)" />
      </svg>
      <div className="leading-tight">
        <div className="font-extrabold text-[15px] liara-gradient-text">Liara Super Agent</div>
        <div className="text-[10.5px] text-muted-foreground">دستیار هوشمند پلتفرم ابری لیارا</div>
      </div>
    </div>
  );
}

const STATUS_MAP: Record<AppStatus, { label: string; cls: string; dot: string }> = {
  running: { label: "در حال اجرا", cls: "text-[#87fcc4] bg-[#87fcc4]/10 border-[#87fcc4]/25", dot: "bg-[#87fcc4]" },
  stopped: { label: "خاموش", cls: "text-[#9fb0a6] bg-white/5 border-white/15", dot: "bg-[#9fb0a6]" },
  deploying: { label: "در حال استقرار", cls: "text-[#28c1f5] bg-[#28c1f5]/10 border-[#28c1f5]/25", dot: "bg-[#28c1f5]" },
  building: { label: "در حال بیلد", cls: "text-[#28c1f5] bg-[#28c1f5]/10 border-[#28c1f5]/25", dot: "bg-[#28c1f5]" },
  starting: { label: "در حال راه‌اندازی", cls: "text-[#ffc000] bg-[#ffc000]/10 border-[#ffc000]/25", dot: "bg-[#ffc000]" },
  failed: { label: "خطا / کرش", cls: "text-[#ff6b6b] bg-[#ff6b6b]/10 border-[#ff6b6b]/30", dot: "bg-[#ff6b6b]" },
};

export function StatusBadge({ status, pulse }: { status: AppStatus; pulse?: boolean }) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.stopped;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
        s.cls
      )}
    >
      <span className={cn("size-1.5 rounded-full", s.dot, pulse && "pulse-dot")} />
      {s.label}
    </span>
  );
}

const RISK_MAP: Record<RiskLevel, { label: string; cls: string }> = {
  low: { label: "ریسک پایین", cls: "text-[#87fcc4] bg-[#87fcc4]/10 border-[#87fcc4]/25" },
  medium: { label: "ریسک متوسط", cls: "text-[#ffc000] bg-[#ffc000]/10 border-[#ffc000]/25" },
  high: { label: "ریسک بالا", cls: "text-[#ff9a4d] bg-[#ff9a4d]/10 border-[#ff9a4d]/30" },
  critical: { label: "بحرانی", cls: "text-[#ff6b6b] bg-[#ff6b6b]/12 border-[#ff6b6b]/35" },
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  const r = RISK_MAP[level] ?? RISK_MAP.low;
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold", r.cls)}>
      {r.label}
    </span>
  );
}

export function PlanBadge({ plan }: { plan: string }) {
  return (
    <span className="inline-flex items-center rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] font-semibold text-[#d0e0ef]">
      {plan}
    </span>
  );
}

export function DemoBadge({ demo }: { demo: boolean }) {
  return demo ? (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-[#ffc000]/30 bg-[#ffc000]/10 px-3 py-1 text-[11px] font-bold text-[#ffc000]"
      title="داده‌ها شبیه‌سازی شده‌اند — برای اتصال واقعی از تنظیمات، توکن API لیارا را وارد کنید"
    >
      <span className="size-1.5 rounded-full bg-[#ffc000] pulse-dot" />
      حالت دمو
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[#87fcc4]/30 bg-[#87fcc4]/10 px-3 py-1 text-[11px] font-bold text-[#87fcc4]">
      <span className="size-1.5 rounded-full bg-[#87fcc4]" />
      اتصال زنده به لیارا
    </span>
  );
}

export function MetricBar({
  value,
  warn = 80,
  crit = 90,
}: {
  value: number;
  warn?: number;
  crit?: number;
}) {
  const color = value >= crit ? "#ff6b6b" : value >= warn ? "#ffc000" : "#87fcc4";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/8">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(100, value)}%`, background: color }}
      />
    </div>
  );
}
