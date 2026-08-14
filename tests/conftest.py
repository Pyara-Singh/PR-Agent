import os
from pathlib import Path

os.environ["PR_AGENT_ENVIRONMENT"] = "test"
os.environ["PR_AGENT_DATABASE_URL"] = "sqlite+aiosqlite:///./PR_Agent-test.db"
os.environ["PR_AGENT_LLM_PROVIDER"] = "deterministic"
os.environ["PR_AGENT_QUEUE_BACKEND"] = "memory"


def pytest_sessionstart(session):
    del session
    Path("PR_Agent-test.db").unlink(missing_ok=True)


def pytest_sessionfinish(session, exitstatus):
    del session, exitstatus
    try:
        Path("PR_Agent-test.db").unlink(missing_ok=True)
    except PermissionError:
        # Windows can briefly retain SQLite handles while async cleanup completes.
        pass
