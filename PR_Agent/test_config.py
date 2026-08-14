"""Safe, versioned repository test configuration."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


class TestConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class TestPlan:
    commands: list[str]
    image: str | None = None


def load_test_plan(workspace: Path) -> TestPlan | None:
    """Read only the base branch's .pr-agent.toml configuration."""
    config_file = workspace / ".pr-agent.toml"
    if not config_file.is_file():
        return None
    try:
        data = tomllib.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise TestConfigurationError(f"Invalid .pr-agent.toml: {exc}") from exc
    commands = data.get("test", {}).get("commands")
    if not isinstance(commands, list) or not commands or not all(
        isinstance(command, str) and command.strip() and len(command) <= 500
        for command in commands
    ):
        raise TestConfigurationError("test.commands must be a non-empty list of short commands")
    image = data.get("sandbox", {}).get("image")
    if image is not None and (
        not isinstance(image, str) or not re.fullmatch(r"[A-Za-z0-9._/-]+(?::[A-Za-z0-9._-]+)?", image)
    ):
        raise TestConfigurationError("sandbox.image is not a valid container image reference")
    return TestPlan(commands=commands, image=image)
