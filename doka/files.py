from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .runtime.base import BaseRuntime


class FilesClient:
    """File I/O interface for the sandbox, accessible via sandbox.files."""

    def __init__(self, runtime: "BaseRuntime"):
        self._runtime = runtime

    def write(self, path: str, content: str) -> None:
        """Write content to the specified path inside the sandbox."""
        self._runtime.write_file(path, content)

    def read(self, path: str) -> str:
        """Read and return the content of a file inside the sandbox."""
        return self._runtime.read_file(path)

    def exists(self, path: str) -> bool:
        """Return True if the given path exists inside the sandbox."""
        return self._runtime.file_exists(path)
