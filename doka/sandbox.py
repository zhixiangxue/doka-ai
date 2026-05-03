from typing import Optional

from .commands import CommandsClient
from .files import FilesClient
from .limits import Limits
from .uri import parse as parse_runtime_uri
from .runtime.base import BaseRuntime
from .runtime.docker import DockerRuntime
from .runtime.cube import CubeRuntime
from .runtime.kata import KataRuntime
from .exceptions import SandboxAlreadyClosedError

# driver -> implementation class registry.
# Adding a new backend only requires one new entry here.
_RUNTIME_REGISTRY: dict[str, type[BaseRuntime]] = {
    "docker": DockerRuntime,
    "cube": CubeRuntime,
    "kata": KataRuntime,
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
            runtime: Backend runtime URI. Format: '<driver>[:<variant>]'.
                     Examples: "docker", "docker:gvisor", "cube".
            limits:  Resource constraints. Defaults to Limits() with sensible defaults.
            image:   What to run. For docker: an OCI image name (e.g. "python:3.11-slim").
                     For cube: a CubeSandbox template ID (e.g. "tpl-abc123").
        """
        self._closed = False
        self._limits = limits or Limits()
        self._image = image
        self._runtime = self._build_runtime(runtime)

        self.commands = CommandsClient(self._runtime)
        self.files = FilesClient(self._runtime)

    def _build_runtime(self, uri_str: str) -> BaseRuntime:
        uri = parse_runtime_uri(uri_str)
        cls = _RUNTIME_REGISTRY[uri.driver]  # parse() already validated the driver
        return cls(limits=self._limits, image=self._image, variant=uri.variant)

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
