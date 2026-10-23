// ─────────────────────────────────────────────────────────────
// Demo engine — realistic mock data so the whole environment is
// fully explorable without a real Liara token. Deterministic-ish
// with smooth random walks; ported spirit of the Python agent's
// offline cache fallback.
// ─────────────────────────────────────────────────────────────
import type {
  DeployEvent,
  LiaraProject,
  LogEntry,
  MetricsReport,
  MetricPeriod,
  MetricPoint,
  MetricType,
  ProjectDetail,
  ReleaseInfo,
  AppStatus,
} from "./types";

// Simple seeded PRNG (mulberry32) for stable demo series
function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function rng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const DEMO_PROJECTS: LiaraProject[] = [
  {
    id: "prj_shop01",
    name: "shop-front",
    platform: "nodejs",
    status: "running",
    scale: 1,
    planId: "ir-medium",
    isDeployed: true,
    createdAt: "2025-11-04T08:21:00Z",
    defaultSubdomain: "shop-front.liara.run",
    region: "iran",
    zeroDowntime: true,
  },
  {
    id: "prj_api02",
    name: "orders-api",
    platform: "python",
    status: "running",
    scale: 1,
    planId: "standard-base",
    isDeployed: true,
    createdAt: "2025-12-19T14:05:00Z",
    defaultSubdomain: "orders-api.liara.run",
    region: "iran",
    zeroDowntime: true,
  },
  {
    id: "prj_blog03",
    name: "content-blog",
    platform: "php",
    status: "running",
    scale: 1,
    planId: "ir-small",
    isDeployed: true,
    createdAt: "2026-01-27T10:44:00Z",
    defaultSubdomain: "content-blog.liara.run",
    region: "iran",
    zeroDowntime: false,
  },
  {
    id: "prj_bot04",
    name: "notify-bot",
    platform: "go",
    status: "failed",
    scale: 1,
    planId: "ir-small",
    isDeployed: false,
    createdAt: "2026-02-15T18:30:00Z",
    defaultSubdomain: "notify-bot.liara.run",
    region: "iran",
    zeroDowntime: false,
  },
  {
    id: "prj_stg05",
    name: "staging-panel",
    platform: "nodejs",
    status: "stopped",
    scale: 0,
    planId: "micro",
    isDeployed: true,
    createdAt: "2026-03-02T09:12:00Z",
    defaultSubdomain: "staging-panel.liara.run",
    region: "iran",
    zeroDowntime: false,
  },
];

// Baseline metric profiles per project (drives OOM/bug demo scenarios)
const PROFILE: Record<string, { cpu: [number, number]; memory: [number, number]; network: [number, number] }> = {
  "shop-front": { cpu: [42, 14], memory: [72, 10], network: [35, 12] },
  "orders-api": { cpu: [38, 12], memory: [88, 6], network: [52, 18] }, // mem high → OOM alert
  "content-blog": { cpu: [18, 8], memory: [41, 8], network: [12, 6] },
  "notify-bot": { cpu: [5, 4], memory: [12, 5], network: [2, 2] },
  "staging-panel": { cpu: [0, 0], memory: [0, 0], network: [0, 0] },
};

function periodSeconds(p: MetricPeriod): number {
  return { "1h": 3600, "6h": 6 * 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400 }[p];
}

export function demoMetrics(
  project: string,
  metric: MetricType,
  period: MetricPeriod
): MetricsReport {
  const prof = PROFILE[project] ?? { cpu: [30, 10], memory: [50, 10], network: [20, 8] } as const;
  const base = prof[metric][0];
  const jitter = prof[metric][1];
  const total = periodSeconds(period);
  const step = period === "1h" ? 60 : period === "6h" ? 300 : period === "24h" ? 900 : period === "7d" ? 3600 : 21600;
  const count = Math.min(120, Math.floor(total / step));
  const now = Math.floor(Date.now() / 1000);
  const rand = rng(hashSeed(`${project}:${metric}:${period}:${Math.floor(now / (step * 5))}`));

  const points: MetricPoint[] = [];
  let v = base;
  const unit = metric === "network" ? "KB/s" : metric === "disk" ? "GB" : "%";
  for (let i = count - 1; i >= 0; i--) {
    // random walk with pull toward base
    v += (rand() - 0.5) * jitter + (base - v) * 0.08;
    v = Math.max(0, Math.min(99, v));
    // diurnal-ish wave
    const wave = Math.sin((i / count) * Math.PI * 2) * jitter * 0.6;
    const val = Math.max(0, Math.min(99.5, v + wave));
    points.push({ t: now - i * step, v: Number(val.toFixed(1)) });
  }
  const vals = points.map((p) => p.v);
  const sorted = [...vals].sort((a, b) => a - b);
  return {
    project,
    metric,
    period,
    unit,
    points,
    summary: {
      avg: Number((vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)),
      max: Number(Math.max(...vals).toFixed(1)),
      min: Number(Math.min(...vals).toFixed(1)),
      p95: Number(sorted[Math.floor(sorted.length * 0.95)].toFixed(1)),
    },
  };
}

const DEMO_LOG_TEMPLATES: Record<string, ((r: () => number) => LogEntry)[]> = {
  "orders-api": [
    (r) => ({
      t: 0,
      level: "info",
      pod: "orders-api-7d9f6c-bx2zk",
      message: `POST /v1/orders 200 ${Math.floor(40 + r() * 120)}ms`,
    }),
    (r) => ({
      t: 0,
      level: "warn",
      pod: "orders-api-7d9f6c-bx2zk",
      message: `Memory usage high: heap_used=${(0.62 + r() * 0.2).toFixed(2)}GB plan_limit=2.00GB`,
    }),
    (r) => ({
      t: 0,
      level: "error",
      pod: "orders-api-7d9f6c-mx4pq",
      message: `FATAL: container killed (OOM) — out of memory, exit code 137`,
    }),
    (r) => ({
      t: 0,
      level: "info",
      pod: "orders-api-7d9f6c-bx2zk",
      message: `GET /healthz 200 OK`,
    }),
    (r) => ({
      t: 0,
      level: "error",
      pod: "orders-api-7d9f6c-mx4pq",
      message: `System.OutOfMemoryException: Exception of type 'Out of memory' was thrown. worker exited`,
    }),
    (r) => ({
      t: 0,
      level: "debug",
      pod: "orders-api-7d9f6c-bx2zk",
      message: `redis connection pool: acquired=8 idle=2`,
    }),
  ],
  default: [
    (r) => ({
      t: 0,
      level: "info",
      pod: `pod-${Math.floor(r() * 9)}abc`,
      message: `GET / 200 ${Math.floor(20 + r() * 90)}ms`,
    }),
    (r) => ({
      t: 0,
      level: "info",
      pod: `pod-${Math.floor(r() * 9)}abc`,
      message: `POST /api/session 201 created`,
    }),
    (r) => ({
      t: 0,
      level: "warn",
      pod: `pod-${Math.floor(r() * 9)}abc`,
      message: `slow query detected: ${Math.floor(300 + r() * 700)}ms db=query.users`,
    }),
    (r) => ({
      t: 0,
      level: "error",
      pod: `pod-${Math.floor(r() * 9)}abc`,
      message: `Error: connect ECONNREFUSED 10.20.0.5:5432 (postgres primary)`,
    }),
    (r) => ({
      t: 0,
      level: "info",
      pod: `pod-${Math.floor(r() * 9)}abc`,
      message: `deploy: image pushed digest sha256:${Math.floor(r() * 1e9).toString(16)}`,
    }),
  ],
  "notify-bot": [
    (r) => ({
      t: 0,
      level: "error",
      pod: "notify-bot-5c88dd-xq7lb",
      message: `panic: listen tcp :8080 -> bind: address already in use (EADDRINUSE)`,
    }),
    (r) => ({
      t: 0,
      level: "error",
      pod: "notify-bot-5c88dd-xq7lb",
      message: `goroutine 1 [running]: main.main() crash-loop restart #${Math.floor(1 + r() * 30)}`,
    }),
    (r) => ({
      t: 0,
      level: "info",
      pod: "notify-bot-5c88dd-xq7lb",
      message: `container restarting (backoff 5s)`,
    }),
  ],
};

export function demoLogs(project: string, since: number, limit = 60): LogEntry[] {
  const now = Math.floor(Date.now() / 1000);
  const rand = rng(hashSeed(`${project}:logs:${Math.floor(now / 30)}`));
  const templates = DEMO_LOG_TEMPLATES[project] ?? DEMO_LOG_TEMPLATES["default"];
  const out: LogEntry[] = [];
  for (let i = 0; i < limit; i++) {
    const tpl = templates[Math.floor(rand() * templates.length)];
    const e = tpl(rand);
    e.t = Math.max(since, now - Math.floor(rand() * (now - since || 1800)));
    out.push(e);
  }
  return out.sort((a, b) => a.t - b.t);
}

export function demoReleases(project: string): ReleaseInfo[] {
  const now = Date.now();
  const rand = rng(hashSeed(`${project}:rel`));
  const failed = project === "notify-bot";
  return Array.from({ length: 6 }, (_, i) => ({
    id: `rel_${(hashSeed(project) + i).toString(16).slice(0, 10)}`,
    state: i === 0 && failed ? "failed" : i === 0 ? "running" : "cancelled",
    port: project === "orders-api" ? 8000 : project === "notify-bot" ? 8080 : 3000,
    type: DEMO_PROJECTS.find((p) => p.name === project)?.platform ?? "nodejs",
    createdAt: new Date(now - (i * 86400000 * (1 + Math.floor(rand() * 3)))).toISOString(),
    message:
      i === 0 && failed
        ? "Build failed: exit code 1 (panic at boot — EADDRINUSE)"
        : undefined,
  })) as ReleaseInfo[];
}

export function demoEvents(project: string): DeployEvent[] {
  const now = Date.now();
  const failed = project === "notify-bot";
  const base: DeployEvent[] = [
    {
      id: `${project}-ev1`,
      type: "deploy",
      message: failed
        ? "Deployment failed: container exited immediately after start (code 1)"
        : "Deployment succeeded — release is live",
      createdAt: new Date(now - 3600_000 * 2).toISOString(),
    },
    {
      id: `${project}-ev2`,
      type: "build",
      message: failed
        ? "Image build completed in 1m 42s"
        : "Image build completed in 58s",
      createdAt: new Date(now - 3600_000 * 2.3).toISOString(),
    },
    {
      id: `${project}-ev3`,
      type: "source",
      message: "Source upload received (application.tar.gz)",
      createdAt: new Date(now - 3600_000 * 2.5).toISOString(),
    },
    {
      id: `${project}-ev4`,
      type: "scale",
      message: "Scale set to 1 instance",
      createdAt: new Date(now - 86400_000).toISOString(),
    },
  ];
  return base;
}

export function demoProjectDetail(project: string): ProjectDetail {
  const p = DEMO_PROJECTS.find((x) => x.name === project);
  if (!p) throw new Error("پروژه یافت نشد");
  return {
    ...p,
    releases: demoReleases(project),
    events: demoEvents(project),
    envCount: project === "orders-api" ? 7 : 3,
    domains: [p.defaultSubdomain, ...(project === "shop-front" ? ["shop.example.ir"] : [])],
    disks: project === "content-blog" ? [{ name: "wp-uploads", sizeGb: 5 }] : [],
  };
}

// ─── Demo state mutation (actions actually change demo state) ──
const demoState = new Map<string, { status: AppStatus; scale: number; planId: string }>();
for (const p of DEMO_PROJECTS) {
  demoState.set(p.name, { status: p.status, scale: p.scale, planId: p.planId });
}

export function applyDemoAction(
  project: string,
  action: string,
  params: Record<string, string | number | boolean> = {}
): { ok: boolean; message: string } {
  const st = demoState.get(project);
  if (!st) return { ok: false, message: "پروژه یافت نشد" };
  switch (action) {
    case "restart":
      st.status = "running";
      return { ok: true, message: `سرویس «${project}» با موفقیت ری‌استارت شد` };
    case "scale":
      st.scale = Number(params.scale ?? 1);
      st.status = st.scale === 0 ? "stopped" : "running";
      return {
        ok: true,
        message:
          st.scale === 0
            ? `سرویس «${project}» خاموش شد (scale=0)`
            : `سرویس «${project}» روشن شد (scale=1)`,
      };
    case "resize": {
      const planId = String(params.planID ?? "ir-medium");
      st.planId = planId;
      return { ok: true, message: `پلن سرویس «${project}» به «${planId}» تغییر کرد` };
    }
    case "zero_downtime":
      return { ok: true, message: `Zero-downtime برای «${project}» تنظیم شد` };
    default:
      return { ok: false, message: `اکشن ناشناخته: ${action}` };
  }
}

export function syncDemoProjects(): LiaraProject[] {
  return DEMO_PROJECTS.map((p) => {
    const st = demoState.get(p.name)!;
    return { ...p, status: st.status, scale: st.scale, planId: st.planId };
  });
}

export function resetDemoState() {
  for (const p of DEMO_PROJECTS) {
    demoState.set(p.name, { status: p.status, scale: p.scale, planId: p.planId });
  }
}
