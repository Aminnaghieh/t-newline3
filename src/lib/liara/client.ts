// ─────────────────────────────────────────────────────────────
// Liara PaaS API client (server-only).
// Faithful port of api/client.py behaviour: bearer auth, retries
// with exponential backoff, rate limiting, structured errors —
// with a transparent demo-mode fallback so the environment always
// works, even without a token or connectivity.
// ─────────────────────────────────────────────────────────────
import "server-only";
import type {
  LiaraProject,
  LogEntry,
  MetricsReport,
  MetricPeriod,
  MetricType,
  ProjectDetail,
} from "./types";
import { getSettings } from "./store";
import {
  applyDemoAction,
  demoLogs,
  demoMetrics,
  demoProjectDetail,
  syncDemoProjects,
} from "./demo";

export const LIARA_API_BASE = "https://api.liara.ir";

export class LiaraApiError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public endpoint = ""
  ) {
    super(message);
    this.name = "LiaraApiError";
  }
}

const RATE_READ = 60;
const RATE_WRITE = 20;
const readTs: number[] = [];
const writeTs: number[] = [];

function checkRate(method: string) {
  const now = Date.now();
  const win = 60_000;
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase())) {
    while (writeTs.length && now - writeTs[0] > win) writeTs.shift();
    if (writeTs.length >= RATE_WRITE)
      throw new LiaraApiError(429, "محدودیت نرخ درخواست (کلاینت‌ساید) — چند لحظه بعد تلاش کنید");
    writeTs.push(now);
  } else {
    while (readTs.length && now - readTs[0] > win) readTs.shift();
    if (readTs.length >= RATE_READ)
      throw new LiaraApiError(429, "محدودیت نرخ درخواست (کلاینت‌ساید) — چند لحظه بعد تلاش کنید");
    readTs.push(now);
  }
}

export async function isLiveMode(): Promise<boolean> {
  const s = await getSettings();
  return !s.demoMode && s.liaraToken.length > 10;
}

async function request<T>(
  method: string,
  path: string,
  opts: { token: string; json?: unknown; params?: Record<string, string> } 
): Promise<T> {
  checkRate(method);
  const url = new URL(LIARA_API_BASE + path);
  for (const [k, v] of Object.entries(opts.params ?? {})) url.searchParams.set(k, v);

  let lastErr: unknown;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(url.toString(), {
        method,
        headers: {
          Authorization: `Bearer ${opts.token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined,
        signal: AbortSignal.timeout(20_000),
      });
      if (res.status === 401)
        throw new LiaraApiError(401, "توکن API نامعتبر است — توکن را از console.liara.ir بگیرید");
      if (res.status === 404)
        throw new LiaraApiError(404, "پروژه موردنظر پیدا نشد", path);
      if (res.status === 429) {
        const retryAfter = Number(res.headers.get("Retry-After") ?? "30");
        if (attempt === 3) throw new LiaraApiError(429, `Rate limit — ${retryAfter} ثانیه دیگر تلاش کنید`);
        await new Promise((r) => setTimeout(r, retryAfter * 1000));
        continue;
      }
      if (!res.ok) {
        const text = (await res.text()).slice(0, 200);
        throw new LiaraApiError(res.status, text || `HTTP ${res.status}`, path);
      }
      if (res.status === 204) return {} as T;
      return (await res.json()) as T;
    } catch (e) {
      lastErr = e;
      if (e instanceof LiaraApiError && e.statusCode !== 429) throw e;
      if (attempt === 3) break;
      await new Promise((r) => setTimeout(r, 2 ** attempt * 1000));
    }
  }
  throw lastErr instanceof Error ? lastErr : new LiaraApiError(502, "اتصال به API لیارا برقرار نشد");
}

// ─── Public API (auto demo fallback) ─────────────────────────

export async function getProjects(): Promise<{ projects: LiaraProject[]; demo: boolean }> {
  if (await isLiveMode()) {
    const s = await getSettings();
    try {
      const data = await request<{ data?: unknown[] }>("GET", "/v1/projects", { token: s.liaraToken });
      const list = Array.isArray(data) ? data : (data.data as unknown[]) ?? [];
      return {
        projects: list.map(normalizeProject),
        demo: false,
      };
    } catch (e) {
      if (e instanceof LiaraApiError && e.statusCode === 401) throw e;
      // graceful degradation → demo
      return { projects: syncDemoProjects(), demo: true };
    }
  }
  return { projects: syncDemoProjects(), demo: true };
}

// Raw Liara project shape (snake/camel mix) → normalized
 
function normalizeProject(p: any): LiaraProject {
  const name = p.project_id ?? p.name ?? p._id ?? "unknown";
  return {
    id: p._id ?? name,
    name,
    platform: p.type ?? "docker",
    status: (p.status ?? (p.scale === 0 ? "stopped" : "running")) as LiaraProject["status"],
    scale: p.scale ?? 1,
    planId: p.planID ?? p.planId ?? "ir-small",
    isDeployed: Boolean(p.isDeployed ?? true),
    createdAt: p.created_at ?? new Date().toISOString(),
    defaultSubdomain: p.default_subdomain ?? `${name}.liara.run`,
    region: p.region ?? "iran",
    zeroDowntime: Boolean(p.zero_downtime ?? false),
  };
}

export async function getProjectDetail(name: string): Promise<{ project: ProjectDetail; demo: boolean }> {
  if (await isLiveMode()) {
    const s = await getSettings();
    try {
       
      const data = await request<any>("GET", `/v1/projects/${encodeURIComponent(name)}`, { token: s.liaraToken });
      const proj = normalizeProject(data);
      return {
        project: {
          ...proj,
          releases: [],
          events: [],
          envCount: Object.keys(data.envs ?? {}).length,
          domains: [proj.defaultSubdomain],
          disks: [],
        },
        demo: false,
      };
    } catch {
      return { project: demoProjectDetail(name), demo: true };
    }
  }
  return { project: demoProjectDetail(name), demo: true };
}

export async function getMetrics(
  name: string,
  metric: MetricType,
  period: MetricPeriod
): Promise<{ report: MetricsReport; demo: boolean }> {
  if (await isLiveMode()) {
    const s = await getSettings();
    try {
       
      const data = await request<any>(
        "GET",
        `/v1/projects/${encodeURIComponent(name)}/reports`,
        { token: s.liaraToken, params: { metric, period } }
      );
       
      const points = (Array.isArray(data) ? data : data.data ?? []).map((d: any) => ({
        t: Number(d.time ?? d.t ?? 0),
        v: Number(d.value ?? d.v ?? 0),
      }));
      const vals = points.map((p: { v: number }) => p.v);
      const sorted = [...vals].sort((a, b) => a - b);
      return {
        report: {
          project: name,
          metric,
          period,
          unit: metric === "network" ? "KB/s" : "%",
          points,
          summary: {
            avg: vals.length ? vals.reduce((a: number, b: number) => a + b, 0) / vals.length : 0,
            max: vals.length ? Math.max(...vals) : 0,
            min: vals.length ? Math.min(...vals) : 0,
            p95: sorted.length ? sorted[Math.floor(sorted.length * 0.95)] : 0,
          },
        },
        demo: false,
      };
    } catch {
      return { report: demoMetrics(name, metric, period), demo: true };
    }
  }
  return { report: demoMetrics(name, metric, period), demo: true };
}

export async function getLogs(name: string, since: number): Promise<{ logs: LogEntry[]; demo: boolean }> {
  if (await isLiveMode()) {
    const s = await getSettings();
    try {
       
      const data = await request<any>("GET", `/v1/projects/${encodeURIComponent(name)}/logs`, {
        token: s.liaraToken,
        params: { since: String(since) },
      });
      const arr = Array.isArray(data) ? data : data.data ?? data.logs ?? [];
       
      const logs: LogEntry[] = arr.map((l: any) => ({
        t: Number(l.time ?? l.t ?? Date.now() / 1000),
        level: guessLevel(String(l.line ?? l.message ?? "")),
        pod: l.pod ?? l.pod_name ?? "pod",
        message: String(l.line ?? l.message ?? ""),
      }));
      return { logs, demo: false };
    } catch {
      return { logs: demoLogs(name, since), demo: true };
    }
  }
  return { logs: demoLogs(name, since), demo: true };
}

function guessLevel(line: string): LogEntry["level"] {
  const l = line.toLowerCase();
  if (l.includes("error") || l.includes("fatal") || l.includes("panic") || l.includes("exception"))
    return "error";
  if (l.includes("warn")) return "warn";
  if (l.includes("debug")) return "debug";
  return "info";
}

export async function executeAction(
  name: string,
  action: string,
  params: Record<string, string | number | boolean> = {}
): Promise<{ ok: boolean; message: string; demo: boolean }> {
  const live = await isLiveMode();
  if (live) {
    const s = await getSettings();
    const token = s.liaraToken;
    try {
      switch (action) {
        case "restart":
          await request("POST", `/v1/projects/${encodeURIComponent(name)}/actions/restart`, { token });
          break;
        case "scale":
          await request("POST", `/v1/projects/${encodeURIComponent(name)}/actions/scale`, {
            token,
            json: { scale: Number(params.scale ?? 1) },
          });
          break;
        case "resize":
          await request("POST", `/v1/projects/${encodeURIComponent(name)}/resize`, {
            token,
            json: { planID: String(params.planID ?? "") },
          });
          break;
        case "zero_downtime":
          await request(
            "POST",
            `/v1/projects/${encodeURIComponent(name)}/zero-downtime/${params.enabled ? "enable" : "disable"}`,
            { token }
          );
          break;
        default:
          return { ok: false, message: `اکشن ناشناخته: ${action}`, demo: false };
      }
      return { ok: true, message: `عملیات «${action}» روی «${name}» با موفقیت اجرا شد`, demo: false };
    } catch (e) {
      return {
        ok: false,
        message: e instanceof Error ? e.message : "اجرای عملیات ناموفق بود",
        demo: false,
      };
    }
  }
  return { ...applyDemoAction(name, action, params), demo: true };
}

export async function testConnection(): Promise<{
  ok: boolean;
  demo: boolean;
  user?: unknown;
  message: string;
}> {
  const s = await getSettings();
  if (s.demoMode) {
    return { ok: true, demo: true, message: "حالت دمو فعال است — داده‌ها شبیه‌سازی می‌شوند" };
  }
  if (!s.liaraToken) {
    return { ok: false, demo: false, message: "توکن API تنظیم نشده است" };
  }
  try {
    const user = await request<unknown>("GET", "/v1/me", { token: s.liaraToken });
    return { ok: true, demo: false, user, message: "اتصال به API لیارا برقرار است" };
  } catch (e) {
    return {
      ok: false,
      demo: false,
      message: e instanceof Error ? e.message : "اتصال ناموفق",
    };
  }
}
