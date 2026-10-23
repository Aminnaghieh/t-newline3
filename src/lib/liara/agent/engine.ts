// ─────────────────────────────────────────────────────────────
// Super Agent engine — orchestrates: intent routing → tool
// execution → streamed final answer. Includes a rule-based
// fallback so the chat remains functional even without AI.
// ─────────────────────────────────────────────────────────────
import "server-only";
import ZAI from "z-ai-web-dev-sdk";
import type { AgentSseEvent, ActionProposal } from "../types";
import { buildSystemPrompt, FINAL_ANSWER_INSTRUCTION, ROUTER_INSTRUCTION } from "./prompts";
import { TOOLS, remediationsToProposals } from "./tools";
import { getProjects, isLiveMode } from "../client";
import { checkAlerts, heuristicDiagnose } from "../rca";
import { getMetrics, getLogs, getProjectDetail } from "../client";
import { planLabel, getAllPlans, formatPrice } from "../plans";

export interface AgentTurn {
  sessionId: string;
  message: string;
   
  history: { role: "user" | "assistant"; content: string }[];
}

type Emit = (e: AgentSseEvent) => void;

 
async function llmMessages(system: string, msgs: any[]): Promise<any[]> {
  return [{ role: "system", content: system }, ...msgs];
}

async function llmCall(system: string, msgs: { role: string; content: string }[], stream: false): Promise<string>;
async function llmCall(
  system: string,
  msgs: { role: string; content: string }[],
  stream: true
   
): Promise<AsyncGenerator<string>>;
 
async function llmCall(system: string, msgs: any[], stream: boolean): Promise<unknown> {
  const zai = await ZAI.create();
  const messages = await llmMessages(system, msgs);
  if (!stream) {
    const res = await zai.chat.completions.create({
      messages,
      thinking: { type: "disabled" },
    });
     
    return (res as any).choices?.[0]?.message?.content ?? "";
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = await zai.chat.completions.create({
    messages,
    thinking: { type: "disabled" },
    stream: true,
  } as any);

  // SDK returns the ReadableStream itself; older versions may wrap in Response
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const body = (raw as any)?.getReader ? raw : (raw as any)?.body;
  if (!body) throw new Error("stream body missing");
   
  return (async function* () {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        const s = line.trim();
        if (!s.startsWith("data:")) continue;
        const payload = s.slice(5).trim();
        if (payload === "[DONE]") return;
        try {
           
          const json = JSON.parse(payload);
          const delta = json.choices?.[0]?.delta?.content;
          if (delta) yield delta as string;
        } catch {
          /* partial json — ignore */
        }
      }
    }
  })();
}

function extractJson(text: string): unknown | null {
  const cleaned = text.replace(/```json|```/g, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start === -1 || end === -1) return null;
  try {
    return JSON.parse(cleaned.slice(start, end + 1));
  } catch {
    return null;
  }
}

// ─── Rule-based fallback (AI unavailable) ────────────────────
async function fallbackTurn(turn: AgentTurn, emit: Emit): Promise<string> {
  const q = turn.message.toLowerCase();
  const { projects } = await getProjects();
  const names = projects.map((p) => p.name);
  const mentioned = names.find((n) => q.includes(n.toLowerCase()));

  const say = (text: string) => emit({ type: "delta", text });

  if (mentioned && (q.includes("خطا") || q.includes("مشکل") || q.includes("دیباگ") || q.includes("down") || q.includes("چرا"))) {
    emit({ type: "status", stage: "collect", label: "جمع‌آوری لاگ و متریک" });
    const since = Math.floor(Date.now() / 1000) - 1800;
    const [{ logs }, cpu, memory, detail] = await Promise.all([
      getLogs(mentioned, since),
      getMetrics(mentioned, "cpu", "1h"),
      getMetrics(mentioned, "memory", "1h"),
      getProjectDetail(mentioned),
    ]);
    const diagnosis = heuristicDiagnose({
      projectName: mentioned,
      planId: detail.project.planId,
      status: detail.project.status,
      logs,
      metrics: { cpu: cpu.report, memory: memory.report },
    });
    const alerts = checkAlerts(mentioned, { cpu: cpu.report, memory: memory.report });
    emit({ type: "tool", tool: "diagnose", label: "عیب‌یابی RCA", result: { diagnosis, alerts } });
    let out = `## 🔍 نتیجه عیب‌یابی «${mentioned}»\n\n${diagnosis.rootCauseSummary}\n\n### فرضیات\n`;
    for (const h of diagnosis.hypotheses) {
      out += `- **${h.title}** — احتمال ${Math.round(h.probability * 100)}٪\n  - ${h.explanation}\n`;
    }
    if (diagnosis.suggestedRemediations.length) {
      out += `\n### 🛠 راهکارهای پیشنهادی\n`;
      for (const r of diagnosis.suggestedRemediations) {
        out += `- ${r.title} (${r.description}) — سطح ریسک: ${r.riskLevel}\n`;
      }
      out += `\nبرای اجرای راهکار، تاییدیه Human-in-the-Loop لازم است.`;
    }
    // emit proposals for executable remediations
    const proposals = await remediationsToProposals(mentioned, diagnosis.suggestedRemediations);
    for (const p of proposals) emit({ type: "proposal", proposal: p, diagnosis });
    say(out);
    return out;
  }

  if (q.includes("پلن") || q.includes("قیمت") || q.includes("plan")) {
    emit({ type: "tool", tool: "liara_docs", label: "دانش‌نامه پلن‌ها", result: { topic: "plan" } });
    let out = "## 💰 پلن‌های لیارا\n\n| پلن | vCPU | رم | دیسک | قیمت ماهانه |\n|---|---|---|---|---|\n";
    for (const p of getAllPlans()) {
      out += `| ${p.label} | ${p.cpu} | ${p.ramGb}GB | ${p.diskGb}GB | ${formatPrice(p.priceIRR)} |\n`;
    }
    out += "\nبرای پیشنهاد دقیق، فریم‌ورک و حجم پروژه‌ات را بگو.";
    say(out);
    return out;
  }

  if (q.includes("وضعیت") || q.includes("پروژه") || q.includes("status") || q.includes("لیست")) {
    emit({ type: "tool", tool: "list_projects", label: "لیست پروژه‌ها", result: { count: projects.length } });
    let out = "## 📦 پروژه‌های شما\n\n";
    for (const p of projects) {
      out += `- **${p.name}** (${p.platform}) — وضعیت: ${p.status === "running" ? "🟢 running" : p.status === "stopped" ? "⚪️ stopped" : "🔴 " + p.status} — پلن: ${planLabel(p.planId)}\n`;
    }
    say(out);
    return out;
  }

  const intro = `سلام! 👋 من **سوپر ایجنت لیارا** هستم — مهندس SRE اختصاصی تو روی پلتفرم ابری لیارا.\n\nمی‌تونم این کارها رو برات انجام بدم:\n\n- 📦 **مدیریت پروژه‌ها** — لیست، وضعیت، ری‌استارت، تغییر پلن (با تایید تو)\n- 📈 **مانیتورینگ** — CPU/رم/شبکه با هشدار آستانه\n- 📜 **لاگ‌ها** — مشاهده و تحلیل خطاها\n- 🔍 **عیب‌یابی هوشمند (RCA)** — ریشه‌یابی کرش، OOM، خطای 500\n- 🚀 **استقرار** — تحلیل سورس و پیشنهاد پلن بهینه\n\nچطور می‌تونم کمک کنم؟`;
  say(intro);
  return intro;
}

// ─── Main turn pipeline ──────────────────────────────────────
export async function runAgentTurn(turn: AgentTurn, emit: Emit): Promise<void> {
  const live = await isLiveMode();
  const { projects } = await getProjects();
  const projectNames = projects.map((p) => p.name);
  const system = buildSystemPrompt(!live, projectNames);

  // Keep context compact: last 8 turns
  const history = turn.history.slice(-8);
  const userMsgs = [...history, { role: "user" as const, content: turn.message }];

  let routerText = "";
  try {
    emit({ type: "status", stage: "think", label: "تحلیل درخواست" });
    routerText = await llmCall(
      system + "\n\n" + ROUTER_INSTRUCTION,
      userMsgs,
      false
    );
  } catch {
    await fallbackTurn(turn, emit);
    return;
  }

  const plan = extractJson(routerText) as
    | { direct?: boolean; reply?: string; tools?: { name: string; args?: Record<string, unknown> }[] }
    | null;

  // Direct knowledge answer (no tools) → stream it if we already have text,
  // otherwise re-ask for streaming. To keep latency low we emit the router
  // reply directly.
  if (plan === null || (plan.direct && (!plan.tools || !plan.tools.length))) {
    let reply = plan?.reply ?? routerText;
    if (!reply.trim()) {
      await fallbackTurn(turn, emit);
      return;
    }
    // If the router wrapped markdown fences, strip them
    reply = reply.replace(/```(markdown|md)?\n?/g, "");
    emit({ type: "delta", text: reply });
    return;
  }

  // Execute tools sequentially, streaming progress
  const toolResults: { name: string; label: string; result: unknown }[] = [];
  const proposals: ActionProposal[] = [];
  let lastDiagnosis: import("../types").Diagnosis | null = null;

  const toolCalls = plan.tools ?? [];
  for (const call of toolCalls.slice(0, 4)) {
    const tool = TOOLS[call.name];
    if (!tool) continue;
    emit({ type: "status", stage: "tool", label: tool.label });
    try {
      const args = (call.args ?? {}) as Record<string, unknown>;
      // Auto-fill project if model guessed a name not in list
      const requestedProject = "project" in args ? String(args.project ?? "") : "";
      if (
        requestedProject &&
        projectNames.length &&
        !projectNames.includes(requestedProject)
      ) {
        const guess = projectNames.find((n) => n.includes(requestedProject.slice(0, 4)));
        if (guess) args.project = guess;
      }
      const result = await tool.run(args);
      toolResults.push({ name: tool.name, label: tool.label, result });
      emit({ type: "tool", tool: tool.name, label: tool.label, result });

      // collect proposals
       
      const r = result as any;
      if (r?.proposal) proposals.push(r.proposal);
      if (r?.diagnosis) {
        lastDiagnosis = r.diagnosis as import("../types").Diagnosis;
        const remProps = await remediationsToProposals(
          (args.project as string) ?? "",
          (r.diagnosis.suggestedRemediations ?? []) as import("../types").Remediation[]
        );
        proposals.push(...remProps);
      }
    } catch (e) {
      toolResults.push({
        name: tool.name,
        label: tool.label,
        result: { error: e instanceof Error ? e.message : "tool failed" },
      });
    }
  }

  // Final streamed answer with tool context
  try {
    emit({ type: "status", stage: "answer", label: "تدوین پاسخ" });
    const toolContext = JSON.stringify(
      toolResults.map((t) => ({ tool: t.name, result: t.result })),
      null,
      1
    ).slice(0, 8000);

    const msgs = [
      ...userMsgs,
      {
        role: "assistant" as const,
        content: `[نتایج ابزارها]:\n${toolContext}`,
      },
      { role: "user" as const, content: FINAL_ANSWER_INSTRUCTION },
    ];

    const stream = (await llmCall(system, msgs, true)) as AsyncGenerator<string>;
    for await (const delta of stream) {
      emit({ type: "delta", text: delta });
    }

    // Proposals after answer so cards render at the end
    for (const p of proposals.slice(0, 2)) {
      emit({ type: "proposal", proposal: p, diagnosis: lastDiagnosis ?? undefined });
    }
  } catch {
    // streaming failed → rule-based composition from tool results
    await fallbackTurn(turn, emit);
  }
}
