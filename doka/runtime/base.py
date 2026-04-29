from abc import ABC, abstractmethod
from typing import Iterator, Optional

from ..result import CommandResult


class BaseRuntime(ABC):
    """
    Abstract interface for sandbox runtimes.

    Every isolation backend (docker, gvisor, kata) must subclass this
    and implement all abstract methods.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def start(self) -> None:
        """Start the sandbox container / virtual machine."""

    @abstractmethod
    def stop(self) -> None:
        """Stop and destroy the sandbox, releasing all resources."""

    # ------------------------------------------------------------------
    # Blocking command execution
    # ------------------------------------------------------------------

    @abstractmethod
    def exec(
        self,
        command: str,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> CommandResult:
        """Execute a command and block until it completes, returning a CommandResult."""

    # ------------------------------------------------------------------
    # Background command execution
    # ------------------------------------------------------------------

    @abstractmethod
    def exec_background(
        self,
        command: str,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> str:
        """Start a command in the background and return an exec_id for tracking."""

    @abstractmethod
    def stream_output(self, exec_id: str) -> Iterator[str]:
        """Yield stdout lines from a background process in real time."""

    @abstractmethod
    def wait_exec(self, exec_id: str) -> int:
        """Wait for a background process to finish and return its exit code."""

    @abstractmethod
    def kill_exec(self, exec_id: str) -> None:
        """Forcefully terminate a background process."""

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        """Write content to the given path inside the sandbox."""

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read and return the content of a file inside the sandbox."""

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Return True if the given path exists inside the sandbox."""
