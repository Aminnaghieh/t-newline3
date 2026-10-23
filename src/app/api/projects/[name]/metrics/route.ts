import { NextRequest } from "next/server";
import { getMetrics } from "@/lib/liara/client";
import type { MetricPeriod, MetricType } from "@/lib/liara/types";

export const runtime = "nodejs";

export async function GET(req: NextRequest, ctx: { params: Promise<{ name: string }> }) {
  try {
    const { name } = await ctx.params;
    const metric = (req.nextUrl.searchParams.get("metric") ?? "cpu") as MetricType;
    const period = (req.nextUrl.searchParams.get("period") ?? "1h") as MetricPeriod;
    const { report, demo } = await getMetrics(name, metric, period);
    return Response.json({ report, demo });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "خطا در دریافت متریک" },
      { status: 500 }
    );
  }
}
