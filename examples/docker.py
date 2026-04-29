"""
Minimal Docker runtime demo.

Run from the project root after installing the package in editable mode:
    python -m pip install -e .
    python playground/docker_demo.py

Requires Docker Desktop to be running with Linux containers enabled.
"""

from pathlib import Path
import sys

from doka import Limits, Sandbox


def main() -> None:
    limits = Limits(
        cpu="1.0",
        memory="512m",
        timeout=30,
        network=True,
    )

    with Sandbox(limits=limits, image="python:3.11-slim") as sandbox:
        hello = sandbox.commands.run('echo "Hello from Doka Sandbox!"')
        print("Command stdout:")
        print(hello.stdout.strip())

        sandbox.files.write("/tmp/agent.py", "print('Hello from an agent script')\n")
        result = sandbox.commands.run("python /tmp/agent.py")
        print("Agent stdout:")
        print(result.stdout.strip())

        sandbox.files.write("/tmp/output.txt", "Generated inside sandbox\n")
        output = sandbox.files.read("/tmp/output.txt")
        print("File content:")
        print(output.strip())

        long_task_code = """
import time

for i in range(5):
    print(f'tick {i}', flush=True)
    time.sleep(1)

print('done', flush=True)
"""
        sandbox.files.write("/tmp/long_task.py", long_task_code)
        process = sandbox.commands.run("python -u /tmp/long_task.py", background=True)

        print("Background stdout:")
        for chunk in process.stdout.stream():
            print(chunk, end="")

        exit_code = process.wait()
        print(f"Background exit code: {exit_code}")


if __name__ == "__main__":
    main()
