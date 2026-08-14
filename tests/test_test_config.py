from pathlib import Path

import pytest

from PR_Agent.test_config import TestConfigurationError as ConfigError
from PR_Agent.test_config import load_test_plan


def test_loads_repository_test_configuration(tmp_path: Path) -> None:
    (tmp_path / ".pr-agent.toml").write_text(
        '[test]\ncommands = ["npm ci", "npm test"]\n[sandbox]\nimage = "node:22-alpine"\n',
        encoding="utf-8",
    )

    plan = load_test_plan(tmp_path)

    assert plan is not None
    assert plan.commands == ["npm ci", "npm test"]
    assert plan.image == "node:22-alpine"


def test_rejects_invalid_repository_test_configuration(tmp_path: Path) -> None:
    (tmp_path / ".pr-agent.toml").write_text("[test]\ncommands = []\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="non-empty"):
        load_test_plan(tmp_path)
