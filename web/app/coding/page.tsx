"use client";

import Link from "next/link";
import { Check, Code2, GitCommitHorizontal, LoaderCircle, ShieldCheck, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { API_URL, api } from "@/lib/api";
import type { CodingJob } from "@/lib/types";

export default function CodingPage() {
  const [repositoryPath, setRepositoryPath] = useState("");
  const [prompt, setPrompt] = useState("");
  const [commitMessage, setCommitMessage] = useState("PR_Agent: approved coding change");
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [job, setJob] = useState<CodingJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
      const next = await api.decideCodingJob(job.id, selectedPaths, commitMessage);
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
      <section className="coding-notice"><ShieldCheck /><p>Nothing is written while drafting. Only files you select are committed locally after approval. Remote push is disabled by default.</p></section>
      <form className="coding-form" onSubmit={(event) => void start(event)}>
        <label>Local Git repository path<input value={repositoryPath} onChange={(event) => setRepositoryPath(event.target.value)} placeholder="C:\\Users\\you\\Documents\\project" required /></label>
        <label>What should change?<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Add input validation to the login form" required minLength={5} /></label>
        <button className="approve-button" disabled={busy} type="submit">{busy ? <LoaderCircle className="spin" /> : <Code2 />} Draft changes</button>
      </form>
      {error && <p className="coding-error"><X /> {error}</p>}
      {job && <section className="coding-job"><div className="coding-job-head"><div><p className="eyebrow">Job {job.id.slice(0, 8)}</p><h2>{job.status.replaceAll("_", " ")}</h2></div>{job.status === "planning" || job.status === "drafting" ? <LoaderCircle className="spin" /> : null}</div>
        <ol className="coding-events">{job.events.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ol>
        {job.proposals.map((proposal) => <article className="coding-proposal" key={proposal.path}><label className="proposal-select"><input type="checkbox" checked={selectedPaths.includes(proposal.path)} disabled={job.status !== "awaiting_approval"} onChange={() => toggle(proposal.path)} /> <strong>{proposal.path}</strong></label><pre>{proposal.diff}</pre></article>)}
        {job.status === "awaiting_approval" && <div className="coding-decision"><label>Commit message<input value={commitMessage} onChange={(event) => setCommitMessage(event.target.value)} required /></label><button className="approve-button" disabled={busy} onClick={() => void decide()} type="button">{busy ? <LoaderCircle className="spin" /> : <GitCommitHorizontal />} Commit selected files locally</button><button className="reject-button" disabled={busy} onClick={() => void rejectAll()} type="button"><X /> Reject all</button></div>}
        {job.status === "committed" || job.status === "pushed" ? <p className="coding-success"><Check /> Created commit <code>{job.commit.slice(0, 12)}</code> on <code>{job.branch}</code>.</p> : null}
      </section>}
    </main>
  );
}
