"""
Kata Containers runtime for doka.

Uses nerdctl (containerd-native CLI) to run containers backed by Kata's
KVM MicroVM isolation — completely independent of Docker.

Call chain:
    doka Sandbox(runtime="kata")
        └── KataRuntime
             └── nerdctl run --runtime=io.containerd.kata.v2 ...
                  └── containerd → containerd-shim-kata-v2 → QEMU → KVM MicroVM

Requirements
------------
- Kata Containers installed  (https://github.com/kata-containers/kata-containers)
- nerdctl installed          (https://github.com/containerd/nerdctl)
- CNI plugins installed      (https://github.com/containernetworking/plugins)
- /opt/kata/bin/containerd-shim-kata-v2 symlinked into PATH
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import uuid
from typing import Iterator, Optional

from ..limits import Limits
from ..result import CommandResult
from ..exceptions import RuntimeError as DokaRuntimeError
from .base import BaseRuntime

_KATA_RUNTIME = "io.containerd.kata.v2"
_DEFAULT_IMAGE = "python:3.11-slim"
_NERDCTL = "nerdctl"

# nerdctl must run as root to reach system containerd.
# A passwordless sudo rule is configured for the nerdctl binary:
#   echo "$USER ALL=(root) NOPASSWD: /usr/local/bin/nerdctl" \
#       | sudo tee /etc/sudoers.d/nerdctl
_NERDCTL_CMD = ["sudo", "nerdctl"]


def _require_nerdctl() -> None:
    if shutil.which(_NERDCTL) is None:
        raise DokaRuntimeError(
            "KataRuntime requires 'nerdctl'. "
            "Install from https://github.com/containerd/nerdctl/releases"
        )


class KataRuntime(BaseRuntime):
    """
    Kata Containers runtime — KVM MicroVM isolation via nerdctl + containerd.

    Each sandbox maps to a long-running nerdctl container using the
    io.containerd.kata.v2 runtime shim.  Commands are executed via
    `nerdctl exec`.  File I/O is done by piping through `nerdctl exec sh`.
    """

    def __init__(
        self,
        limits: Limits,
        image: Optional[str] = None,
        variant: Optional[str] = None,   # reserved for future kata variants
        **kwargs,
    ):
        _require_nerdctl()
        self._limits = limits
        self._image = image or _DEFAULT_IMAGE
        self._name: Optional[str] = None
        # Maps exec_id -> subprocess.Popen for background processes
        self._bg_procs: dict[str, subprocess.Popen] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, *args: str, input: Optional[bytes] = None, check: bool = True) -> subprocess.CompletedProcess:
        """Run a nerdctl command, returning CompletedProcess."""
        cmd = [*_NERDCTL_CMD, *args]
        return subprocess.run(
            cmd,
            input=input,
            capture_output=True,
            check=check,
        )

    def _ensure_running(self) -> None:
        if self._name is None:
            raise DokaRuntimeError(
                "Sandbox is not running. Use 'with Sandbox() as sb:' or call start() first."
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spin up a long-running Kata MicroVM container."""
        self._name = f"doka-kata-{uuid.uuid4().hex[:8]}"

        cpu_quota = int(float(self._limits.cpu) * 100_000)

        cmd = [
            *_NERDCTL_CMD, "run",
            "--detach",
            f"--name={self._name}",
            f"--runtime={_KATA_RUNTIME}",
            f"--cpus={self._limits.cpu}",
            f"--memory={self._limits.memory}",
        ]
        if not self._limits.network:
            cmd.append("--network=none")
        if self._limits.fs_readonly:
            cmd.append("--read-only")

        cmd += [self._image, "sleep", "infinity"]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace")
            raise DokaRuntimeError(f"Failed to start Kata container: {stderr}") from e

    def stop(self) -> None:
        """Force-remove the Kata container."""
        if self._name is None:
            return
        subprocess.run(
            [*_NERDCTL_CMD, "rm", "--force", self._name],
            capture_output=True,
            check=False,
        )
        self._name = None

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
        cmd = [*_NERDCTL_CMD, "exec"]
        if workdir:
            cmd += ["--workdir", workdir]
        for k, v in (env or {}).items():
            cmd += ["--env", f"{k}={v}"]
        cmd += [self._name, "sh", "-c", command]

        result = subprocess.run(cmd, capture_output=True, check=False)
        return CommandResult(
            stdout=result.stdout.decode("utf-8", errors="replace"),
            stderr=result.stderr.decode("utf-8", errors="replace"),
            exit_code=result.returncode,
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
        cmd = [*_NERDCTL_CMD, "exec"]
        if workdir:
            cmd += ["--workdir", workdir]
        for k, v in (env or {}).items():
            cmd += ["--env", f"{k}={v}"]
        cmd += [self._name, "sh", "-c", command]

        exec_id = uuid.uuid4().hex
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._bg_procs[exec_id] = proc
        return exec_id

    def stream_output(self, exec_id: str) -> Iterator[str]:
        self._ensure_running()
        proc = self._bg_procs.get(exec_id)
        if proc is None:
            raise DokaRuntimeError(f"Unknown background exec id: {exec_id}")
        assert proc.stdout is not None
        for line in proc.stdout:
            yield line.decode("utf-8", errors="replace")

    def wait_exec(self, exec_id: str) -> int:
        self._ensure_running()
        proc = self._bg_procs.get(exec_id)
        if proc is None:
            raise DokaRuntimeError(f"Unknown background exec id: {exec_id}")
        proc.wait()
        return proc.returncode

    def kill_exec(self, exec_id: str) -> None:
        proc = self._bg_procs.get(exec_id)
        if proc is not None:
            proc.kill()

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def write_file(self, path: str, content: str) -> None:
        """Write a file into the Kata MicroVM via base64-encoded exec."""
        self._ensure_running()
        # nerdctl cp cannot penetrate the Kata VM boundary (separate guest FS).
        # Encode as base64 and pass as a command argument instead.
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        # Ensure parent directory exists, then decode+write atomically.
        dir_path = path.rsplit("/", 1)[0] if "/" in path else ""
        if dir_path:
            self.exec(f"mkdir -p {dir_path}")
        result = self.exec(f"sh -c 'echo {encoded} | base64 -d > {path}'")
        if result.exit_code != 0:
            raise DokaRuntimeError(
                f"write_file failed for '{path}': {result.stderr}"
            )

    def read_file(self, path: str) -> str:
        """Read a file from the container."""
        self._ensure_running()
        result = self.exec(f"cat {path}")
        return result.stdout

    def file_exists(self, path: str) -> bool:
        self._ensure_running()
        result = self.exec(f"test -e {path}")
        return result.exit_code == 0
