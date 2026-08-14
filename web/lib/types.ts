export type ReviewStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "failed";

export type TaskStatus = "queued" | "running" | "passed" | "warning" | "failed" | "skipped";

export type Finding = {
  severity: "info" | "low" | "medium" | "high" | "critical";
  title: string;
  detail: string;
  file?: string | null;
  line?: number | null;
};

export type AgentTask = {
  id: string;
  agent_role: string;
  status: TaskStatus;
  title: string;
  summary: string;
  score: number | null;
  findings: Finding[];
  evidence: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
};

export type Review = {
  id: string;
  status: ReviewStatus;
  overall_decision: "pass" | "needs_work" | "blocked" | null;
  alignment_score: number | null;
  risk_score: number | null;
  summary: string;
  error: string;
  trace_id: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  pull_request: {
    id: string;
    repository: string;
    number: number;
    title: string;
    author: string;
    description: string;
    base_ref: string;
    head_ref: string;
    html_url: string;
  };
  tasks: AgentTask[];
  approval: {
    decision: string;
    reviewer: string;
    note: string;
    created_at: string;
  } | null;
};

export type ReviewList = { items: Review[]; total: number };
export type DemoScenario = "secure-fix" | "risky-change" | "incomplete-fix";

export type CodingProposal = { path: string; diff: string };

export type CodingJob = {
  id: string;
  prompt: string;
  repository_path: string;
  status: "queued" | "planning" | "drafting" | "awaiting_approval" | "rejected" | "committed" | "pushed" | "failed";
  plan: { path: string; instruction: string }[];
  proposals: CodingProposal[];
  events: string[];
  error: string;
  branch: string;
  commit: string;
  created_at: string;
  updated_at: string;
};
