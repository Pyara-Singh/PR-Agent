from PR_Agent.llm import parse_untrusted_json


def test_parses_json_wrapped_in_a_markdown_fence() -> None:
    assert parse_untrusted_json('```json\n{"answer": "ok"}\n```') == {"answer": "ok"}
