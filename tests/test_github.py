import hashlib
import hmac

import pytest

from PR_Agent.github import InvalidWebhookSignature, verify_github_signature


def test_webhook_signature_verification() -> None:
    body = b'{"action":"opened"}'
    secret = "test-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verify_github_signature(body, signature, secret)


def test_webhook_signature_rejects_tampering() -> None:
    with pytest.raises(InvalidWebhookSignature):
        verify_github_signature(b"tampered", "sha256=bad", "test-secret")
