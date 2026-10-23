"use client";
import { useState } from "react";
import type { ActionProposal } from "@/lib/liara/types";
import { RiskBadge } from "./badges";
import { Button } from "@/components/ui/button";
import { ShieldCheck, ShieldX, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const RISK_BORDER: Record<string, string> = {
  low: "border-[#87fcc4]/30",
  medium: "border-[#ffc000]/35",
  high: "border-[#ff9a4d]/40",
  critical: "border-[#ff6b6b]/45",
};

export type ProposalState = "pending" | "approved" | "rejected" | "expired" | "failed" | "success";

export function ProposalCard({
  proposal,
  onResolved,
}: {
  proposal: ActionProposal;
  onResolved?: (state: ProposalState, message: string) => void;
}) {
  const [state, setState] = useState<ProposalState>("pending");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const { toast } = useToast();

  const respond = async (approved: boolean) => {
    setBusy(true);
    try {
      const res = await fetch("/api/agent/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ proposal, approved }),
      });
      const data = await res.json();
      const next: ProposalState = data.ok ? (approved ? "success" : "rejected") : "failed";
      setState(next);
      setResult(data.message ?? "");
      onResolved?.(next, data.message ?? "");
      toast({
        title: approved ? "عملیات اجرا شد" : "عملیات رد شد",
        description: data.message,
      });
    } catch {
      setState("failed");
      setResult("ارتباط با سرور برقرار نشد");
    } finally {
      setBusy(false);
    }
  };

  const expired = proposal.expiresAt < Date.now();

  return (
    <div
      className={`rounded-2xl border ${RISK_BORDER[proposal.riskLevel] ?? "border-white/15"} bg-[#202723]/80 p-4 shadow-lg`}
    >
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-[#87fcc4]/12 text-[#87fcc4]">
            🛡
          </span>
          <div>
            <div className="text-[13px] font-extrabold">{proposal.title}</div>
            <div className="text-[10.5px] text-muted-foreground">
              دروازه تایید انسانی — امضا:{" "}
              <span className="latin-digits" dir="ltr">
                {proposal.approvalHash.slice(0, 10)}
              </span>
            </div>
          </div>
        </div>
        <RiskBadge level={proposal.riskLevel as "medium"} />
      </div>

      <p className="mb-3 text-[12.5px] leading-6 text-muted-foreground">{proposal.description}</p>

      {Object.keys(proposal.parameters).length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5" dir="ltr">
          {Object.entries(proposal.parameters).map(([k, v]) => (
            <span
              key={k}
              className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10.5px] text-[#d0e0ef] latin-digits"
            >
              {k}={String(v)}
            </span>
          ))}
        </div>
      )}

      {state === "pending" && !expired && (
        <div className="flex gap-2">
          <Button
            onClick={() => respond(true)}
            disabled={busy}
            className="liara-gradient flex-1 font-extrabold text-[#0e1512] hover:opacity-90"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
            تایید و اجرا
          </Button>
          <Button
            onClick={() => respond(false)}
            disabled={busy}
            variant="outline"
            className="flex-1 border-white/15 hover:bg-white/5"
          >
            <ShieldX className="size-4" />
            رد کردن
          </Button>
        </div>
      )}

      {(expired || state !== "pending") && (
        <div
          className={`rounded-lg px-3 py-2 text-[12px] font-bold ${
            state === "success"
              ? "bg-[#87fcc4]/10 text-[#87fcc4]"
              : state === "rejected"
                ? "bg-white/5 text-muted-foreground"
                : "bg-[#ff6b6b]/10 text-[#ff6b6b]"
          }`}
        >
          {expired
            ? "⏰ مهلت تایید این عملیات منقضی شد (۱۵ دقیقه)"
            : state === "success"
              ? `✅ ${result}`
              : state === "rejected"
                ? `🚫 ${result}`
                : `⚠️ ${result}`}
        </div>
      )}
    </div>
  );
}
