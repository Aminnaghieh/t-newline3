"use client";
import { useEffect, useState } from "react";
import { SectionCard } from "./dashboard";
import { RiskBadge } from "./badges";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ScrollText, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface AuditRow {
  id: string;
  createdAt: string;
  action: string;
  target: string;
  riskLevel: string;
  status: string;
  source: string;
  details?: Record<string, unknown> | null;
}

const STATUS_CLS: Record<string, string> = {
  success: "bg-[#87fcc4]/12 text-[#87fcc4]",
  approved: "bg-[#87fcc4]/12 text-[#87fcc4]",
  failed: "bg-[#ff6b6b]/12 text-[#ff6b6b]",
  rejected: "bg-white/8 text-muted-foreground",
  pending: "bg-[#ffc000]/12 text-[#ffc000]",
};

const ACTION_FA: Record<string, string> = {
  restart: "ری‌استارت",
  scale: "خاموش/روشن (Scale)",
  resize: "تغییر پلن",
  deploy: "استقرار",
  analyze_project: "تحلیل پروژه",
  propose_restart: "پیشنهاد ری‌استارت",
  propose_scale: "پیشنهاد خاموش/روشن",
  propose_resize: "پیشنهاد تغییر پلن",
};

export function AuditView() {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [filter, setFilter] = useState("");

  const load = () =>
    fetch("/api/audit?limit=150")
      .then((r) => r.json())
      .then((d) => setRows(d.events ?? []))
      .catch(() => setRows([]));

  useEffect(() => {
    load();
  }, []);

  const shown = (rows ?? []).filter(
    (r) =>
      !filter ||
      r.action.includes(filter) ||
      r.target.toLowerCase().includes(filter.toLowerCase()) ||
      r.source.includes(filter)
  );

  return (
    <SectionCard
      title="گزارش ممیزی (Append-Only)"
      icon={<ScrollText className="size-4" />}
      action={
        <Button variant="ghost" size="sm" onClick={load} className="text-muted-foreground hover:bg-white/5">
          <RefreshCw className="size-3.5" /> بروزرسانی
        </Button>
      }
    >
      <div className="mb-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="جستجو در اکشن‌ها، سرویس‌ها، منبع…"
          className="h-9 w-full max-w-sm rounded-lg border border-white/10 bg-[#161b18] px-3 text-[12.5px] outline-none placeholder:text-muted-foreground/60 focus-visible:ring-1 focus-visible:ring-[#87fcc4]/40"
        />
      </div>

      {!rows ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12 rounded-xl" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <div className="py-10 text-center text-[13px] text-muted-foreground">
          هنوز عملیاتی ثبت نشده — پس از اجرای عملیات‌ها اینجا لاگ تغییرناپذیرشان را می‌بینی.
        </div>
      ) : (
        <div className="max-h-[560px] space-y-2 overflow-y-auto pl-1">
          {shown.map((r) => (
            <div
              key={r.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-white/8 bg-white/3 px-3.5 py-2.5"
            >
              <span
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-[10.5px] font-bold",
                  STATUS_CLS[r.status] ?? STATUS_CLS.pending
                )}
              >
                {r.status === "success"
                  ? "موفق"
                  : r.status === "failed"
                    ? "ناموفق"
                    : r.status === "pending"
                      ? "در انتظار"
                      : r.status === "approved"
                        ? "تاییدشده"
                        : "ردشده"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] font-bold">
                  {ACTION_FA[r.action] ?? r.action} — <span dir="ltr">{r.target}</span>
                </div>
                <div className="text-[10.5px] text-muted-foreground latin-digits" dir="ltr">
                  {new Date(r.createdAt).toLocaleString("fa-IR")} • منبع: {r.source}
                  {r.details && Object.keys(r.details).length > 0 && (
                    <span className="mr-2" dir="ltr">
                      {JSON.stringify(r.details).slice(0, 90)}
                    </span>
                  )}
                </div>
              </div>
              <RiskBadge level={r.riskLevel as "medium"} />
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
