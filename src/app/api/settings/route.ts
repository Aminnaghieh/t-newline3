import { NextRequest } from "next/server";
import { getSettings, saveSettings } from "@/lib/liara/store";

export const runtime = "nodejs";

function maskToken(t: string): string {
  if (!t) return "";
  if (t.length <= 10) return "••••••••";
  return `${t.slice(0, 7)}${"•".repeat(Math.min(20, t.length - 10))}${t.slice(-3)}`;
}

export async function GET() {
  const s = await getSettings();
  return Response.json({
    demoMode: s.demoMode,
    hasToken: s.liaraToken.length > 10,
    tokenMasked: maskToken(s.liaraToken),
    teamId: s.teamId,
  });
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      liaraToken?: string;
      demoMode?: boolean;
      teamId?: string;
    };
    const patch: Record<string, unknown> = {};
    if (body.liaraToken !== undefined) patch.liaraToken = body.liaraToken.trim();
    if (body.demoMode !== undefined) patch.demoMode = Boolean(body.demoMode);
    if (body.teamId !== undefined) patch.teamId = body.teamId.trim();
    const s = await saveSettings(patch);
    return Response.json({
      demoMode: s.demoMode,
      hasToken: s.liaraToken.length > 10,
      tokenMasked: maskToken(s.liaraToken),
      teamId: s.teamId,
    });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "خطا در ذخیره تنظیمات" },
      { status: 500 }
    );
  }
}
