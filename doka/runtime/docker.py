import io
import tarfile
import time
import uuid
from typing import Iterator, Optional

import docker
import docker.errors

from ..limits import Limits
from ..result import CommandResult
from ..exceptions import RuntimeError as DokaRuntimeError
from .base import BaseRuntime

_DEFAULT_IMAGE = "python:3.11-slim"


class DockerRuntime(BaseRuntime):
    """
    Docker-based sandbox runtime (default v0.1 implementation).

    Manages the container lifecycle via the Docker Python SDK.
    Commands are executed through exec_run / exec_create.
    File I/O is handled via tar archives (Docker's native put_archive API).
    """

    def __init__(self, limits: Limits, image: Optional[str] = None):
        self._limits = limits
        self._image = image or _DEFAULT_IMAGE
        self._client = docker.from_env()
        self._container = None
        # Maps exec_id -> exec object for background process tracking
        self._execs: dict[str, object] = {}
        # Maps exec_id -> output stream returned by Docker exec_start
        self._exec_streams: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spin up a long-running sandbox container."""
        cpu_quota = int(float(self._limits.cpu) * 100_000)  # microseconds per 100ms
        self._container = self._client.containers.run(
            self._image,
            command="sleep infinity",   # keep the container alive; commands are injected via exec
            detach=True,
            cpu_quota=cpu_quota,
            cpu_period=100_000,
            mem_limit=self._limits.memory,
            network_disabled=not self._limits.network,
            read_only=self._limits.fs_readonly,
            name=f"doka-{uuid.uuid4().hex[:8]}",
        )

    def stop(self) -> None:
        """Force-remove the container."""
        if self._container is not None:
            try:
                self._container.remove(force=True)
            except docker.errors.NotFound:
                pass
            finally:
                self._container = None

    # ------------------------------------------------------------------
    # Blocking command execution
    # ------------------------------------------------------------------

    def exec(
        self,
        command: str,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> CommandResult:
        self._ensure_running()
        exit_code, output = self._container.exec_run(
            cmd=["sh", "-c", command],
            environment=env or {},
            workdir=workdir,
            demux=True,
        )
        stdout, stderr = output if output else (b"", b"")
        return CommandResult(
            stdout=(stdout or b"").decode("utf-8", errors="replace"),
            stderr=(stderr or b"").decode("utf-8", errors="replace"),
            exit_code=exit_code or 0,
        )

    # ------------------------------------------------------------------
    # Background command execution
    # ------------------------------------------------------------------

    def exec_background(
        self,
        command: str,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> str:
        self._ensure_running()
        exec_obj = self._client.api.exec_create(
            self._container.id,
            cmd=["sh", "-c", command],
            environment=env or {},
            workdir=workdir,
        )
        exec_id = exec_obj["Id"]
        stream = self._client.api.exec_start(exec_id, stream=True, demux=True)
        self._execs[exec_id] = exec_obj
        self._exec_streams[exec_id] = stream
        return exec_id

    def stream_output(self, exec_id: str) -> Iterator[str]:
        self._ensure_running()
        stream = self._exec_streams.get(exec_id)
        if stream is None:
            raise DokaRuntimeError(f"Unknown background exec id: {exec_id}")

        for chunk in stream:
            if isinstance(chunk, tuple):
                stdout, stderr = chunk
                for part in (stdout, stderr):
                    if part:
                        yield part.decode("utf-8", errors="replace")
            elif chunk:
                yield chunk.decode("utf-8", errors="replace")

    def wait_exec(self, exec_id: str) -> int:
        self._ensure_running()
        while True:
            result = self._client.api.exec_inspect(exec_id)
            exit_code = result.get("ExitCode")
            if exit_code is not None:
                return exit_code
            time.sleep(0.1)

    def kill_exec(self, exec_id: str) -> None:
        # Docker has no native per-exec kill; send SIGKILL to the process PID instead
        self._ensure_running()
        inspect = self._client.api.exec_inspect(exec_id)
        pid = inspect.get("Pid")
        if pid:
            self._container.exec_run(f"kill -9 {pid}")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def write_file(self, path: str, content: str) -> None:
        """Write a string to the given path inside the container via a tar archive."""
        self._ensure_running()
        data = content.encode("utf-8")
        filename = path.lstrip("/").split("/")[-1]
        dirpath = "/" + "/".join(path.lstrip("/").split("/")[:-1])

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        buf.seek(0)
        self._container.put_archive(dirpath or "/", buf)

    def read_file(self, path: str) -> str:
        """Read a file from the container by running cat inside the sandbox."""
        self._ensure_running()
        result = self.exec(f"cat {path}")
        return result.stdout

    def file_exists(self, path: str) -> bool:
        self._ensure_running()
        result = self.exec(f"test -e {path}")
        return result.exit_code == 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_running(self) -> None:
        if self._container is None:
            raise DokaRuntimeError(
                "Sandbox is not running. Use 'with Sandbox() as sb:' or call start() first."
            )
