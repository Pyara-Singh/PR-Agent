"use client";

import Link from "next/link";
import { Check, Code2, GitCommitHorizontal, LoaderCircle, ShieldCheck, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { API_URL, api } from "@/lib/api";
import type { CodingJob, PolicyStatus } from "@/lib/types";

export default function CodingPage() {
  const [repositoryPath, setRepositoryPath] = useState("");
  const [prompt, setPrompt] = useState("");
  const [commitMessage, setCommitMessage] = useState("PR_Agent: approved coding change");
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [job, setJob] = useState<CodingJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [policies, setPolicies] = useState<PolicyStatus | null>(null);
  const [pushAfterCommit, setPushAfterCommit] = useState(false);
  const formReady = repositoryPath.trim().length > 0 && prompt.trim().length >= 5;
  const codingEnabled = policies?.coding_agent.enabled === true;
  const pushEnabled = policies?.coding_agent.remote_push_enabled === true;

  useEffect(() => {
    void api.getPolicies().then(setPolicies).catch(() => setError("Could not load Coding Agent settings."));
  }, []);

  useEffect(() => {
    if (!job || !["queued", "planning", "drafting"].includes(job.status)) return;
    const source = new EventSource(`${API_URL}/coding/jobs/${job.id}/events`);
    source.addEventListener("coding_job", (event) => {
      const next = JSON.parse((event as MessageEvent).data) as CodingJob;
      setJob(next);
      if (next.status === "awaiting_approval") setSelectedPaths(next.proposals.map((proposal) => proposal.path));
    });
    source.onerror = () => source.close();
    return () => source.close();
  }, [job?.id, job?.status]);

  async function start(event: FormEvent) {
    event.preventDefault();
    if (!formReady) {
      setError("Enter an absolute local Git repository path and a request of at least 5 characters.");
      return;
    }
    setBusy(true);
    try {
      const next = await api.createCodingJob(prompt, repositoryPath);
      setJob(next); setError(""); setSelectedPaths([]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create coding job");
    } finally { setBusy(false); }
  }

  async function decide() {
    if (!job) return;
    setBusy(true);
    try {
      const next = await api.decideCodingJob(job.id, selectedPaths, commitMessage, pushAfterCommit);
      setJob(next); setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not record decision");
    } finally { setBusy(false); }
  }

  async function rejectAll() {
    if (!job) return;
    setBusy(true);
    try {
      const next = await api.decideCodingJob(job.id, [], commitMessage);
      setJob(next); setError(""); setSelectedPaths([]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not reject drafts");
    } finally { setBusy(false); }
  }

  function toggle(path: string) {
    setSelectedPaths((current) => current.includes(path) ? current.filter((item) => item !== path) : [...current, path]);
  }

  return (
    <main className="coding-page">
      <header className="coding-header"><div><p className="eyebrow">Guarded Coding Agent</p><h1>Draft. Review. Commit.</h1></div><Link href="/" className="secondary-button">Back to reviews</Link></header>
      <section className="coding-notice"><ShieldCheck /><p>{codingEnabled ? "Nothing is written while drafting. Only files you select are committed locally after approval." : "Coding Agent is currently disabled. Enable it in your backend .env file before creating drafts."}</p></section>
      <form className="coding-form" noValidate onSubmit={(event) => void start(event)}>
        <label>Local Git repository path <span className="required-mark">Required</span><input value={repositoryPath} onChange={(event) => setRepositoryPath(event.target.value)} placeholder="C:\\Users\\you\\Documents\\project" aria-describedby="repository-help" /></label>
        <p className="field-help" id="repository-help">Use an absolute path to a clean Git repository inside your configured allowed folder.</p>
        <label>What should change? <span className="required-mark">Required</span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Example: Add input validation to the login form" aria-describedby="request-help" /></label>
        <p className="field-help" id="request-help">Describe the result you want. PR_Agent drafts files first; it does not write anything until you approve.</p>
        <button className="approve-button draft-button" disabled={busy || !formReady || !codingEnabled} type="submit">{busy ? <LoaderCircle className="spin" /> : <Code2 />} Draft changes</button>
        <p className={`draft-helper ${formReady && codingEnabled ? "ready" : ""}`}>{!policies ? "Checking Coding Agent settings…" : !codingEnabled ? "Enable PR_AGENT_CODING_AGENT_ENABLED=true, then restart the backend." : formReady ? "Ready to create read-only drafts." : "Complete both required fields to unlock drafting."}</p>
      </form>
      {error && <p className="coding-error"><X /> {error}</p>}
      {job && <section className="coding-job"><div className="coding-job-head"><div><p className="eyebrow">Job {job.id.slice(0, 8)}</p><h2>{job.status.replaceAll("_", " ")}</h2></div>{job.status === "planning" || job.status === "drafting" ? <LoaderCircle className="spin" /> : null}</div>
        <ol className="coding-events">{job.events.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ol>
        {job.proposals.map((proposal) => <article className="coding-proposal" key={proposal.path}><label className="proposal-select"><input type="checkbox" checked={selectedPaths.includes(proposal.path)} disabled={job.status !== "awaiting_approval"} onChange={() => toggle(proposal.path)} /> <strong>{proposal.path}</strong></label><pre>{proposal.diff}</pre></article>)}
        {job.status === "awaiting_approval" && <div className="coding-decision"><label>Commit message<input value={commitMessage} onChange={(event) => setCommitMessage(event.target.value)} required /></label><label className="push-choice"><input type="checkbox" checked={pushAfterCommit} disabled={!pushEnabled} onChange={(event) => setPushAfterCommit(event.target.checked)} /> Push branch to GitHub after committing <small>{pushEnabled ? "A remote named origin is required." : "Enable PR_AGENT_CODING_AUTO_PUSH=true to allow this."}</small></label><button className="approve-button" disabled={busy} onClick={() => void decide()} type="button">{busy ? <LoaderCircle className="spin" /> : <GitCommitHorizontal />} {pushAfterCommit ? "Commit and push" : "Commit selected files locally"}</button><button className="reject-button" disabled={busy} onClick={() => void rejectAll()} type="button"><X /> Reject all</button></div>}
        {job.status === "committed" || job.status === "pushed" ? <p className="coding-success"><Check /> Created commit <code>{job.commit.slice(0, 12)}</code> on <code>{job.branch}</code>.</p> : null}
      </section>}
    </main>
  );
}
