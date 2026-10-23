import { NextRequest } from "next/server";
import { getLogs } from "@/lib/liara/client";

export const runtime = "nodejs";

export async function GET(req: NextRequest, ctx: { params: Promise<{ name: string }> }) {
  try {
    const { name } = await ctx.params;
    const since = Number(req.nextUrl.searchParams.get("since") ?? 0) ||
      Math.floor(Date.now() / 1000) - 1800;
    const { logs, demo } = await getLogs(name, since);
    return Response.json({ logs, demo });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "خطا در دریافت لاگ‌ها" },
      { status: 500 }
    );
  }
}
