from fastapi.testclient import TestClient

from PR_Agent.api import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_secure_demo_produces_evidence_and_accepts_human_decision() -> None:
    with TestClient(app) as client:
        created = client.post("/api/v1/reviews/demo", json={"scenario": "secure-fix"})
        assert created.status_code == 202
        review_id = created.json()["id"]

        response = client.get(f"/api/v1/reviews/{review_id}")
        review = response.json()
        assert review["status"] == "awaiting_approval"
        assert review["overall_decision"] == "pass"
        assert len(review["tasks"]) == 5
        assert review["artifact_uri"]

        decision = client.post(
            f"/api/v1/reviews/{review_id}/decision",
            json={"decision": "approve", "reviewer": "test-reviewer", "note": "Evidence checked"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "approved"
        assert decision.json()["approval"]["reviewer"] == "test-reviewer"


def test_security_regression_is_blocked() -> None:
    with TestClient(app) as client:
        created = client.post("/api/v1/reviews/demo", json={"scenario": "risky-change"})
        review = client.get(f"/api/v1/reviews/{created.json()['id']}").json()
    assert review["overall_decision"] == "blocked"
    security = next(task for task in review["tasks"] if task["agent_role"] == "security")
    assert security["status"] == "failed"
    assert any(finding["severity"] == "critical" for finding in security["findings"])


def test_incomplete_fix_needs_work() -> None:
    with TestClient(app) as client:
        created = client.post("/api/v1/reviews/demo", json={"scenario": "incomplete-fix"})
        review = client.get(f"/api/v1/reviews/{created.json()['id']}").json()
    assert review["overall_decision"] == "needs_work"
    assert any(task["status"] == "failed" for task in review["tasks"])
