import os
from pathlib import Path

os.environ["PROOFMERGE_ENVIRONMENT"] = "test"
os.environ["PROOFMERGE_DATABASE_URL"] = "sqlite+aiosqlite:///./proofmerge-test.db"
os.environ["PROOFMERGE_LLM_PROVIDER"] = "deterministic"
os.environ["PROOFMERGE_QUEUE_BACKEND"] = "memory"


def pytest_sessionstart(session):
    del session
    Path("proofmerge-test.db").unlink(missing_ok=True)


def pytest_sessionfinish(session, exitstatus):
    del session, exitstatus
    try:
        Path("proofmerge-test.db").unlink(missing_ok=True)
    except PermissionError:
        # Windows can briefly retain SQLite handles while async cleanup completes.
        pass
