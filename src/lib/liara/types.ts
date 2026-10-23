// ─────────────────────────────────────────────────────────────
// Shared types for the Liara Super Agent — ported from the
// original Python SRE Agent (liara_agent.models + constants)
// ─────────────────────────────────────────────────────────────

export type AppStatus =
  | "running"
  | "stopped"
  | "deploying"
  | "failed"
  | "building"
  | "starting";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type MetricType = "cpu" | "memory" | "network" | "disk";
export type MetricPeriod = "1h" | "6h" | "24h" | "7d" | "30d";

export type ErrorCategory =
  | "resource_exhaustion"
  | "code_bug"
  | "config_error"
  | "dependency_failure"
  | "network_issue"
  | "build_failure"
  | "permission_error"
  | "unknown";

export interface PlanInfo {
  id: string;
  label: string;
  cpu: number; // vCPU cores
  ramGb: number;
  diskGb: number;
  bandwidthGb: number;
  priceIRR: number; // monthly, IRR
  description: string;
}

export interface LiaraProject {
  id: string;
  name: string;
  platform: string;
  status: AppStatus;
  scale: number;
  planId: string;
  isDeployed: boolean;
  createdAt: string;
  defaultSubdomain: string;
  region: string;
  zeroDowntime: boolean;
}

export interface MetricPoint {
  t: number; // epoch seconds
  v: number; // value
}

export interface MetricsReport {
  project: string;
  metric: MetricType;
  period: MetricPeriod;
  unit: string;
  points: MetricPoint[];
  summary: { avg: number; max: number; min: number; p95: number };
}

export interface LogEntry {
  t: number;
  level: "info" | "warn" | "error" | "debug";
  pod: string;
  message: string;
}

export interface ReleaseInfo {
  id: string;
  state: "running" | "building" | "failed" | "cancelled";
  port: number;
  type: string;
  createdAt: string;
  message?: string;
}

export interface DeployEvent {
  id: string;
  type: string;
  message: string;
  createdAt: string;
}

export interface ProjectDetail extends LiaraProject {
  releases: ReleaseInfo[];
  events: DeployEvent[];
  envCount: number;
  domains: string[];
  disks: { name: string; sizeGb: number }[];
}

export interface AnalysisResult {
  platform: string;
  framework: string | null;
  port: number;
  startCmd: string;
  buildCmd: string | null;
  dependencies: string[];
  envVarsNeeded: string[];
  hasDockerfile: boolean;
  projectSizeMb: number;
  notes: string[];
}

export interface PlanRecommendationResult {
  recommendedPlan: string;
  reason: string;
  alternatives: string[];
  estimatedRequirements: {
    cpuCores: number;
    ramGb: number;
    projectSizeMb: number;
  };
}

// ─── RCA / Debugger ──────────────────────────────────────────

export interface Hypothesis {
  title: string;
  probability: number; // 0..1
  category: ErrorCategory;
  explanation: string;
  impact: string;
}

export interface Remediation {
  id: string;
  title: string;
  actionType: "restart" | "scale" | "resize" | "env_update" | "manual";
  description: string;
  riskLevel: RiskLevel;
  parameters: Record<string, string | number | boolean>;
  projectName: string;
  approvalHash?: string;
}

export interface Diagnosis {
  rootCauseSummary: string;
  confidence: number;
  hypotheses: Hypothesis[];
  suggestedRemediations: Remediation[];
}

// ─── Alerts ──────────────────────────────────────────────────

export interface AlertEvent {
  id: string;
  projectName: string;
  rule: string;
  metric: string;
  severity: "info" | "warning" | "critical";
  message: string;
  value: number;
  threshold: number;
  at: string;
}

// ─── HITL Action Proposals ───────────────────────────────────

export interface ActionProposal {
  proposalId: string;
  actionType: string;
  projectName: string;
  title: string;
  description: string;
  riskLevel: RiskLevel;
  parameters: Record<string, string | number | boolean>;
  approvalHash: string;
  expiresAt: number;
}

// ─── Chat protocol (client ↔ server SSE) ────────────────────

export type AgentSseEvent =
  | { type: "status"; stage: string; label: string }
  | { type: "tool"; tool: string; label: string; result: unknown }
  | { type: "delta"; text: string }
  | { type: "proposal"; proposal: ActionProposal; diagnosis?: Diagnosis }
  | { type: "done"; messageId: string }
  | { type: "error"; message: string };

export interface ChatHistoryItem {
  role: "user" | "assistant";
  content: string;
  payload?: unknown;
  pending?: boolean;
}
