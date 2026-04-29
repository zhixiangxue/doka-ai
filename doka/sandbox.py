from typing import Optional

from .commands import CommandsClient
from .files import FilesClient
from .limits import Limits
from .runtime.base import BaseRuntime
from .runtime.docker import DockerRuntime
from .exceptions import SandboxAlreadyClosedError

# Runtime name -> implementation class registry.
# Adding gVisor or Kata only requires one new entry here.
_RUNTIME_REGISTRY: dict[str, type[BaseRuntime]] = {
    "docker": DockerRuntime,
}


class Sandbox:
    """
    Core sandbox class that provides an isolated command execution environment.

    Usage:
        with Sandbox() as sb:
            result = sb.commands.run('python agent.py')
            print(result.stdout)
    """

    def __init__(
        self,
        runtime: str = "docker",
        limits: Optional[Limits] = None,
        image: Optional[str] = None,
    ):
        """
        Args:
            runtime: Backend runtime to use. Options: "docker" | "gvisor" | "kata".
            limits:  Resource constraints. Defaults to Limits() with sensible defaults.
            image:   Container image to use. Defaults to the runtime's built-in default.
        """
        self._closed = False
        self._limits = limits or Limits()
        self._image = image
        self._runtime = self._build_runtime(runtime)

        self.commands = CommandsClient(self._runtime)
        self.files = FilesClient(self._runtime)

    def _build_runtime(self, name: str) -> BaseRuntime:
        cls = _RUNTIME_REGISTRY.get(name)
        if cls is None:
            raise ValueError(
                f"Unsupported runtime: '{name}'. "
                f"Available: {list(_RUNTIME_REGISTRY.keys())}"
            )
        return cls(limits=self._limits, image=self._image)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> "Sandbox":
        """Start the sandbox and return itself for fluent usage."""
        if self._closed:
            raise SandboxAlreadyClosedError("Cannot start a sandbox that has already been closed.")
        self._runtime.start()
        return self

    def close(self) -> None:
        """Destroy the sandbox and release all resources."""
        if self._closed:
            return
        self._runtime.stop()
        self._closed = True

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Sandbox":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __repr__(self) -> str:
        status = "closed" if self._closed else "running"
        return f"<Sandbox runtime={self._runtime.__class__.__name__} status={status}>"
