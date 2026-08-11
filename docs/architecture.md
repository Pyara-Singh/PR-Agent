# Architecture decisions

## Deployable boundaries

The API is the trusted control plane. It authenticates GitHub events, persists state, and
dispatches only opaque review identifiers. Workers load review context from PostgreSQL and
execute a LangGraph lifecycle. The web application reads evidence through the API and cannot
directly reach Kafka, object storage, sandboxes, or GitHub credentials.

Agent roles are Python components rather than separately deployed services. This keeps local
development understandable while worker replicas provide horizontal scale. Roles can later be
split by Kafka topic without changing API contracts or persisted task records.

## Trust zones

1. **Control plane:** API, worker, PostgreSQL, queue, and secret manager.
2. **Model plane:** bounded prompts containing explicitly delimited untrusted PR content.
3. **Execution plane:** disposable sandboxes with no control-plane credentials or internal
   network route.
4. **Human plane:** evidence dashboard and GitHub checks that make the final decision explicit.

## Evidence contract

Every agent returns a status, numeric score, structured findings, and raw evidence. Aggregation
is deterministic: critical findings block; failed empirical checks require work; all other
results still require human approval. Model prose can enrich a finding but cannot override this
policy.

## Scaling model

Kafka partitions distribute review IDs across worker replicas. Each review runs independent
agent tasks concurrently. PostgreSQL is authoritative for state; S3 contains larger immutable
reports; Qdrant contains project goals, ADRs, and past-review embeddings. OpenTelemetry trace IDs
match persisted review trace IDs so API, worker, model, and sandbox activity can be correlated.

