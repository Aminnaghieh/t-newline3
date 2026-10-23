// Persistence layer — settings, audit trail, chat history (Prisma/SQLite).
// Mirrors the Python agent's storage/ (database.py, audit.py, credentials.py).
import { db } from "@/lib/db";

export interface AgentSettings {
  liaraToken: string;
  demoMode: boolean;
  teamId: string;
}

const DEFAULT_SETTINGS: AgentSettings = {
  liaraToken: "",
  demoMode: true,
  teamId: "",
};

export async function getSettings(): Promise<AgentSettings> {
  const rows = await db.setting.findMany({ where: { key: { startsWith: "agent." } } });
  const map = Object.fromEntries(rows.map((r) => [r.key, r.value]));
  return {
    liaraToken: map["agent.liaraToken"] ?? DEFAULT_SETTINGS.liaraToken,
    demoMode: (map["agent.demoMode"] ?? String(DEFAULT_SETTINGS.demoMode)) === "true",
    teamId: map["agent.teamId"] ?? DEFAULT_SETTINGS.teamId,
  };
}

export async function saveSettings(patch: Partial<AgentSettings>): Promise<AgentSettings> {
  const entries: [string, string][] = [];
  if (patch.liaraToken !== undefined) entries.push(["agent.liaraToken", patch.liaraToken]);
  if (patch.demoMode !== undefined) entries.push(["agent.demoMode", String(patch.demoMode)]);
  if (patch.teamId !== undefined) entries.push(["agent.teamId", patch.teamId]);
  for (const [key, value] of entries) {
    await db.setting.upsert({ where: { key }, update: { value }, create: { key, value } });
  }
  return getSettings();
}

// ─── Audit (append-only, mirrors storage/audit.py) ───────────

export interface AuditInput {
  action: string;
  target: string;
  riskLevel: string;
  status: "success" | "failed" | "pending" | "approved" | "rejected";
  source?: string;
  details?: Record<string, unknown>;
}

export async function writeAudit(input: AuditInput) {
  return db.auditEvent.create({
    data: {
      action: input.action,
      target: input.target,
      riskLevel: input.riskLevel,
      status: input.status,
      source: input.source ?? "web",
      details: input.details ? JSON.stringify(input.details) : null,
    },
  });
}

export async function listAudit(limit = 100) {
  const rows = await db.auditEvent.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
  });
  return rows.map((r) => ({
    id: r.id,
    createdAt: r.createdAt.toISOString(),
    action: r.action,
    target: r.target,
    riskLevel: r.riskLevel,
    status: r.status,
    source: r.source,
    details: r.details ? JSON.parse(r.details) : null,
  }));
}

// ─── Chat history ────────────────────────────────────────────

export async function saveChatMessage(opts: {
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  payload?: unknown;
}) {
  return db.chatMessage.create({
    data: {
      sessionId: opts.sessionId,
      role: opts.role,
      content: opts.content,
      payload: opts.payload ? JSON.stringify(opts.payload) : null,
    },
  });
}

export async function getChatHistory(sessionId: string, limit = 40) {
  const rows = await db.chatMessage.findMany({
    where: { sessionId },
    orderBy: { createdAt: "asc" },
    take: limit,
  });
  return rows.map((r) => ({
    id: r.id,
    role: r.role as "user" | "assistant",
    content: r.content,
    payload: r.payload ? JSON.parse(r.payload) : null,
    createdAt: r.createdAt.toISOString(),
  }));
}

export async function clearChatHistory(sessionId: string) {
  return db.chatMessage.deleteMany({ where: { sessionId } });
}
