# Production checklist

- Replace the local GitHub token adapter with installation-token minting for the GitHub App.
- Require the webhook secret at startup in production.
- Deploy an isolated gVisor or Firecracker runner pool with deny-by-default egress.
- Store GitHub, LLM, database, and object-storage credentials in a managed secret store.
- Use PostgreSQL row-level retention policies and S3 object lock for regulated audit trails.
- Configure Redpanda replication, dead-letter topics, lag alerts, and idempotent consumers.
- Connect project ADR and roadmap ingestion to the Qdrant alignment namespace.
- Add organization SSO/RBAC to the reviewer dashboard.
- Enable Semgrep/CodeQL runners inside language-specific sandbox images.
- Export OpenTelemetry traces and configure cost, latency, failure-rate, and loop-budget alerts.
- Perform a threat-model review before enabling automatic GitHub writes.
- Keep auto-correction behind both repository policy and human approval.

