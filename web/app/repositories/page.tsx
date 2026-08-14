"use client";

import Link from "next/link";
import { ArrowUpRight, FolderGit2, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { Review } from "@/lib/types";

export default function RepositoriesPage() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api.listReviews()
      .then((data) => setReviews(data.items))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load repositories"))
      .finally(() => setLoading(false));
  }, []);

  const repositories = useMemo(() => {
    const grouped = new Map<string, Review[]>();
    for (const review of reviews) grouped.set(review.pull_request.repository, [...(grouped.get(review.pull_request.repository) ?? []), review]);
    return [...grouped.entries()].map(([name, items]) => ({ name, latest: items[0], count: items.length }));
  }, [reviews]);

  return <main className="utility-page"><header className="utility-header"><div><p className="eyebrow">Workspace</p><h1>Repositories</h1></div><nav className="utility-nav"><Link href="/">Review queue</Link><Link href="/coding">Coding agent</Link><Link href="/policies">Policies</Link></nav></header>
    {error && <p className="coding-error">{error}</p>}
    {loading && <p className="utility-empty"><LoaderCircle className="spin" /> Loading repositories…</p>}
    {!loading && !error && !reviews.length && <p className="utility-empty">No pull-request reviews have been received yet.</p>}
    <section className="repository-grid">{repositories.map(({ name, latest, count }) => <article className="repository-card" key={name}><FolderGit2 /><div><p className="eyebrow">{count} review{count === 1 ? "" : "s"}</p><h2>{name}</h2><p>Latest: PR #{latest.pull_request.number} · {latest.status.replaceAll("_", " ")}</p><Link href={`/?review=${latest.id}`}>Open latest review <ArrowUpRight /></Link></div></article>)}</section>
  </main>;
}
