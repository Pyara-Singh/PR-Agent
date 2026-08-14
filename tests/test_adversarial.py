import pytest

from PR_Agent.agents.adversarial import AdversarialAgent
from PR_Agent.agents.base import ReviewContext
from PR_Agent.llm import DeterministicProvider
from PR_Agent.models import TaskStatus


@pytest.mark.asyncio
async def test_flags_deleted_or_disabled_tests() -> None:
    agent = AdversarialAgent(DeterministicProvider())
    context = ReviewContext(
        repository="owner/repo",
        number=1,
        title="Change",
        description="",
        author="owner",
        diff=(
            "--- a/tests/widget_test.py\n"
            "+++ /dev/null\n"
            "-def test_widget():\n"
            "-    assert widget()\n"
            "+describe.skip('widget', () => {})\n"
        ),
    )

    result = await agent.run(context)

    assert result.status == TaskStatus.failed
    assert result.evidence["removed_test_files"] == ["tests/widget_test.py"]
    assert result.evidence["disabled_test_signals"] == 1
