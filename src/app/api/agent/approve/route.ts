import { NextRequest } from "next/server";
import { executeAction } from "@/lib/liara/client";
import { remediationHash } from "@/lib/liara/rca";
import { writeAudit } from "@/lib/liara/store";
import type { ActionProposal } from "@/lib/liara/types";

export const runtime = "nodejs";

// Human-in-the-Loop approval gate — port of cli/components/approval.py.
// The server recomputes the approval hash and rejects tampered/stale
// proposals, then executes the action and writes an audit entry.
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      proposal: ActionProposal;
      approved: boolean;
      source?: string;
    };
    const p = body.proposal;
    if (!p?.proposalId || !p.actionType) {
      return Response.json({ ok: false, message: "درخواست نامعتبر است" }, { status: 400 });
    }

    // Rebind risk level server-side (never trust the client's copy)
    const SERVER_RISK: Record<string, "medium" | "high" | "critical"> = {
      restart: "medium",
      scale: "high",
      resize: "high",
      env_update: "medium",
    };
    const risk = SERVER_RISK[p.actionType];
    if (!risk) {
      return Response.json(
        { ok: false, message: `نوع عملیات «${p.actionType}» از طریق این دروازه قابل اجرا نیست` },
        { status: 400 }
      );
    }

    // Expiry check
    if (p.expiresAt && Date.now() > p.expiresAt) {
      await writeAudit({
        action: `approve_${p.actionType}`,
        target: p.projectName,
        riskLevel: risk,
        status: "rejected",
        source: body.source ?? "chat",
        details: { reason: "expired" },
      });
      return Response.json({ ok: false, message: "مهلت تایید این عملیات منقضی شده است (۱۵ دقیقه)" });
    }

    // Tamper check — recompute hash
    const expected = await remediationHash({
      id: p.actionType,
      actionType: p.actionType,
      projectName: p.projectName,
      title: p.title,
      parameters: p.parameters ?? {},
    });
    if (expected !== p.approvalHash) {
      await writeAudit({
        action: `approve_${p.actionType}`,
        target: p.projectName,
        riskLevel: risk,
        status: "rejected",
        source: body.source ?? "chat",
        details: { reason: "hash_mismatch" },
      });
      return Response.json({ ok: false, message: "امضای عملیات معتبر نیست (hash mismatch)" });
    }

    if (!body.approved) {
      await writeAudit({
        action: `${p.actionType}`,
        target: p.projectName,
        riskLevel: risk,
        status: "rejected",
        source: body.source ?? "chat",
        details: { parameters: p.parameters },
      });
      return Response.json({ ok: true, executed: false, message: "عملیات توسط شما رد شد ✅" });
    }

    // Execute
    const result = await executeAction(p.projectName, p.actionType, p.parameters ?? {});
    await writeAudit({
      action: p.actionType,
      target: p.projectName,
      riskLevel: risk,
      status: result.ok ? "success" : "failed",
      source: body.source ?? "chat",
      details: { parameters: p.parameters, message: result.message },
    });
    return Response.json({ ok: result.ok, executed: result.ok, message: result.message });
  } catch (e) {
    return Response.json(
      { ok: false, message: e instanceof Error ? e.message : "خطای اجرا" },
      { status: 500 }
    );
  }
}
