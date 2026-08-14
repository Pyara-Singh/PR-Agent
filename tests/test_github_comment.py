from PR_Agent.github import format_review_comment


def test_evidence_comment_is_bounded_and_advisory() -> None:
    comment = format_review_comment(
        {
            "decision": "needs_work",
            "summary": "The change needs additional work.",
            "agents": [
                {
                    "title": "Security and quality",
                    "status": "failed",
                    "score": 40,
                    "findings": [{"severity": "high", "title": "Unsafe shell"}],
                }
            ],
        }
    )

    assert "`NEEDS WORK`" in comment
    assert "Unsafe shell" in comment
    assert "human reviewer" in comment
