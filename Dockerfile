FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup --system proofmerge && adduser --system --ingroup proofmerge proofmerge
COPY pyproject.toml README.md ./
COPY proofmerge ./proofmerge
RUN pip install --no-cache-dir .
RUN mkdir -p /app/.proofmerge-artifacts /app/.proofmerge-workspaces && chown -R proofmerge:proofmerge /app

USER proofmerge
EXPOSE 8000
CMD ["uvicorn", "proofmerge.api:app", "--host", "0.0.0.0", "--port", "8000"]

