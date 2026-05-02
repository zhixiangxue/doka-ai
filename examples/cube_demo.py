"""
CubeSandbox runtime demo.

CubeSandbox is a self-hosted KVM MicroVM sandbox service compatible with the
E2B SDK. Each sandbox is a fully isolated VM (dedicated kernel, filesystem,
and network) that boots in under 60ms.

Project: https://github.com/tencentcloud/CubeSandbox


=== Prerequisites ===

1. A KVM-enabled x86_64 Linux environment (any of the following):
     - WSL 2 on Windows 11 22H2+ (nested virtualization must be enabled in BIOS)
     - A Linux physical machine
     - A Linux VM with nested virtualization enabled

2. Docker and QEMU installed and running in that Linux environment.


=== Step 1: Install CubeSandbox ===

Inside your Linux / WSL2 environment, run:

    git clone https://github.com/tencentcloud/CubeSandbox.git
    cd CubeSandbox/dev-env
    ./prepare_image.sh     # one-off: download and initialise the runtime image
    ./run_vm.sh            # boot the environment (keep this terminal open)

In a second terminal, log into the environment:

    cd CubeSandbox/dev-env && ./login.sh

Inside that shell, install the service:

    curl -sL https://github.com/tencentcloud/CubeSandbox/raw/master/deploy/one-click/online-install.sh | bash

    # China mainland mirror:
    # curl -sL https://cnb.cool/CubeSandbox/CubeSandbox/-/git/raw/master/deploy/one-click/online-install.sh | MIRROR=cn bash


=== Step 2: Create a Template ===

Inside the same shell, create a code-interpreter template:

    cubemastercli tpl create-from-image \
        --image ccr.ccs.tencentyun.com/ags-image/sandbox-code:latest \
        --writable-layer-size 1G \
        --expose-port 49999 \
        --expose-port 49983 \
        --probe 49999

    cubemastercli tpl watch --job-id <job_id>   # wait until status = READY

Note the template_id from the output. You will need it below.


=== Step 3: Configure Environment Variables ===

Export the following before running this script (or put them in a .env file):

    export CUBE_ENDPOINT="http://127.0.0.1:3000"
    export CUBE_TEMPLATE_ID="<your-template-id>"

    # If CubeSandbox's built-in mkcert certificate is used:
    # export SSL_CERT_FILE="/root/.local/share/mkcert/rootCA.pem"


=== Step 4: Install Python Dependencies and Run ===

    pip install 'dokapy[cube]'
    python examples/cube.py


=== Architecture (for reference) ===

    This script  (doka SDK)
         │
         │  REST API (port 3000)
         ▼
      CubeAPI
         │
         ▼
    CubeMaster ──► Cubelet ──► KVM MicroVM
                                    │
                              cube-agent (PID 1)
                                    │
                              Python / shell process
"""

import os
import sys

# ---------------------------------------------------------------------------
# Load configuration from environment variables.
# ---------------------------------------------------------------------------

CUBE_ENDPOINT   = os.environ.get("CUBE_ENDPOINT", "http://localhost:3000")
CUBE_TEMPLATE   = os.environ.get("CUBE_TEMPLATE_ID", "tpl-cce7c0bbf697454896fe8d52")
CUBE_SSL_CERT   = os.environ.get("SSL_CERT_FILE")   # None if not set

if not CUBE_TEMPLATE:
    print("ERROR: CUBE_TEMPLATE_ID is not set.")
    print("       Run `cubemastercli tpl list` to find your template ID,")
    print("       then: export CUBE_TEMPLATE_ID=<your-template-id>")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Import doka and run the demo.
# ---------------------------------------------------------------------------

from doka import Limits, Sandbox


def main() -> None:
    limits = Limits(
        cpu="1.0",
        memory="512m",
        timeout=60,
        network=True,
    )

    with Sandbox(
        runtime="cube",
        limits=limits,
        image=CUBE_TEMPLATE,
        connect={
            "endpoint": CUBE_ENDPOINT,
            "ssl_cert": CUBE_SSL_CERT,   # omit or set to None if not using mkcert
        },
    ) as sandbox:

        # ------------------------------------------------------------------
        # 1. Run a shell command
        # ------------------------------------------------------------------
        hello = sandbox.commands.run('echo "Hello from Doka + CubeSandbox!"')
        print("Command stdout:")
        print(hello.stdout.strip())

        # ------------------------------------------------------------------
        # 2. Write and execute a Python script inside the VM
        # ------------------------------------------------------------------
        sandbox.files.write("/tmp/agent.py", "print('Hello from an agent inside a KVM VM')\n")
        result = sandbox.commands.run("python /tmp/agent.py")
        print("\nAgent stdout:")
        print(result.stdout.strip())

        # ------------------------------------------------------------------
        # 3. Write a file and read it back
        # ------------------------------------------------------------------
        sandbox.files.write("/tmp/output.txt", "Generated inside the KVM sandbox\n")
        content = sandbox.files.read("/tmp/output.txt")
        print("\nFile content:")
        print(content.strip())

        # ------------------------------------------------------------------
        # 4. Background process with real-time streaming output
        # ------------------------------------------------------------------
        long_task_code = """
import time

for i in range(5):
    print(f'tick {i}', flush=True)
    time.sleep(1)

print('done', flush=True)
"""
        sandbox.files.write("/tmp/long_task.py", long_task_code)
        process = sandbox.commands.run("python -u /tmp/long_task.py", background=True)

        print("\nBackground stdout (streaming):")
        for chunk in process.stdout.stream():
            print(chunk, end="", flush=True)

        exit_code = process.wait()
        print(f"Background exit code: {exit_code}")


if __name__ == "__main__":
    main()
