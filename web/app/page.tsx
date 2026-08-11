"use client";

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  FlaskConical,
  GitPullRequest,
  LoaderCircle,
  Menu,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { API_URL, api } from "@/lib/api";
import type { AgentTask, DemoScenario, Review, TaskStatus } from "@/lib/types";

const scenarioLabels: Record<DemoScenario, string> = {
  "secure-fix": "Verified fix",
  "incomplete-fix": "Incomplete fix",
  "risky-change": "Security regression",
};

const roleIndex: Record<string, string> = {
  alignment: "01",
  reproduction: "02",
  security: "03",
  adversarial: "04",
  behavioral: "05",
};

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

function StatusIcon({ status }: { status: TaskStatus }) {
  if (status === "passed") return <CheckCircle2 aria-hidden />;
  if (status === "failed") return <XCircle aria-hidden />;
  if (status === "warning") return <AlertTriangle aria-hidden />;
  if (status === "running") return <LoaderCircle className="spin" aria-hidden />;
  return <Clock3 aria-hidden />;
}

function ScoreRing({ value, label, inverse = false }: { value: number | null; label: string; inverse?: boolean }) {
  const score = Math.round(value ?? 0);
  const display = value === null ? "—" : String(score);
  const progress = inverse ? 100 - score : score;
  return (
    <div className="score-wrap">
      <div className="score-ring" style={{ "--score": `${progress * 3.6}deg` } as React.CSSProperties}>
        <div>
          <strong>{display}</strong>
          <span>/100</span>
        </div>
      </div>
      <p>{label}</p>
    </div>
  );
}

function TaskCard({ task, active, onClick }: { task: AgentTask; active: boolean; onClick: () => void }) {
  return (
    <button className={`task-card ${active ? "active" : ""}`} onClick={onClick} type="button">
      <span className="task-number">{roleIndex[task.agent_role] ?? "·"}</span>
      <span className={`task-icon ${task.status}`}><StatusIcon status={task.status} /></span>
      <span className="task-copy">
        <strong>{task.title}</strong>
        <small>{task.summary}</small>
      </span>
      <span className="task-score">{task.score === null ? "—" : Math.round(task.score)}</span>
      <ChevronRight aria-hidden />
    </button>
  );
}

function EmptyState({ onRun }: { onRun: (scenario: DemoScenario) => void }) {
  return (
    <main className="empty-state">
      <div className="empty-mark"><FlaskConical aria-hidden /></div>
      <p className="eyebrow">Zero-trust review lab</p>
      <h1>Don&apos;t trust the fix.<br /><em>Prove it.</em></h1>
      <p className="empty-copy">
        Run a controlled pull request through reproduction, adversarial testing, security analysis,
        behavioral diffing, and human sign-off.
      </p>
      <button className="primary-action" onClick={() => onRun("secure-fix")} type="button">
        <Play aria-hidden /> Run the verified-fix demo
      </button>
    </main>
  );
}

export default function Dashboard() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  const selected = useMemo(
    () => reviews.find((review) => review.id === selectedId) ?? reviews[0] ?? null,
    [reviews, selectedId],
  );
  const selectedTask = useMemo(
    () => selected?.tasks.find((task) => task.id === selectedTaskId) ?? selected?.tasks[0] ?? null,
    [selected, selectedTaskId],
  );

  const loadReviews = useCallback(async () => {
    try {
      const data = await api.listReviews();
      setReviews(data.items);
      setSelectedId((current) => current ?? data.items[0]?.id ?? null);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not reach the API");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadReviews(); }, [loadReviews]);

  useEffect(() => {
    if (!selected || !["queued", "running"].includes(selected.status)) return;
    const source = new EventSource(`${API_URL}/reviews/${selected.id}/events`);
    source.addEventListener("review", (event) => {
      const next = JSON.parse((event as MessageEvent).data) as Review;
      setReviews((current) => [next, ...current.filter((item) => item.id !== next.id)]);
    });
    source.onerror = () => { source.close(); void loadReviews(); };
    return () => source.close();
  }, [selected?.id, selected?.status, loadReviews]);

  async function runDemo(scenario: DemoScenario) {
    setCreating(true);
    setScenarioOpen(false);
    try {
      const review = await api.createDemo(scenario);
      setReviews((current) => [review, ...current]);
      setSelectedId(review.id);
      setSelectedTaskId(null);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create the demo");
    } finally {
      setCreating(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!selected) return;
    try {
      const next = await api.decide(selected.id, decision);
      setReviews((current) => current.map((item) => item.id === next.id ? next : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Decision failed");
    }
  }

  async function rerun() {
    if (!selected) return;
    try {
      const next = await api.rerun(selected.id);
      setReviews((current) => current.map((item) => item.id === next.id ? next : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Rerun failed");
    }
  }

  const runningCount = reviews.filter((review) => ["queued", "running"].includes(review.status)).length;
  const blockedCount = reviews.filter((review) => review.overall_decision === "blocked").length;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "mobile-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><ShieldCheck aria-hidden /></div>
          <div><strong>ProofMerge</strong><span>Evidence console</span></div>
          <button className="mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X /></button>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <button className="nav-item active" type="button"><Activity aria-hidden /><span>Review queue</span><b>{reviews.length}</b></button>
          <button className="nav-item" type="button"><GitPullRequest aria-hidden /><span>Repositories</span></button>
          <button className="nav-item" type="button"><FlaskConical aria-hidden /><span>Test lab</span></button>
          <button className="nav-item" type="button"><ShieldCheck aria-hidden /><span>Policies</span></button>
        </nav>

        <div className="sidebar-section">
          <div className="section-label"><span>Recent reviews</span><Search aria-hidden /></div>
          <div className="review-list">
            {reviews.map((review) => (
              <button
                className={`review-item ${selected?.id === review.id ? "active" : ""}`}
                key={review.id}
                onClick={() => { setSelectedId(review.id); setSelectedTaskId(null); setMobileNav(false); }}
                type="button"
              >
                <span className={`review-dot ${review.status}`} />
                <span><strong>{review.pull_request.repository}</strong><small>PR #{review.pull_request.number}</small></span>
                <ChevronRight aria-hidden />
              </button>
            ))}
          </div>
        </div>

        <div className="system-card">
          <div><span className="pulse" /> System operational</div>
          <p>5 agents ready · sandbox policy enforced</p>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu /></button>
          <div className="breadcrumb"><span>Workspace</span><ChevronRight /><strong>Review queue</strong></div>
          <div className="top-stats">
            <span><CircleDot /> {runningCount} running</span>
            <span><AlertTriangle /> {blockedCount} blocked</span>
          </div>
          <div className="demo-menu-wrap">
            <button className="run-button" onClick={() => setScenarioOpen((open) => !open)} disabled={creating} type="button">
              {creating ? <LoaderCircle className="spin" /> : <Sparkles />} Run demo <ChevronRight />
            </button>
            {scenarioOpen && (
              <div className="scenario-menu">
                {(Object.keys(scenarioLabels) as DemoScenario[]).map((scenario) => (
                  <button key={scenario} onClick={() => void runDemo(scenario)} type="button">
                    <span>{scenarioLabels[scenario]}</span><small>{scenario.replaceAll("-", " ")}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        </header>

        {error && <div className="error-banner"><AlertTriangle /> {error}<button onClick={() => setError("")}><X /></button></div>}

        {loading ? (
          <div className="loading-screen"><LoaderCircle className="spin" /><span>Loading evidence console…</span></div>
        ) : !selected ? (
          <EmptyState onRun={(scenario) => void runDemo(scenario)} />
        ) : (
          <main className="review-workspace">
            <section className="review-hero">
              <div className="hero-main">
                <div className="hero-kicker">
                  <span className={`status-pill ${selected.status}`}>{statusLabel(selected.status)}</span>
                  <span>Trace {selected.trace_id.slice(0, 8)}</span>
                </div>
                <p className="repo-line"><GitPullRequest /> {selected.pull_request.repository} <span>/</span> PR #{selected.pull_request.number}</p>
                <h1>{selected.pull_request.title}</h1>
                <p className="hero-description">{selected.pull_request.description}</p>
                <div className="hero-meta">
                  <span className="avatar">{selected.pull_request.author.slice(0, 2).toUpperCase()}</span>
                  <span>Opened by <strong>{selected.pull_request.author}</strong></span>
                  <i />
                  <span>{selected.pull_request.head_ref} → {selected.pull_request.base_ref}</span>
                  {selected.pull_request.html_url && <a href={selected.pull_request.html_url} target="_blank" rel="noreferrer">Open PR <ArrowUpRight /></a>}
                </div>
              </div>
              <div className="hero-scores">
                <ScoreRing value={selected.alignment_score} label="Alignment" />
                <ScoreRing value={selected.risk_score} label="Risk" inverse />
                <div className={`verdict-card ${selected.overall_decision ?? "pending"}`}>
                  <span>System verdict</span>
                  <strong>{selected.overall_decision ? statusLabel(selected.overall_decision) : "Collecting"}</strong>
                  <p>{selected.summary}</p>
                </div>
              </div>
            </section>

            <section className="evidence-grid">
              <div className="agent-panel">
                <div className="panel-heading">
                  <div><p className="eyebrow">Independent analysis</p><h2>Evidence chain</h2></div>
                  <span className="agent-count"><Zap /> {selected.tasks.filter((task) => task.status === "passed").length}/{selected.tasks.length} passed</span>
                </div>
                <div className="task-list">
                  {selected.tasks.length === 0 ? (
                    <div className="agents-starting"><LoaderCircle className="spin" /> Agents are entering the review graph…</div>
                  ) : selected.tasks.map((task) => (
                    <TaskCard key={task.id} task={task} active={selectedTask?.id === task.id} onClick={() => setSelectedTaskId(task.id)} />
                  ))}
                </div>
              </div>

              <aside className="detail-panel">
                {selectedTask ? (
                  <>
                    <div className="detail-head">
                      <span className={`task-icon large ${selectedTask.status}`}><StatusIcon status={selectedTask.status} /></span>
                      <div><p className="eyebrow">Agent evidence</p><h2>{selectedTask.title}</h2></div>
                      <strong className="detail-score">{Math.round(selectedTask.score ?? 0)}</strong>
                    </div>
                    <p className="detail-summary">{selectedTask.summary}</p>
                    <div className="finding-list">
                      {selectedTask.findings.length ? selectedTask.findings.map((finding, index) => (
                        <article className={`finding ${finding.severity}`} key={`${finding.title}-${index}`}>
                          <div><span>{finding.severity}</span>{finding.file && <code>{finding.file}{finding.line ? `:${finding.line}` : ""}</code>}</div>
                          <h3>{finding.title}</h3><p>{finding.detail}</p>
                        </article>
                      )) : (
                        <div className="clean-evidence"><Check /><div><strong>No blocking finding</strong><p>The collected evidence is recorded in the immutable review trace.</p></div></div>
                      )}
                    </div>
                    <details className="raw-evidence">
                      <summary>Inspect raw evidence <ChevronRight /></summary>
                      <pre>{JSON.stringify(selectedTask.evidence, null, 2)}</pre>
                    </details>
                  </>
                ) : <p>Select an agent to inspect its evidence.</p>}
              </aside>
            </section>

            <section className="approval-bar">
              <div>
                <span className="approval-icon"><ShieldCheck /></span>
                <div><p className="eyebrow">Human-in-the-loop gate</p><h2>{selected.approval ? `Decision recorded: ${selected.approval.decision}` : "Evidence is ready for your judgment"}</h2></div>
              </div>
              <div className="approval-actions">
                {selected.status === "awaiting_approval" ? (
                  <><button className="reject-button" onClick={() => void decide("reject")}><X /> Request changes</button><button className="approve-button" onClick={() => void decide("approve")}><Check /> Approve change</button></>
                ) : selected.status === "running" || selected.status === "queued" ? (
                  <span className="collecting"><LoaderCircle className="spin" /> Collecting evidence</span>
                ) : (
                  <button className="secondary-button" onClick={() => void rerun()}><RefreshCw /> Run review again</button>
                )}
              </div>
            </section>
          </main>
        )}
      </section>
    </div>
  );
}

