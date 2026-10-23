// RCA heuristic engine + alerting — ported from core/debugger.py & core/alerting.py
import type {
  AlertEvent,
  Diagnosis,
  ErrorCategory,
  Hypothesis,
  LogEntry,
  MetricsReport,
  Remediation,
  RiskLevel,
} from "./types";
import { getPlan } from "./plans";

export interface RcaContext {
  projectName: string;
  planId: string;
  status: string;
  logs: LogEntry[];
  metrics: { cpu?: MetricsReport; memory?: MetricsReport };
}

// ─── Remediation hash (mirrors Python compute_hash) ──────────
export async function remediationHash(r: {
  id: string;
  actionType: string;
  projectName: string;
  title: string;
  parameters: Record<string, string | number | boolean>;
}): Promise<string> {
  const payload = `${r.id}|${r.actionType}|${r.projectName}|${r.title}|${JSON.stringify(
    Object.entries(r.parameters).sort(([a], [b]) => a.localeCompare(b))
  ).replace(/[[\]"]/g, "").replace(/,/g, ",").replace(/:/g, ":")}`;
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(payload));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
}

export function nextPlanHigher(planId: string): string {
  const ladder: Record<string, string> = {
    micro: "small",
    "ir-small": "ir-medium",
    "ir-medium": "standard-base",
    small: "medium",
    "standard-base": "standard-plus",
    medium: "standard-plus",
    "standard-plus": "pro",
    pro: "pro-plus",
  };
  return ladder[planId] ?? "standard-base";
}

// ─── Heuristic RCA (faithful port of Debugger._heuristic path) ──
export function heuristicDiagnose(ctx: RcaContext): Diagnosis {
  const logsText = ctx.logs.map((l) => l.message).join(" \n ").toLowerCase();
  const hypotheses: Hypothesis[] = [];
  const remediations: Remediation[] = [];
  const projectName = ctx.projectName;

  const memAvg = ctx.metrics.memory?.summary.avg ?? 0;
  const cpuAvg = ctx.metrics.cpu?.summary.avg ?? 0;

  const pushRemediation = (r: Omit<Remediation, "projectName">) =>
    remediations.push({ ...r, projectName });

  if (
    logsText.includes("oom") ||
    logsText.includes("out of memory") ||
    logsText.includes("killed") ||
    memAvg > 85
  ) {
    hypotheses.push({
      title: "خطای اتمام حافظه رم (OOM / Out of Memory)",
      probability: memAvg > 85 ? 0.94 : 0.92,
      category: "resource_exhaustion",
      explanation:
        "کانتینر به دلیل عبور مصرف رم از سقف پلن فعلی توسط هسته لینوکس متوقف (Killed) شده است.",
      impact: "قطعی کامل اپلیکیشن و خطای 502/503 برای کاربران",
    });
    const target = nextPlanHigher(ctx.planId);
    pushRemediation({
      id: "fix_resize_ram",
      title: `ارتقای پلن به ${target}`,
      actionType: "resize",
      description: `ارتقای پلن از «${ctx.planId}» به «${target}» جهت تامین حافظه مورد نیاز`,
      riskLevel: "high",
      parameters: { planID: target },
    });
    pushRemediation({
      id: "fix_restart",
      title: "راه‌اندازی مجدد (Restart) موقت",
      actionType: "restart",
      description: "راه‌اندازی مجدد برنامه برای آزادسازی موقت رم",
      riskLevel: "medium",
      parameters: {},
    });
  }

  if (logsText.includes("eaddrinuse") || logsText.includes("address already in use")) {
    hypotheses.push({
      title: "تداخل در پورت اتصال (Port Conflict)",
      probability: 0.88,
      category: "config_error",
      explanation:
        "پورت مشخص‌شده توسط پروسس دیگری اشغال شده یا وب‌سرور به پورت اعلام‌شده در پلتفرم لیارا گوش نمی‌دهد.",
      impact: "عدم راه‌اندازی وب‌سرور و ارور CrashLoop",
    });
    pushRemediation({
      id: "fix_restart_port",
      title: "ری‌استارت کانتینر برای بستن پورت‌های قبلی",
      actionType: "restart",
      description: "ری‌استارت کل پاد کانتینر در لیارا",
      riskLevel: "medium",
      parameters: {},
    });
  }

  if (
    logsText.includes("connection refused") ||
    logsText.includes("etimedout") ||
    logsText.includes("econnrefused") ||
    logsText.includes("database") ||
    logsText.includes("mongo") ||
    logsText.includes("redis")
  ) {
    hypotheses.push({
      title: "عدم برقراری اتصال به دیتابیس یا سرویس جانبی",
      probability: 0.8,
      category: "network_issue",
      explanation:
        "برنامه نمی‌تواند به دیتابیس یا سرویس وابسته وصل شود. آدرس اتصال در متغیرهای محیطی و دسترسی شبکه را بررسی کنید.",
      impact: "بروز ارور 500 در کوئری‌ها و ریکوئست‌های دیتابیسی",
    });
  }

  if (
    logsText.includes("cannot find module") ||
    logsText.includes("modulenotfound") ||
    logsText.includes("npm err") ||
    logsText.includes("pip install") ||
    logsText.includes("build failed") ||
    logsText.includes("err!")
  ) {
    hypotheses.push({
      title: "خطای بیلد یا نصب وابستگی‌ها (Build Failure)",
      probability: 0.76,
      category: "build_failure",
      explanation:
        "فرآیند ساخت ایمیج با خطا مواجه شده — معمولاً به دلیل ناسازگاری نسخه پکیج‌ها یا نبود فایل لاک.",
      impact: "ریلیز جدید اعمال نمی‌شود و نسخه قبلی سر کار می‌ماند",
    });
  }

  if (logsText.includes("permission denied") || logsText.includes("eacces")) {
    hypotheses.push({
      title: "خطای دسترسی فایل‌سیستم (Permission Error)",
      probability: 0.7,
      category: "permission_error",
      explanation:
        "پروسس اجازه نوشتن/خواندن روی مسیر موردنظر را ندارد. در لیارا فایل‌سیستم به‌صورت پیش‌فرض قابل‌نوشتن است؛ مسیر دیسک پایدار را بررسی کنید.",
      impact: "کرش در زمان بوت یا نوشتن لاگ/آپلود",
    });
  }

  if (cpuAvg > 80) {
    hypotheses.push({
      title: "اشباع پردازنده (CPU Saturation)",
      probability: 0.72,
      category: "resource_exhaustion",
      explanation: `میانگین مصرف CPU در بازه اخیر ${cpuAvg.toFixed(0)}٪ است و ظرفیت پلن فعلی پاسخگو نیست.`,
      impact: "کندی شدید و تایم‌اوت ریکوئست‌ها",
    });
    const target = nextPlanHigher(ctx.planId);
    pushRemediation({
      id: "fix_resize_cpu",
      title: `ارتقای پلن به ${target}`,
      actionType: "resize",
      description: `افزایش vCPU با ارتقا به پلن «${target}» یا مقیاس‌دهی افقی`,
      riskLevel: "high",
      parameters: { planID: target },
    });
  }

  if (!hypotheses.length) {
    hypotheses.push({
      title: "خطای احتمالی در زمان راه‌اندازی یا کد برنامه",
      probability: 0.55,
      category: "code_bug",
      explanation:
        "در لاگ‌ها الگوی خطای شناخته‌شده‌ای دیده نشد؛ احتمالاً خطای نرم‌افزاری در خود اپلیکیشن است.",
      impact: "وابسته به نوع خطای برنامه",
    });
  }

  hypotheses.sort((a, b) => b.probability - a.probability);

  const plan = getPlan(ctx.planId);
  const summary = hypotheses[0]
    ? `محتمل‌ترین علت: ${hypotheses[0].title} — ${hypotheses[0].explanation} (پلن فعلی: ${plan?.label ?? ctx.planId}، وضعیت: ${ctx.status})`
    : "خطای نامشخص";

  return {
    rootCauseSummary: summary,
    confidence: hypotheses[0]?.probability ?? 0.5,
    hypotheses,
    suggestedRemediations: remediations,
  };
}

// ─── Alert engine (port of core/alerting.py default rules) ───

interface AlertRule {
  name: string;
  metric: "cpu" | "memory";
  threshold: number;
  severity: "warning" | "critical";
  messageTemplate: string;
}

const DEFAULT_RULES: AlertRule[] = [
  {
    name: "High CPU Usage",
    metric: "cpu",
    threshold: 80,
    severity: "warning",
    messageTemplate: "مصرف پردازنده بالاست ({value}% > {threshold}%)",
  },
  {
    name: "Critical CPU Usage",
    metric: "cpu",
    threshold: 95,
    severity: "critical",
    messageTemplate: "مصرف پردازنده در آستانه اشباع کامل است ({value}% > {threshold}%)",
  },
  {
    name: "High Memory Usage",
    metric: "memory",
    threshold: 85,
    severity: "warning",
    messageTemplate: "مصرف رم بالاست ({value}% > {threshold}%) — خطر OOM",
  },
  {
    name: "Critical Memory Usage",
    metric: "memory",
    threshold: 95,
    severity: "critical",
    messageTemplate: "مصرف رم بحرانی است ({value}% > {threshold}%) — امکان کرش سیستم",
  },
];

export function checkAlerts(
  projectName: string,
  metrics: { cpu?: MetricsReport; memory?: MetricsReport }
): AlertEvent[] {
  const events: AlertEvent[] = [];
  const now = new Date().toISOString();
  for (const rule of DEFAULT_RULES) {
    const report = rule.metric === "cpu" ? metrics.cpu : metrics.memory;
    if (!report) continue;
    const value = report.summary.avg;
    if (value > rule.threshold) {
      events.push({
        id: `${projectName}-${rule.metric}-${rule.severity}`,
        projectName,
        rule: rule.name,
        metric: rule.metric,
        severity: rule.severity,
        message: rule.messageTemplate
          .replace("{value}", value.toFixed(0))
          .replace("{threshold}", String(rule.threshold)),
        value,
        threshold: rule.threshold,
        at: now,
      });
    }
  }
  return events;
}
