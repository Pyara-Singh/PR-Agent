from PR_Agent.schemas import PullRequestCreate

DEMO_DATA = {
    "secure-fix": PullRequestCreate(
        repository="PR_Agent/demo",
        number=184,
        title="Fix duplicate settlement when webhook delivery is retried",
        author="maya-chen",
        description=(
            "Fixes the idempotency bug reported in #912. The same webhook may be delivered "
            "more than once, so settlement now uses the provider event ID as a unique key. "
            "Includes a regression test and preserves the existing API contract."
        ),
        base_sha="73be1a4",
        head_sha="e901d8c",
        base_ref="main",
        head_ref="demo/secure-fix",
        html_url="https://github.com/PR_Agent/demo/pull/184",
        diff=(
            "--- a/app/settlement.py\n+++ b/app/settlement.py\n"
            "@@ -20,4 +20,7 @@\n-def settle(payload):\n+def settle(payload):\n"
            "+    if ledger.has_event(payload.event_id):\n+        return ledger.receipt(payload.event_id)\n"
            "     return ledger.create(payload)\n"
            "+def test_duplicate_event_returns_original_receipt():\n+    assert settle(event) == settle(event)\n"
        ),
    ),
    "risky-change": PullRequestCreate(
        repository="PR_Agent/demo",
        number=185,
        title="Fix admin callback timeout by bypassing signature middleware",
        author="alex-rivera",
        description=(
            "Temporary workaround for callback timeouts. Disables verification on the admin "
            "callback until the upstream service is migrated."
        ),
        base_sha="73be1a4",
        head_sha="ffd220a",
        base_ref="main",
        head_ref="demo/risky-change",
        html_url="https://github.com/PR_Agent/demo/pull/185",
        diff=(
            "--- a/app/auth.py\n+++ b/app/auth.py\n@@ -40,4 +40,5 @@\n"
            "-    verify_signature(request)\n+    # temporary bypass\n+    verified = True\n"
        ),
    ),
    "incomplete-fix": PullRequestCreate(
        repository="PR_Agent/demo",
        number=186,
        title="Fix normalizer crash for missing customer names",
        author="sam-kim",
        description=(
            "Fixes a production bug where customer names can be null. Adds a regression test "
            "for null values while keeping the response schema unchanged."
        ),
        base_sha="73be1a4",
        head_sha="313ea2b",
        base_ref="main",
        head_ref="demo/incomplete-fix",
        html_url="https://github.com/PR_Agent/demo/pull/186",
        diff=(
            "--- a/app/normalize.py\n+++ b/app/normalize.py\n@@ -16,3 +16,4 @@\n"
            " def normalize(value):\n+    if value is None:\n+        return ''\n"
            "     return value.strip().lower()\n+def test_null_name():\n+    assert normalize(None) == ''\n"
        ),
    ),
}
