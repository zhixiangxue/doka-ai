import os
import queue
import socket
import threading
import uuid
from typing import Iterator, Optional
from urllib.parse import urlparse

from ..limits import Limits
from ..result import CommandResult
from ..exceptions import RuntimeError as DokaRuntimeError
from .base import BaseRuntime

# API port -> CubeSandbox HTTPS proxy port
# Bare-metal default : API 3000  -> CubeProxy HTTPS 443
# QEMU dev-env       : API 13000 -> CubeProxy HTTPS 11443 (hostfwd mapping)
_API_TO_PROXY_PORT: dict[int, int] = {
    3000: 443,
    13000: 11443,
}

# Candidate API ports to probe when auto-discovering a local CubeSandbox
_DISCOVERY_PORTS = (3000, 13000)

# Paths where mkcert installs its root CA by default
_MKCERT_CA_CANDIDATES = [
    "/tmp/cube-rootCA.pem",
    os.path.expanduser("~/.local/share/mkcert/rootCA.pem"),
    "/root/.local/share/mkcert/rootCA.pem",
]


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

    Example::

        with Sandbox(runtime="cube", image="tpl-abc123", limits=limits) as sb:
            result = sb.commands.run("echo hello")
            print(result.stdout)
    """

    def __init__(
        self,
        limits: Limits,
        image: Optional[str] = None,
        variant: Optional[str] = None,  # reserved for future cube variants
        **kwargs,
    ):
        try:
            import e2b_code_interpreter as _e2b
        except ImportError:
            raise ImportError(
                "CubeRuntime requires 'e2b-code-interpreter'. "
                "Install with: pip install 'dokapy[cube]'"
            ) from None

        self._e2b = _e2b
        self._limits = limits
        self._template_id = image or ""

        # Auto-discover the local CubeSandbox API endpoint
        self._endpoint = self._discover_endpoint()
        self._api_key = "dummy"

        # Derive the CubeProxy HTTPS port from the API port
        api_port = urlparse(self._endpoint).port or 3000
        self._proxy_port: int = _API_TO_PROXY_PORT.get(api_port, 443)

        # Auto-discover the mkcert root CA for SSL verification
        self._ssl_cert: Optional[str] = (
            os.environ.get("SSL_CERT_FILE")
            or self._find_mkcert_ca()
        )

        self._sandbox = None
        # exec_id -> (CommandHandle, Thread, output_queue, exit_code_holder)
        self._bg_processes: dict = {}

        # Apply SSL + DNS patches now so they're in place before any SDK call
        self._apply_local_patches()

    # ------------------------------------------------------------------
    # Local connection helpers (auto-discovery, SSL cert + DNS)
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_endpoint() -> str:
        """Probe well-known local ports to find a running CubeSandbox API."""
        for port in _DISCOVERY_PORTS:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return f"http://127.0.0.1:{port}"
        # Fall back to the standard bare-metal port
        return "http://localhost:3000"

    @staticmethod
    def _find_mkcert_ca() -> Optional[str]:
        """Return the first mkcert root-CA PEM found in well-known locations."""
        for path in _MKCERT_CA_CANDIDATES:
            if os.path.isfile(path):
                return path
        return None

    def _apply_local_patches(self) -> None:
        """Configure SSL trust and patch DNS so *.cube.app resolves locally."""
        # 1. Point Python's SSL stack at the mkcert root CA
        if self._ssl_cert and "SSL_CERT_FILE" not in os.environ:
            os.environ["SSL_CERT_FILE"] = self._ssl_cert

        # 2. Redirect *.cube.app -> 127.0.0.1:<proxy_port>
        #    run_code / commands connect to https://<port>-<id>.cube.app;
        #    we transparently route those to the local CubeProxy.
        proxy_port = self._proxy_port
        _orig = socket.getaddrinfo

        def _patched_getaddrinfo(host, port, *args, **kwargs):
            if isinstance(host, str) and host.endswith(".cube.app"):
                return _orig("127.0.0.1", proxy_port, *args, **kwargs)
            return _orig(host, port, *args, **kwargs)

        socket.getaddrinfo = _patched_getaddrinfo

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
