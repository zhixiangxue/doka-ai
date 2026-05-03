"""
gVisor Runtime Demo
===================

Demonstrates running code inside a Docker container backed by gVisor (runsc).

gVisor interposes a userspace kernel (Sentry) between the container process
and the host kernel, so even if a container exploit succeeds it only reaches
the Sentry — not the real host kernel.

Usage
-----
    python examples/gvisor_demo.py

Requirements
------------
- Docker Engine running
- gVisor (runsc) installed and registered as a Docker runtime:

    curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor \
        -o /usr/share/keyrings/gvisor-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] \
        https://storage.googleapis.com/gvisor/releases release main" \
        | sudo tee /etc/apt/sources.list.d/gvisor.list
    sudo apt-get update && sudo apt-get install -y runsc
    sudo runsc install && sudo systemctl restart docker
"""

from doka import Limits, Sandbox


def main():
    limits = Limits(cpu=1, memory="256m", network=False)

    print("=== doka gVisor Demo ===\n")

    # -----------------------------------------------------------------------
    # 1. Basic execution
    # -----------------------------------------------------------------------
    print("── 1. Basic execution ──────────────────────────────────────────")
    with Sandbox(runtime="docker:gvisor", limits=limits, image="python:3.11-slim") as sb:
        result = sb.commands.run("echo 'Hello from gVisor sandbox!'")
        print(result.stdout)

    # -----------------------------------------------------------------------
    # 2. Show isolation: uname reports gVisor's kernel, not the host kernel
    # -----------------------------------------------------------------------
    print("── 2. Kernel isolation (uname -r) ──────────────────────────────")
    with Sandbox(runtime="docker:gvisor", limits=limits, image="python:3.11-slim") as sb:
        result = sb.commands.run("uname -r")
        kernel = result.stdout.strip()
        print(f"  Container kernel : {kernel}")
        # gVisor reports something like "4.4.0" regardless of host kernel
        if "gvisor" in kernel.lower() or kernel.startswith("4.4"):
            print("  ✓ Running under gVisor (Sentry kernel)")
        else:
            print(f"  (host kernel reported — runsc may not be active)")

    # -----------------------------------------------------------------------
    # 3. Run Python code inside the sandbox
    # -----------------------------------------------------------------------
    print("\n── 3. Python inside gVisor ──────────────────────────────────────")
    with Sandbox(runtime="docker:gvisor", limits=limits, image="python:3.11-slim") as sb:
        code = "import sys; print(f'Python {sys.version} running in gVisor sandbox')"
        result = sb.commands.run(f'python -c "{code}"')
        print(" ", result.stdout.strip())

    # -----------------------------------------------------------------------
    # 4. Compare: plain Docker vs gVisor — both work the same way from doka
    # -----------------------------------------------------------------------
    print("\n── 4. API parity: docker vs docker:gvisor ───────────────────────")
    script = "print(sum(range(1_000_000)))"
    for rt in ("docker", "docker:gvisor"):
        with Sandbox(runtime=rt, limits=limits, image="python:3.11-slim") as sb:
            result = sb.commands.run(f'python -c "{script}"')
            print(f"  [{rt:15}] → {result.stdout.strip()}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
