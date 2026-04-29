from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from .runtime.base import BaseRuntime


class ProcessStdout:
    """Streaming standard output of a background process."""

    def __init__(self, generator):
        self._generator = generator

    def stream(self) -> Iterator[str]:
        """Iterate over output lines in real time."""
        yield from self._generator


class Process:
    """Handle for a background process returned by commands.run(..., background=True)."""

    def __init__(self, runtime: "BaseRuntime", exec_id: str):
        self._runtime = runtime
        self._exec_id = exec_id
        self.stdout = ProcessStdout(self._runtime.stream_output(exec_id))

    def wait(self) -> int:
        """Block until the process finishes and return its exit code."""
        return self._runtime.wait_exec(self._exec_id)

    def kill(self) -> None:
        """Forcefully terminate the process."""
        self._runtime.kill_exec(self._exec_id)
