import type { DemoScenario, Review, ReviewList } from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listReviews: () => request<ReviewList>("/reviews"),
  createDemo: (scenario: DemoScenario) =>
    request<Review>("/reviews/demo", { method: "POST", body: JSON.stringify({ scenario }) }),
  decide: (reviewId: string, decision: "approve" | "reject", note = "") =>
    request<Review>(`/reviews/${reviewId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer: "dashboard-reviewer", note }),
    }),
  rerun: (reviewId: string) => request<Review>(`/reviews/${reviewId}/rerun`, { method: "POST" }),
};

