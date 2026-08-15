# PR_Agent

PR_Agent is a zero-trust pull-request reviewer and guarded local Coding Agent.

It helps a developer move from a requested change to reviewed evidence:

```text
Coding request -> proposed diffs -> human-approved local commit -> GitHub pull request
GitHub webhook -> evidence collection -> human review decision
```

The system is intentionally human-in-the-loop. It can draft code, collect evidence, create
an approved local commit, and optionally push a branch, but it does not silently modify or
merge a repository.

## Features

### Pull-request review

- Receives signed GitHub `pull_request` webhooks.
- Runs five independent review agents:
  - Strategic alignment
  - Scientific reproduction
  - Security and quality
  - Adversarial hardening
  - Behavioral compatibility
- Stores review evidence, findings, scores, and a final advisory decision.
- Compares configured test commands on the base and pull-request commits.
- Detects common test weakening, such as deleted or skipped tests.
- Requires an explicit human approval or rejection in the dashboard.
- Can optionally post an advisory evidence summary back to GitHub.

### Guarded Coding Agent

- Accepts a plain-English request for an existing local Git repository.
- Supports Gemini, OpenAI, Grok, Ollama, or deterministic analysis.
- Produces file-by-file unified diffs before changing any source file.
- Restricts edits to tracked, allow-listed source files inside configured folders.
- Requires a clean working tree and explicit file selection before committing.
- Creates a separate `pr-agent/coding-...` branch for every approved change.
- Pushes only when explicitly enabled in configuration and selected in the UI.

## Architecture

```text
Next.js dashboard
       |
       v
FastAPI API + Server-Sent Events
       |
       +--> LangGraph review orchestration
       |      +--> five evidence agents
       |      +--> SQLite or PostgreSQL
       |      +--> local or S3-compatible evidence storage
       |
       +--> Guarded Coding Agent
              +--> Gemini / OpenAI / Grok / Ollama
              +--> local Git branch and commit after approval
```

## Tech stack

- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, LangGraph
- Frontend: Next.js, React, TypeScript
- Review execution: restricted Docker sandbox (optional for local review-only use)
- Storage: SQLite for local development; PostgreSQL and S3-compatible storage supported
- Queue: in-memory locally; Kafka/Redpanda supported for workers
- AI providers: Gemini, OpenAI, Grok, Ollama, or deterministic mode

## Quick start

### Prerequisites

- Python 3.12+
- Node.js 22+
- Git
- Docker Desktop only when running sandboxed repository tests

### 1. Start the backend

```powershell
cd C:\path\to\PR-Agent
Copy-Item .env.example .env
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m PR_Agent.cli serve --reload
```

The API is available at `http://127.0.0.1:8000`.

### 2. Start the dashboard

```powershell
cd C:\path\to\PR-Agent\web
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

### 3. Run a demo

Use **Run demo** in the dashboard. Demo reviews do not require GitHub, Docker, or an API key.

## Configure an AI provider

The default `deterministic` provider performs rule-based review analysis but does not generate
Coding Agent drafts. To use the Coding Agent, configure an LLM in your private `.env` file.

### Gemini

```env
PR_AGENT_LLM_PROVIDER=gemini
PR_AGENT_GEMINI_API_KEY=your_private_key
PR_AGENT_GEMINI_MODEL=gemini-3.5-flash
PR_AGENT_GEMINI_URL=https://generativelanguage.googleapis.com/v1beta/models
```

Restart the backend after changing `.env`. Never commit `.env` or share API keys.

### Other providers

`.env.example` includes settings for Ollama, OpenAI, and Grok. Select the provider with
`PR_AGENT_LLM_PROVIDER` and set the matching local API key or Ollama server configuration.

## Use the Coding Agent

1. Clone or choose a clean local Git repository.
2. Enable the feature in `.env`:

   ```env
   PR_AGENT_CODING_AGENT_ENABLED=true
   PR_AGENT_CODING_ALLOWED_ROOTS=C:\Users\your-name\Documents\projects
   PR_AGENT_CODING_AUTO_PUSH=false
   ```

3. Restart the backend and open **Coding agent** in the dashboard.
4. Enter the repository's absolute local path and a request.
5. Select **Draft changes** and inspect every proposed diff.
6. Select only the files you approve and choose **Commit selected files locally**.

The agent creates a local branch and commit only after your approval. To allow the optional
**Commit and push** action, set `PR_AGENT_CODING_AUTO_PUSH=true`, restart the backend, and
ensure the repository has an authenticated `origin` remote.

## Review a real GitHub pull request

1. Run the backend locally.
2. Create a public HTTPS tunnel to port `8000` during local development, for example with ngrok.
3. In GitHub repository settings, add a webhook:

   ```text
   https://YOUR-PUBLIC-URL/api/v1/webhooks/github
   ```

4. Select `application/json` and the **Pull requests** event.
5. Set `PR_AGENT_GITHUB_WEBHOOK_SECRET` to the exact same secret used in GitHub.
6. Open or update a pull request, then inspect it in **Review queue**.

For a permanent multi-user installation, deploy the API to a public host rather than using a
local tunnel, and use a GitHub App instead of a personal token.

## Configure repository tests

Commit `.pr-agent.toml` to the repository's base branch. PR_Agent uses that trusted version
for both base and pull-request test runs.

```toml
[test]
commands = ["g++ -std=c++17 -Wall -Wextra hello.cpp -o /run/program", "/run/program"]

[sandbox]
image = "gcc:14"
```

See [`examples/pr-agent.toml`](examples/pr-agent.toml) for more starting points.

## Safety model

- GitHub webhook signatures are verified when a webhook secret is configured.
- Untrusted PR test execution runs in a network-disabled, read-only Docker sandbox.
- The Coding Agent validates repository roots, paths, file extensions, and working-tree state.
- Drafts remain in memory until a human approves selected files.
- Remote push is off by default.
- LLM output is parsed as data and never directly controls shell commands or orchestration.
- Secrets belong in local environment variables or a secret manager, never Git.

## Verification

Run backend checks:

```powershell
python -m ruff check PR_Agent tests
python -m pytest -q
```

Run the frontend production build:

```powershell
cd web
npm run build
```

## Project structure

```text
PR_Agent/              FastAPI application, agents, sandbox, Coding Agent
web/                   Next.js dashboard
tests/                 Backend test suite
migrations/            Alembic database migrations
examples/              Repository test configuration examples
infra/                 Docker Compose, Helm, and Terraform deployment assets
```

## Status

PR_Agent is a working local-first project and learning prototype. Before using it for
organization-wide production review, deploy it to a persistent host, use a GitHub App,
configure managed secrets, and use a hardened isolated runner for untrusted code.
