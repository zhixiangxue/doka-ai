import os
import queue
import threading
import uuid
from typing import Iterator, Optional

from ..limits import Limits
from ..result import CommandResult
from ..exceptions import RuntimeError as DokaRuntimeError
from .base import BaseRuntime


class CubeRuntime(BaseRuntime):
    """
    CubeSandbox-backed runtime for doka.

    Wraps the e2b-code-interpreter SDK to communicate with a self-hosted
    CubeSandbox deployment (https://github.com/tencentcloud/CubeSandbox).

    CubeSandbox provides true VM-level isolation (KVM MicroVM) with sub-60ms
    cold start and less than 5MB memory overhead per sandbox instance.
    It is fully compatible with the E2B SDK interface.

    Prerequisites:
        1. A running CubeSandbox deployment (requires KVM-enabled x86_64 Linux).
        2. A template created via ``cubemastercli tpl create-from-image``.
        3. Install the extra dependency: ``pip install 'dokapy[cube]'``

    Args:
        image:   CubeSandbox template ID (e.g. ``"tpl-abc123"``).  Obtained from
                 ``cubemastercli tpl list`` after creating a template.
        connect: Connection info dict.  Supported keys:

                   endpoint
                       CubeSandbox API URL.  Default: ``"http://localhost:3000"``.
                   api_key
                       API key string.  Any non-empty value works.  Default: ``"dummy"``.

    Example::
    
        with Sandbox(
            runtime="cube",
            image="tpl-abc123",
            connect={"endpoint": "http://127.0.0.1:3000"},
        ) as sb:
            result = sb.run("echo hello")
            print(result.stdout)
    """

    def __init__(
        self,
        limits: Limits,
        image: Optional[str] = None,
        connect: Optional[dict] = None,
        **kwargs,
    ):
        try:
            import e2b_code_interpreter as _e2b
        except ImportError:
            raise ImportError(
                "CubeRuntime requires 'e2b-code-interpreter'. "
                "Install with: pip install 'dokapy[cube]'"
            ) from None

        connect = connect or {}
        self._e2b = _e2b
        self._limits = limits
        self._template_id = image or ""
        self._endpoint = connect.get("endpoint", "http://localhost:3000")
        self._api_key = connect.get("api_key", "dummy")

        self._sandbox = None
        # exec_id -> (CommandHandle, Thread, output_queue, exit_code_holder)
        self._bg_processes: dict = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create and start a CubeSandbox KVM MicroVM instance."""
        os.environ["E2B_API_URL"] = self._endpoint
        os.environ["E2B_API_KEY"] = self._api_key

        self._sandbox = self._e2b.Sandbox.create(
            template=self._template_id,
            timeout=3600,
        )

    def stop(self) -> None:
        """Kill the sandbox and release all resources."""
        if self._sandbox is not None:
            try:
                self._sandbox.kill()
            except Exception:
                pass
            finally:
                self._sandbox = None

    # ------------------------------------------------------------------ commands

    def exec(
        self,
        command: str,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> CommandResult:
        self._ensure_running()
        result = self._sandbox.commands.run(
            command,
            envs=env or {},
            cwd=workdir,
            timeout=300,
        )
        return CommandResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=result.exit_code or 0,
        )

    # ------------------------------------------------------------------ background

    def exec_background(
        self,
        command: str,
        env: Optional[dict] = None,
        workdir: Optional[str] = None,
    ) -> str:
        self._ensure_running()
        exec_id = uuid.uuid4().hex
        output_queue: queue.Queue = queue.Queue()
        exit_holder: list = [None]

        # Start command in background; timeout=0 means no connection timeout.
        handle = self._sandbox.commands.run(
            command,
            background=True,
            envs=env or {},
            cwd=workdir,
            timeout=0,
        )

        def _wait():
            try:
                result = handle.wait(
                    on_stdout=lambda line: output_queue.put(line + "\n"),
                    on_stderr=lambda line: output_queue.put(line + "\n"),
                )
                exit_holder[0] = result.exit_code or 0
            except Exception as exc:
                output_queue.put(f"[error] {exc}\n")
                exit_holder[0] = -1
            finally:
                output_queue.put(None)  # end-of-stream sentinel

        thread = threading.Thread(target=_wait, daemon=True)
        self._bg_processes[exec_id] = (handle, thread, output_queue, exit_holder)
        thread.start()
        return exec_id

    def stream_output(self, exec_id: str) -> Iterator[str]:
        entry = self._bg_processes.get(exec_id)
        if entry is None:
            raise DokaRuntimeError(f"Unknown background exec id: {exec_id}")
        _, _, output_queue, _ = entry
        while True:
            chunk = output_queue.get()
            if chunk is None:  # sentinel: process has finished
                break
            yield chunk

    def wait_exec(self, exec_id: str) -> int:
        entry = self._bg_processes.get(exec_id)
        if entry is None:
            raise DokaRuntimeError(f"Unknown background exec id: {exec_id}")
        _, thread, _, exit_holder = entry
        thread.join()
        return exit_holder[0] if exit_holder[0] is not None else 0

    def kill_exec(self, exec_id: str) -> None:
        entry = self._bg_processes.get(exec_id)
        if entry is None:
            return
        handle, _, _, _ = entry
        try:
            handle.kill()
        except Exception:
            pass

    # ------------------------------------------------------------------ files

    def write_file(self, path: str, content: str) -> None:
        self._ensure_running()
        self._sandbox.files.write(path, content)

    def read_file(self, path: str) -> str:
        self._ensure_running()
        result = self._sandbox.files.read(path)
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return result

    def file_exists(self, path: str) -> bool:
        self._ensure_running()
        try:
            result = self._sandbox.commands.run(f"test -e {path}", timeout=5)
            return result.exit_code == 0
        except Exception:
            return False

    # ------------------------------------------------------------------ internal

    def _ensure_running(self) -> None:
        if self._sandbox is None:
            raise DokaRuntimeError(
                "Sandbox is not running. Use 'with Sandbox(...) as sb:' or call start() first."
            )
