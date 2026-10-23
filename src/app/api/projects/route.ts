import { getProjects, getMetrics } from "@/lib/liara/client";
import { checkAlerts } from "@/lib/liara/rca";
import type { AlertEvent } from "@/lib/liara/types";

export const runtime = "nodejs";

export async function GET() {
  try {
    const { projects, demo } = await getProjects();
    // Alerts snapshot for the dashboard (memory + cpu per running project)
    const alerts: AlertEvent[] = [];
    for (const p of projects.filter((x) => x.status === "running")) {
      const cpu = await getMetrics(p.name, "cpu", "1h");
      const mem = await getMetrics(p.name, "memory", "1h");
      alerts.push(...checkAlerts(p.name, { cpu: cpu.report, memory: mem.report }));
    }
    return Response.json({ projects, demo, alerts });
  } catch (e) {
    return Response.json(
      { error: e instanceof Error ? e.message : "خطا در دریافت پروژه‌ها" },
      { status: 500 }
    );
  }
}
