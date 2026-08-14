FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup --system pr-agent && adduser --system --ingroup pr-agent pr-agent
COPY pyproject.toml README.md ./
COPY PR_Agent ./PR_Agent
RUN pip install --no-cache-dir .
RUN mkdir -p /app/.pr-agent-artifacts /app/.pr-agent-workspaces && chown -R pr-agent:pr-agent /app

USER pr-agent
EXPOSE 8000
CMD ["uvicorn", "PR_Agent.api:app", "--host", "0.0.0.0", "--port", "8000"]

