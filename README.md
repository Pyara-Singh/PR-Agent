# PR_Agent

PR_Agent is a zero-trust, evidence-driven pull request reviewer. It treats every pull
request as an unproven claim, gathers independent evidence, and requires a human decision
before approval.

The original learning prototype remains at the repository root. The production application
lives in `PR_Agent/`, the reviewer dashboard in `web/`, and deployment assets in `infra/`.

## What is implemented

- Signed GitHub pull-request webhook ingestion
- LangGraph review lifecycle with explicit, inspectable state
- Strategic-alignment, reproduction, security, adversarial, and behavioral agents
- Base-versus-head evidence records and test-weakening detection
- Deterministic local analysis with an optional Ollama provider
- PostgreSQL/SQLite persistence and Alembic migration support
- Kafka-compatible Redpanda queue with separately scalable workers
- Local/S3-compatible immutable evidence reports
- Restricted Docker sandbox adapter with no network, capabilities, or writable source mount
- Live Next.js review dashboard using Server-Sent Events
- Human approval/rejection gate and repeatable demo scenarios
- Docker Compose, Kubernetes Helm, Terraform, and GitHub Actions assets

## Quick start without Docker

Python 3.12+ and Node.js 22+ are required.

```powershell
Copy-Item .env.example .env
python -m venv .venv-production
.\.venv-production\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv-production\Scripts\python.exe -m PR_Agent.cli serve --reload
```

In a second terminal:

```powershell
Set-Location web
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000` and choose **Run demo**. The default configuration uses SQLite,
an in-process review dispatcher, local artifact files, and deterministic analyzers. GitHub,
Kafka, S3, Docker, and Ollama are optional in local development.

To index an ADR, roadmap, or project goal after setting `PR_AGENT_QDRANT_URL`:

```powershell
python -m PR_Agent.cli index .\docs\architecture.md --kind adr
```

## LLM providers

Deterministic rules are the default. To add model-assisted observations, set exactly one
provider in `.env` and provide its key locally. Never commit `.env` or API keys.

```env
# Choose one: deterministic, openai, gemini, grok, ollama
PR_AGENT_LLM_PROVIDER=gemini
PR_AGENT_GEMINI_API_KEY=replace-me
PR_AGENT_GEMINI_MODEL=gemini-2.5-flash
```

The other cloud options are:

```env
PR_AGENT_LLM_PROVIDER=openai
PR_AGENT_OPENAI_API_KEY=replace-me
PR_AGENT_OPENAI_MODEL=gpt-4o-mini

PR_AGENT_LLM_PROVIDER=grok
PR_AGENT_GROK_API_KEY=replace-me
PR_AGENT_GROK_MODEL=grok-4.5
```

The model is used only for structured observations by the alignment and security agents;
the final verdict and Docker reproduction evidence remain controlled by PR_Agent's own
rules. Restart the backend after changing `.env`.

## Full local infrastructure

With Docker available, run:

```bash
docker compose up --build
```

This starts the dashboard, API, review worker, PostgreSQL, Redpanda, Qdrant, and MinIO. The
dashboard is served at `http://localhost:3000`; API documentation is at
`http://localhost:8000/docs`.

## GitHub App setup

1. Create a GitHub App with pull-request read access, issue-comment write access, and contents
   read access. Grant contents write only if auto-correction is explicitly enabled.
2. Subscribe to pull-request events.
3. Set the webhook URL to `https://YOUR_API/api/v1/webhooks/github`.
4. Put the webhook secret and installation credential in your secret manager, then expose them
   as `PR_AGENT_GITHUB_WEBHOOK_SECRET` and `PR_AGENT_GITHUB_TOKEN`.
5. Set `PR_AGENT_QUEUE_BACKEND=kafka` when using external workers.

Webhook signatures are verified before payload parsing. PR descriptions and diffs are treated
as untrusted data and cannot directly control the review graph.

## Review lifecycle

```text
GitHub webhook
    │
    ▼
API gateway ──► durable review record ──► Redpanda
                                              │
                                              ▼
                                      LangGraph orchestrator
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                  reproduction          security           alignment
                         ▼                    ▼                    ▼
                  adversarial        behavioral diff       policy context
                         └────────────────────┼────────────────────┘
                                              ▼
                                      evidence report
                                              ▼
                                      mandatory human gate
```

The system decision is advisory. A `pass` still becomes `awaiting_approval`; it never silently
merges a pull request.

## Configuration modes

| Capability | Safe local default | Production setting |
|---|---|---|
| Database | SQLite | PostgreSQL |
| Queue | In-process background task | Redpanda/Kafka |
| Artifacts | Local directory | S3-compatible object storage |
| LLM | Deterministic analyzers | Ollama or a provider adapter |
| Execution | Docker adapter | gVisor/Firecracker-backed runner |
| Approval | Dashboard action | GitHub check/comment plus RBAC |

All settings are documented in `.env.example`. Configuration uses the `PR_AGENT_` prefix.

To publish the final advisory evidence report to the pull request, give the configured GitHub
token permission to create issue comments and set `PR_AGENT_GITHUB_COMMENTS_ENABLED=true`.
This is disabled by default; comments never approve, merge, or modify source code.

## Guarded Coding Agent

PR_Agent also includes an optional local Coding Agent at `http://localhost:3000/coding`.
It is intentionally separate from PR review. It uses the configured LLM to plan and draft changes
to existing tracked source files, then shows unified diffs over Server-Sent Events. Drafting never
writes to disk.

To enable it for repositories in one trusted folder, set these values in your local `.env` and
restart the backend:

```env
PR_AGENT_CODING_AGENT_ENABLED=true
PR_AGENT_CODING_ALLOWED_ROOTS=C:\Users\singh\Documents\pyara\projects
PR_AGENT_CODING_AUTO_PUSH=false
```

After you select proposed files and press **Commit selected files locally**, PR_Agent creates a
new `pr-agent/coding-...` branch and makes one local commit. It cannot push unless both the API
request asks for it and `PR_AGENT_CODING_AUTO_PUSH=true`. Do not grant it a broad folder such as
your user profile or drive root.

## Repository test configuration

For a real repository, commit this file to its **base branch**. PR_Agent reads that trusted
version and executes the same commands against the base commit and the pull-request commit.
It does not accept test commands from the untrusted PR branch.

```toml
# .pr-agent.toml
[test]
commands = ["npm ci", "npm test"]

[sandbox]
# Use an image that already contains the required runtime.
image = "node:22-alpine"
```

Use shell commands appropriate for the image. The configured container remains networkless,
read-only, capability-free, and time-limited; dependencies therefore need to be included in
the image or already available in the repository. See `examples/pr-agent.toml` for common
Python, Node, and C++ starting points.

## Security model

- Untrusted code does not receive GitHub, LLM, database, or storage credentials.
- Docker sandbox runs are networkless, read-only, non-root, capability-free, resource-capped,
  and time-limited.
- Host execution is disabled by default and requires an explicit opt-in.
- LLM output is parsed as bounded data and never selects graph nodes or shell commands.
- Webhooks use HMAC SHA-256 verification and constant-time signature comparison.
- Evidence reports are kept independently of model responses for auditability.
- Production credentials belong in Vault or a managed secret store, not `.env` files.

The local Docker adapter is intended for development. Executing arbitrary public PRs in
production requires a separate gVisor or Firecracker runner service and strict egress policy.

## Validation

```powershell
python -m pytest
python -m ruff check PR_Agent tests
Set-Location web
npm run build
```

The tests cover health, all three review outcomes, evidence generation, the human gate, and
webhook signature tampering.

## Upgrading a running local database

When you pull a newer version of PR_Agent, stop the backend once and run:

```powershell
python -m alembic upgrade head
```

The current migration adds GitHub delivery idempotency, preventing a retried webhook from
creating duplicate reviews.
