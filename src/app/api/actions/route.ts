import { NextRequest } from "next/server";
import { executeAction } from "@/lib/liara/client";
import { writeAudit } from "@/lib/liara/store";

export const runtime = "nodejs";

// Direct dashboard actions — the UI shows a risk-aware confirmation
// dialog before calling this; the server records everything in audit.
const RISK: Record<string, "medium" | "high" | "critical"> = {
  restart: "medium",
  scale: "high",
  resize: "high",
  zero_downtime: "medium",
};

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      project: string;
      action: string;
      parameters?: Record<string, string | number | boolean>;
      confirmed?: boolean;
    };
    const risk = RISK[body.action];
    if (!risk) {
      return Response.json({ ok: false, message: "اکشن ناشناخته" }, { status: 400 });
    }
    // Risk gate: medium+ operations require explicit confirmation flag
    if (!body.confirmed) {
      await writeAudit({
        action: body.action,
        target: body.project,
        riskLevel: risk,
        status: "pending",
        source: "dashboard",
      });
      return Response.json(
        { ok: false, needsConfirmation: true, riskLevel: risk, message: "نیازمند تایید کاربر" },
        { status: 200 }
      );
    }

    const result = await executeAction(body.project, body.action, body.parameters ?? {});
    await writeAudit({
      action: body.action,
      target: body.project,
      riskLevel: risk,
      status: result.ok ? "success" : "failed",
      source: "dashboard",
      details: { parameters: body.parameters ?? {}, message: result.message },
    });
    return Response.json(result);
  } catch (e) {
    return Response.json(
      { ok: false, message: e instanceof Error ? e.message : "خطای اجرا" },
      { status: 500 }
    );
  }
}
