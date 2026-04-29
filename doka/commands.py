from typing import Optional, Union, TYPE_CHECKING

from .result import CommandResult
from .process import Process

if TYPE_CHECKING:
    from .runtime.base import BaseRuntime


class CommandsClient:
    """Command execution interface for the sandbox, accessible via sandbox.commands."""

    def __init__(self, runtime: "BaseRuntime"):
        self._runtime = runtime

    def run(
        self,
        command: str,
        background: bool = False,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> Union[CommandResult, Process]:
        """
        Execute a command inside the sandbox.

        Args:
            command:    Shell command to execute.
            background: If True, run non-blocking and return a Process handle.
                        If False, block until completion and return a CommandResult.
            env:        Additional environment variables to inject.
            workdir:    Working directory inside the sandbox (defaults to root).

        Returns:
            CommandResult in blocking mode, Process in background mode.
        """
        if background:
            exec_id = self._runtime.exec_background(command, env=env, workdir=workdir)
            return Process(self._runtime, exec_id)

        return self._runtime.exec(command, env=env, workdir=workdir)
