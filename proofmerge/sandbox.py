import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path

from proofmerge.config import Settings


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

    async def run(self, workspace: Path, command: list[str]) -> ExecutionResult:
        if self.settings.sandbox_backend == "disabled":
            raise SandboxUnavailable("Sandbox execution is disabled")
        if self.settings.sandbox_backend == "local":
            return await self._run_local(workspace, command)
        return await self._run_docker(workspace, command)

    async def _run_docker(self, workspace: Path, command: list[str]) -> ExecutionResult:
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
            "-v",
            f"{workspace.resolve()}:/workspace:ro",
            "-w",
            "/workspace",
            self.settings.sandbox_image,
            *command,
        ]
        return await self._spawn(docker_command, Path.cwd())

    async def _run_local(self, workspace: Path, command: list[str]) -> ExecutionResult:
        if not self.settings.allow_local_execution:
            raise SandboxUnavailable(
                "Local execution requires PROOFMERGE_ALLOW_LOCAL_EXECUTION=true"
            )
        if not command or any(any(token in part for token in ";|&><`$") for part in command):
            raise ValueError("Unsafe local command")
        return await self._spawn(command, workspace)

    async def _spawn(self, command: list[str], cwd: Path) -> ExecutionResult:
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

    @staticmethod
    def display_command(command: list[str]) -> str:
        return shlex.join(command)
