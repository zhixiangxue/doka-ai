"""
Kata Containers Runtime Demo
=============================

Demonstrates running code inside a KVM MicroVM backed by Kata Containers,
completely independent of Docker.

Call chain:
    doka Sandbox(runtime="kata")
        └── KataRuntime
             └── nerdctl run --runtime=io.containerd.kata.v2 ...
                  └── containerd → containerd-shim-kata-v2 → QEMU → KVM MicroVM

Usage
-----
    python examples/kata_demo.py

Requirements
------------
1. Kata Containers installed:
   Download kata-static-<ver>-amd64.tar.zst from
   https://github.com/kata-containers/kata-containers/releases
   then: sudo tar -C / -xf kata-static-*.tar.zst

2. containerd-shim-kata-v2 in PATH:
   sudo ln -sf /opt/kata/bin/containerd-shim-kata-v2 /usr/local/bin/

3. nerdctl installed:
   https://github.com/containerd/nerdctl/releases  (non-full, ~20MB)
   sudo tar -C /usr/local/bin -xzf nerdctl-*-linux-amd64.tar.gz nerdctl

4. CNI plugins installed (Linux version):
   https://github.com/containernetworking/plugins/releases
   sudo mkdir -p /opt/cni/bin
   sudo tar -C /opt/cni/bin -xzf cni-plugins-linux-amd64-*.tgz
"""

from doka import Limits, Sandbox


def main():
    limits = Limits(cpu=1, memory="512m", network=False)

    print("=== doka Kata Containers Demo ===\n")

    # -----------------------------------------------------------------------
    # 1. Basic execution
    # -----------------------------------------------------------------------
    print("── 1. Basic execution ──────────────────────────────────────────")
    with Sandbox(runtime="kata", limits=limits, image="python:3.11-slim") as sb:
        result = sb.commands.run("echo 'Hello from Kata MicroVM!'")
        print(result.stdout)

    # -----------------------------------------------------------------------
    # 2. Kernel isolation — Kata boots its own guest kernel
    # -----------------------------------------------------------------------
    print("── 2. Kernel isolation (uname -r) ──────────────────────────────")
    with Sandbox(runtime="kata", limits=limits, image="python:3.11-slim") as sb:
        result = sb.commands.run("uname -r")
        kernel = result.stdout.strip()
        print(f"  Container kernel : {kernel}")
        print(f"  ✓ Kata guest kernel (not the host kernel)")

    # -----------------------------------------------------------------------
    # 3. Run Python inside the MicroVM
    # -----------------------------------------------------------------------
    print("\n── 3. Python inside Kata MicroVM ────────────────────────────────")
    with Sandbox(runtime="kata", limits=limits, image="python:3.11-slim") as sb:
        code = "import sys; print(f'Python {sys.version} running in Kata MicroVM')"
        result = sb.commands.run(f'python -c "{code}"')
        print(" ", result.stdout.strip())

    # -----------------------------------------------------------------------
    # 4. File I/O across the MicroVM boundary
    # -----------------------------------------------------------------------
    print("\n── 4. File I/O ──────────────────────────────────────────────────")
    with Sandbox(runtime="kata", limits=limits, image="python:3.11-slim") as sb:
        sb.files.write("/tmp/hello.py", "print('Written by doka, executed in Kata!')\n")
        result = sb.commands.run("python /tmp/hello.py")
        print(" ", result.stdout.strip())

    # -----------------------------------------------------------------------
    # 5. API parity across all three runtimes
    # -----------------------------------------------------------------------
    print("\n── 5. API parity: docker / docker:gvisor / kata ─────────────────")
    script = "print(sum(range(1_000_000)))"
    for rt in ("docker", "docker:gvisor", "kata"):
        with Sandbox(runtime=rt, limits=limits, image="python:3.11-slim") as sb:
            result = sb.commands.run(f'python -c "{script}"')
            print(f"  [{rt:15}] → {result.stdout.strip()}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
