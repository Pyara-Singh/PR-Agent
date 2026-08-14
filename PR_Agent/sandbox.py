import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PR_Agent.config import Settings


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxUnavailable(RuntimeError):
    pass


class SandboxRunner:
    """Runs untrusted code with network, privilege, and resource restrictions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self, workspace: Path, command: list[str], *, image: str | None = None
    ) -> ExecutionResult:
        if self.settings.sandbox_backend == "disabled":
            raise SandboxUnavailable("Sandbox execution is disabled")
        if self.settings.sandbox_backend == "local":
            return await self._run_local(workspace, command)
        return await self._run_docker(workspace, command, image=image)

    async def _run_docker(
        self, workspace: Path, command: list[str], *, image: str | None = None
    ) -> ExecutionResult:
        docker_command = [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=256",
            "--memory=1g",
            "--cpus=1.5",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=256m",
            "--tmpfs=/run:rw,exec,nosuid,size=256m",
            "-v",
            f"{workspace.resolve()}:/workspace:ro",
            "-w",
            "/workspace",
            image or self.settings.sandbox_image,
            *command,
        ]
        return await self._spawn(docker_command, Path.cwd())

    async def _run_local(self, workspace: Path, command: list[str]) -> ExecutionResult:
        if not self.settings.allow_local_execution:
            raise SandboxUnavailable(
                "Local execution requires PR_AGENT_ALLOW_LOCAL_EXECUTION=true"
            )
        if not command or any(any(token in part for token in ";|&><`$") for part in command):
            raise ValueError("Unsafe local command")
        return await self._spawn(command, workspace)

    async def _spawn(self, command: list[str], cwd: Path) -> ExecutionResult:
        if os.name == "nt":
            return await asyncio.to_thread(self._spawn_windows, command, cwd)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.settings.sandbox_timeout_seconds
            )
        except TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return ExecutionResult(
                -1, stdout.decode(errors="replace"), stderr.decode(errors="replace"), True
            )
        return ExecutionResult(
            process.returncode or 0,
            stdout.decode(errors="replace")[:1_000_000],
            stderr.decode(errors="replace")[:1_000_000],
        )

    def _spawn_windows(self, command: list[str], cwd: Path) -> ExecutionResult:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                timeout=self.settings.sandbox_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                -1,
                (exc.stdout or b"").decode(errors="replace")[:1_000_000],
                (exc.stderr or b"").decode(errors="replace")[:1_000_000],
                True,
            )
        return ExecutionResult(
            completed.returncode,
            completed.stdout.decode(errors="replace")[:1_000_000],
            completed.stderr.decode(errors="replace")[:1_000_000],
        )
