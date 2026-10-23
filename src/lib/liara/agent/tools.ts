// Super Agent tool registry + executor (server-only).
// Mirrors ai/tools.py of the Python agent: read tools auto-execute,
// write actions become HITL proposals (never auto-executed).
import "server-only";
import crypto from "crypto";
import type {
  ActionProposal,
  Diagnosis,
  MetricPeriod,
  MetricType,
  Remediation,
} from "../types";
import { getLogs, getMetrics, getProjects, getProjectDetail, isLiveMode, testConnection } from "../client";
import { checkAlerts, heuristicDiagnose, remediationHash, nextPlanHigher } from "../rca";
import { getPlan, planLabel } from "../plans";
import { writeAudit } from "../store";
import { LIARA_KB } from "./prompts";

export interface ToolDef {
  name: string;
  label: string;
   
  run: (args: any) => Promise<unknown>;
}

const RISK_OF: Record<string, "medium" | "high" | "critical"> = {
  restart: "medium",
  scale: "high",
  resize: "high",
  env_update: "medium",
  delete: "critical",
};

export const TOOLS: Record<string, ToolDef> = {
  list_projects: {
    name: "list_projects",
    label: "دریافت لیست پروژه‌ها",
    run: async () => {
      const { projects, demo } = await getProjects();
      return {
        demo,
        count: projects.length,
        projects: projects.map((p) => ({
          name: p.name,
          platform: p.platform,
          status: p.status,
          plan: planLabel(p.planId),
          planId: p.planId,
          scale: p.scale,
          url: `https://${p.defaultSubdomain}`,
        })),
      };
    },
  },

  project_status: {
    name: "project_status",
    label: "بررسی وضعیت پروژه",
     
    run: async (args: { project: string }) => {
      const { project, demo } = await getProjectDetail(args.project);
      return {
        demo,
        name: project.name,
        platform: project.platform,
        status: project.status,
        plan: planLabel(project.planId),
        planId: project.planId,
        scale: project.scale,
        isDeployed: project.isDeployed,
        zeroDowntime: project.zeroDowntime,
        domains: project.domains,
        url: `https://${project.defaultSubdomain}`,
        lastRelease: project.releases[0] ?? null,
        recentEvents: project.events.slice(0, 3),
      };
    },
  },

  get_metrics: {
    name: "get_metrics",
    label: "واکشی متریک‌های مصرف",
     
    run: async (args: { project: string; metric?: string; period?: string }) => {
      const metric = (["cpu", "memory", "network"].includes(args.metric ?? "") ? args.metric : "cpu") as MetricType;
      const period = (["1h", "6h", "24h", "7d", "30d"].includes(args.period ?? "") ? args.period : "1h") as MetricPeriod;
      const { report, demo } = await getMetrics(args.project, metric, period);
      return {
        demo,
        project: args.project,
        metric,
        period,
        unit: report.unit,
        summary: report.summary,
        trend: report.points.slice(-12).map((p) => p.v),
      };
    },
  },

  get_logs: {
    name: "get_logs",
    label: "واکشی آخرین لاگ‌ها",
     
    run: async (args: { project: string; limit?: number }) => {
      const limit = Math.min(args.limit ?? 25, 60);
      const since = Math.floor(Date.now() / 1000) - 3600;
      const { logs, demo } = await getLogs(args.project, since);
      const tail = logs.slice(-limit);
      return {
        demo,
        project: args.project,
        errorCount: logs.filter((l) => l.level === "error").length,
        warnCount: logs.filter((l) => l.level === "warn").length,
        logs: tail.map((l) => ({
          level: l.level,
          pod: l.pod,
          message: l.message.slice(0, 300),
        })),
      };
    },
  },

  diagnose: {
    name: "diagnose",
    label: "عیب‌یابی هوشمند (RCA)",
     
    run: async (args: { project: string }) => {
      const since = Math.floor(Date.now() / 1000) - 1800;
      const [{ logs, demo: d1 }, cpu, memory, detail] = await Promise.all([
        getLogs(args.project, since),
        getMetrics(args.project, "cpu", "1h"),
        getMetrics(args.project, "memory", "1h"),
        getProjectDetail(args.project),
      ]);
      const diagnosis = heuristicDiagnose({
        projectName: args.project,
        planId: detail.project.planId,
        status: detail.project.status,
        logs,
        metrics: { cpu: cpu.report, memory: memory.report },
      });
      const alerts = checkAlerts(args.project, { cpu: cpu.report, memory: memory.report });
      // Attach approval hashes to executable remediations
      const withHashes = await Promise.all(
        diagnosis.suggestedRemediations.map(async (r) => ({
          ...r,
          approvalHash: await remediationHash({
            id: r.id,
            actionType: r.actionType,
            projectName: args.project,
            title: r.title,
            parameters: r.parameters,
          }),
        }))
      );
      return {
        demo: d1 || cpu.demo || memory.demo,
        diagnosis: { ...diagnosis, suggestedRemediations: withHashes },
        alerts,
      };
    },
  },

  recommend_plan: {
    name: "recommend_plan",
    label: "پیشنهاد پلن بهینه",
     
    run: async (args: {
      platform?: string;
      framework?: string;
      sizeMb?: number;
      dependencies?: number;
      project?: string;
    }) => {
      // If a project is given, use its current plan as anchor
      let currentPlan = "";
      if (args.project) {
        const { project } = await getProjectDetail(args.project);
        currentPlan = project.planId;
      }
      const sizeMb = args.sizeMb ?? 30;
      const deps = args.dependencies ?? 10;
      const platform = args.platform ?? "nodejs";
      const framework = args.framework ?? "";
      let recId = "ir-small";
      const reasons: string[] = [];
      let reqRam = 0.5;
      if (["django", "next", "nuxt", "rails", "spring"].includes(framework.toLowerCase())) {
        recId = "ir-medium";
        reqRam = 1;
        reasons.push(`فریم‌ورک ${framework} به حداقل ۱ گیگ رم نیاز دارد`);
      } else if (deps > 40) {
        recId = "ir-medium";
        reqRam = 1;
        reasons.push(`${deps} پکیج وابستگی — رم بیشتر لازم است`);
      }
      if (sizeMb > 100) {
        recId = "standard-base";
        reqRam = 2;
        reasons.push(`حجم سورس ${sizeMb}MB است`);
      }
      if (!reasons.length) reasons.push("پروژه سبک است؛ پلن اقتصادی کافی است");
      const rec = getPlan(recId);
      const result = {
        currentPlan: currentPlan || null,
        recommended: rec,
        reason: reasons.join(" • "),
        requirements: { ramGb: reqRam, sizeMb, dependencies: deps },
        alternatives: [getPlan("ir-medium"), getPlan("standard-base")].filter(Boolean),
      };
      return result;
    },
  },

  account_info: {
    name: "account_info",
    label: "بررسی وضعیت حساب و اتصال",
    run: async () => {
      const conn = await testConnection();
      return {
        ...conn,
        live: await isLiveMode(),
      };
    },
  },

  propose_action: {
    name: "propose_action",
    label: "ایجاد درخواست تایید عملیات",
     
    run: async (args: {
      project: string;
      actionType: string;
      parameters?: Record<string, string | number | boolean>;
      reason?: string;
    }) => {
      const actionType = args.actionType;
      if (!RISK_OF[actionType]) {
        return { error: `نوع عملیات «${actionType}» مجاز نیست` };
      }
      const parameters = args.parameters ?? {};
      const projectName = args.project;
      let title = "";
      let description = args.reason ?? "";

      if (actionType === "restart") {
        title = `راه‌اندازی مجدد «${projectName}»`;
        description ||= "کانتینر ری‌استارت می‌شود؛ چند ثانیه قطعی موقت خدمات خواهیم داشت.";
      } else if (actionType === "scale") {
        const on = Number(parameters.scale ?? 1) === 1;
        title = `${on ? "روشن کردن" : "خاموش کردن"} «${projectName}»`;
        description ||= on
          ? "سرویس روشن می‌شود و ترافیک مجدداً سرو خواهد شد."
          : "⚠️ سرویس کاملاً خاموش می‌شود و اپلیکیشن از دسترس خارج خواهد شد.";
      } else if (actionType === "resize") {
        const target = String(parameters.planID ?? nextPlanHigher("ir-small"));
        title = `تغییر پلن «${projectName}» به ${planLabel(target)}`;
        const tp = getPlan(target);
        description ||= `منابع سرویس به ${tp?.cpu} vCPU و ${tp?.ramGb}GB رم ارتقا می‌یابد. هزینه ماهانه جدید: ${tp ? tp.priceIRR.toLocaleString("fa-IR") + " ریال" : "—"}`;
      }

      const proposal: ActionProposal = {
        proposalId: crypto.randomUUID(),
        actionType,
        projectName,
        title,
        description,
        riskLevel: RISK_OF[actionType],
        parameters,
        approvalHash: await remediationHash({
          id: actionType,
          actionType,
          projectName,
          title,
          parameters,
        }),
        expiresAt: Date.now() + 15 * 60 * 1000,
      };
      await writeAudit({
        action: `propose_${actionType}`,
        target: projectName,
        riskLevel: proposal.riskLevel,
        status: "pending",
        source: "chat",
        details: { parameters, reason: args.reason ?? "" },
      });
      return { proposal };
    },
  },

  liara_docs: {
    name: "liara_docs",
    label: "جستجو در دانش‌نامه لیارا",
     
    run: async (args: { topic: string }) => {
      const topic = (args.topic ?? "").toLowerCase();
      const blocks: { key: string; content: string }[] = [
        { key: "deploy", content: "دیپلوی لیارا: 1) پکیج tar.gz سورس 2) POST /v2/projects/{name}/sources 3) POST /v2/projects/{name}/releases با port و type. یا از CLI liara deploy استفاده کن. برای Next.js پورت معمولاً 3000 و دستور npm start است." },
        { key: "plan", content: "پلن‌ها: ir-small (0.5vCPU/0.5GB) تا pro-plus (6vCPU/16GB). ارتقا بدون ری‌اینستال انجام می‌شود (resize)." },
        { key: "database", content: "دیتابیس‌های مدیریت‌شده لیارا: MySQL, PostgreSQL, MongoDB, Redis — از کنسول قابل ایجاد است و credentials در env اپ تنظیم می‌شود." },
        { key: "domain", content: "دامنه اختصاصی: در بخش Domains دامنه را add کن، DNS را به ns1.liara.ir/ns2.liara.ir یا A-Record به IP اپ اشاره بده و SSL رایگان Let's Encrypt خودکار صادر می‌شود." },
        { key: "disk", content: "دیسک پایدار: برای داده ماندگار (آپلود/SQLite) از بخش Disks دیسک بساز و به مسیر mount کند. بدون دیسک فایل‌سیستم با هر دیپلوی پاک می‌شود." },
        { key: "log", content: "لاگ: GET /v1/projects/{name}/logs?since=<unix> برای تاریخی؛ WebSocket برای زنده. در وب‌اپ سوپر ایجنت، تب لاگ هر پروژه هر ۵ ثانیه رفرش می‌شود." },
        { key: "env", content: "متغیر محیطی: POST /v1/projects/update-envs با {project, variables:[{key,value}]} — پس از تغییر، ری‌استارت لازم است." },
        { key: "token", content: "توکن API: کنسول لیارا → بخش API Token → ساخت توکن با دسترسی کامل یا محدود. توکن را فقط در تنظیمات همین محیط ذخیره کن." },
      ];
      const hits = blocks.filter(
        (b) => topic.includes(b.key) || b.content.toLowerCase().includes(topic)
      );
      return {
        query: args.topic,
        results: (hits.length ? hits : blocks.slice(0, 3)).map((b) => b.content),
      };
    },
  },
};

// Shared export for diagnosis payloads → proposals conversion.
// Hash is recomputed with the approve-gate convention (id = actionType)
// so every proposal can be verified by /api/agent/approve.
export async function remediationsToProposals(
  projectName: string,
  remediations: Remediation[]
): Promise<ActionProposal[]> {
  const executable = remediations
    .filter((r) => ["restart", "scale", "resize"].includes(r.actionType))
    .slice(0, 2);
  const out: ActionProposal[] = [];
  for (const r of executable) {
    const parameters = r.parameters ?? {};
    out.push({
      proposalId: crypto.randomUUID(),
      actionType: r.actionType,
      projectName,
      title: r.title,
      description: r.description,
      riskLevel: r.riskLevel,
      parameters,
      approvalHash: await remediationHash({
        id: r.actionType,
        actionType: r.actionType,
        projectName,
        title: r.title,
        parameters,
      }),
      expiresAt: Date.now() + 15 * 60 * 1000,
    });
  }
  return out;
}

export { LIARA_KB };
export type { Diagnosis };
