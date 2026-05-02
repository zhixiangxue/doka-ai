"""
CubeSandbox runtime demo.

CubeSandbox is a self-hosted KVM MicroVM sandbox service compatible with the
E2B SDK. Each sandbox is a fully isolated VM (dedicated kernel, filesystem,
and network) that boots in under 60ms.

Project: https://github.com/tencentcloud/CubeSandbox
"""

import os
import sys

# ---------------------------------------------------------------------------
# Load configuration from environment variables.
# ---------------------------------------------------------------------------

CUBE_TEMPLATE = os.environ.get("CUBE_TEMPLATE_ID", "")

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
