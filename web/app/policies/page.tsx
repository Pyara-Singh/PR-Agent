"use client";

import Link from "next/link";
import { CheckCircle2, LoaderCircle, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { PolicyStatus } from "@/lib/types";

function State({ enabled }: { enabled: boolean }) {
  return enabled ? <span className="policy-state enabled"><CheckCircle2 /> Enabled</span> : <span className="policy-state"><XCircle /> Disabled</span>;
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<PolicyStatus | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void api.getPolicies().then(setPolicies).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load policies")); }, []);

  return <main className="utility-page"><header className="utility-header"><div><p className="eyebrow">System configuration</p><h1>Policies</h1></div><nav className="utility-nav"><Link href="/">Review queue</Link><Link href="/repositories">Repositories</Link><Link href="/coding">Coding agent</Link></nav></header>
    {error && <p className="coding-error">{error}</p>}
    {!policies && !error ? <p className="utility-empty"><LoaderCircle className="spin" /> Loading active policies…</p> : null}
    {policies && <section className="policy-grid"><article className="policy-card"><ShieldCheck /><h2>Review gate</h2><p>Human approval is always required before a review becomes approved.</p><State enabled={policies.review.human_approval_required} /><p>Webhook signature: <strong>{policies.review.webhook_signature_required ? "required" : "development mode"}</strong></p></article><article className="policy-card"><ShieldCheck /><h2>Sandbox</h2><p>Backend: <strong>{policies.execution.backend}</strong></p><p>{policies.execution.network_access}</p><p>Timeout: <strong>{policies.execution.timeout_seconds}s</strong></p><State enabled={!policies.execution.local_execution_enabled} /></article><article className="policy-card"><ShieldCheck /><h2>Coding agent</h2><p>Maximum proposed files: <strong>{policies.coding_agent.maximum_proposed_files}</strong></p><p>Clean Git repository required: <strong>yes</strong></p><State enabled={policies.coding_agent.enabled} /><p>Remote push: <strong>{policies.coding_agent.remote_push_enabled ? "allowed" : "disabled"}</strong></p></article></section>}
  </main>;
}
