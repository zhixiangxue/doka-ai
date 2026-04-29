<div align="center">

<img src="https://raw.githubusercontent.com/zhixiangxue/doka-ai/main/docs/assets/logo.png" alt="doka" width="120">

[![PyPI version](https://badge.fury.io/py/dokapy.svg)](https://badge.fury.io/py/dokapy)
[![Python Version](https://img.shields.io/pypi/pyversions/dokapy)](https://pypi.org/project/dokapy/)
[![License](https://img.shields.io/github/license/zhixiangxue/doka-ai)](LICENSE)

**Self-hosted. Pluggable. Agent-ready.**

doka is a lightweight sandbox runtime for AI Agents — like E2B, but self-hosted and runtime-pluggable. It gives developers a simple programmable environment for running commands, moving files, and managing isolated execution without forcing them into a specific Agent framework.

Agents are hard to standardize. Commands are not. doka focuses on the universal primitive every Agent eventually needs: a safe place to run code.

</div>

---

## Core Features

### Minimalist API

No servers, no orchestration boilerplate, no Agent-specific adapter required:

```python
from doka import Sandbox

with Sandbox() as sandbox:
    result = sandbox.commands.run('echo "Hello from Doka Sandbox!"')
    print(result.stdout)
```

Write files, execute scripts, and read outputs from the sandbox:

```python
from doka import Sandbox

with Sandbox() as sandbox:
    sandbox.files.write("/tmp/agent.py", "print('Hello from an agent script')\n")

    result = sandbox.commands.run("python /tmp/agent.py")
    print(result.stdout)
```

### Command-first Agent Runtime

doka does not try to guess how your Agent should start.

LangChain, AutoGen, CrewAI, custom scripts, shell workflows, compiled binaries — every Agent has a different lifecycle. Instead of forcing an `Agent` abstraction, doka gives you an isolated machine-like environment and lets you run whatever command makes sense.

```python
with Sandbox() as sandbox:
    sandbox.files.write("/workspace/main.py", agent_code)
    result = sandbox.commands.run("python /workspace/main.py")
```

### File I/O Built In

Move data in and out of the sandbox without exposing Docker internals:

```python
with Sandbox() as sandbox:
    sandbox.files.write("/tmp/input.txt", "hello")
    sandbox.commands.run("cat /tmp/input.txt > /tmp/output.txt")
    output = sandbox.files.read("/tmp/output.txt")
```

### Resource Controls

Limit CPU, memory, network, and filesystem behavior with a small configuration object:

```python
from doka import Limits, Sandbox

limits = Limits(
    cpu="1.0",
    memory="512m",
    timeout=60,
    network=False,
    fs_readonly=False,
)

with Sandbox(limits=limits) as sandbox:
    result = sandbox.commands.run("python agent.py")
```

### Pluggable Runtime Backends

doka starts with Docker for local development and quick iteration, while keeping the runtime layer open for stronger isolation backends.

| Runtime | Status | Isolation | Best for |
| --- | --- | --- | --- |
| Docker | Available | Container isolation | Local development, trusted code |
| gVisor | Planned | Userspace kernel sandbox | Production Agent workloads |
| Kata Containers | Planned | Lightweight VM isolation | High-security workloads |

The public API stays the same while the backend changes:

```python
with Sandbox(runtime="docker") as sandbox:
    sandbox.commands.run("python agent.py")

# Future:
# with Sandbox(runtime="gvisor") as sandbox:
#     sandbox.commands.run("python agent.py")
```

---

## Quick Start

### Requirements

- Python 3.10+
- Docker Desktop or Docker Engine
- Linux containers enabled when running on Windows

### Installation

From PyPI after release:

```bash
pip install dokapy
```

For local development:

```bash
pip install -e .
```

### Run a Sandbox Command

```python
from doka import Sandbox

with Sandbox() as sandbox:
    result = sandbox.commands.run('echo "Hello from Doka!"')
    print(result.stdout)
```

### Run an Agent Script

```python
from doka import Sandbox

agent_code = """
print('Agent started')
print('Agent finished')
"""

with Sandbox() as sandbox:
    sandbox.files.write("/tmp/agent.py", agent_code)
    result = sandbox.commands.run("python /tmp/agent.py")
    print(result.stdout)
```

### Local Demo

A temporary Docker demo is available in `playground/docker_demo.py`.

```bash
python playground/docker_demo.py
```

---

## API Reference

### Sandbox(runtime="docker", limits=None, image=None)

Creates an isolated sandbox environment.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| runtime | str | `"docker"` | Runtime backend. Currently supports `"docker"`. |
| limits | Limits \| None | `None` | Resource limits for the sandbox. |
| image | str \| None | `None` | Container image. Defaults to `python:3.11-slim` for Docker. |

Recommended usage:

```python
with Sandbox() as sandbox:
    result = sandbox.commands.run("python --version")
```

Manual lifecycle:

```python
sandbox = Sandbox().start()
try:
    result = sandbox.commands.run("python --version")
finally:
    sandbox.close()
```

### sandbox.commands.run(command, background=False, env=None, workdir=None)

Executes a command inside the sandbox.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| command | str | required | Shell command to execute. |
| background | bool | `False` | Run as a background process when `True`. |
| env | dict \| None | `None` | Additional environment variables. |
| workdir | str \| None | `None` | Working directory inside the sandbox. |

Blocking mode returns `CommandResult`:

```python
result = sandbox.commands.run("python --version")
print(result.stdout)
print(result.stderr)
print(result.exit_code)
```

Background mode returns `Process`:

```python
process = sandbox.commands.run("python long_running_agent.py", background=True)

for chunk in process.stdout.stream():
    print(chunk)

exit_code = process.wait()
```

### sandbox.files

Simple file operations inside the sandbox.

| Method | Description |
| --- | --- |
| `write(path, content)` | Write text content to a file inside the sandbox. |
| `read(path)` | Read a file from inside the sandbox. |
| `exists(path)` | Return whether a path exists inside the sandbox. |

```python
sandbox.files.write("/tmp/input.txt", "hello")
exists = sandbox.files.exists("/tmp/input.txt")
content = sandbox.files.read("/tmp/input.txt")
```

### Limits

Resource constraints for the sandbox.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| cpu | str | `"1.0"` | CPU quota, e.g. `"0.5"`, `"1.0"`, `"2.0"`. |
| memory | str | `"512m"` | Memory limit, e.g. `"512m"`, `"1g"`. |
| timeout | int \| None | `None` | Command timeout in seconds. |
| network | bool | `True` | Whether network access is allowed. |
| fs_readonly | bool | `False` | Whether the root filesystem is read-only. |

---

## Why doka?

AI Agents need execution environments, not another framework-specific wrapper.

doka gives you the minimum useful abstraction:

```python
sandbox = Sandbox()
result = sandbox.commands.run("your command here")
```

Everything else — which Agent framework to use, how to start it, what files it needs, what it outputs — stays under developer control.

---

<div align="right"><img src="https://raw.githubusercontent.com/zhixiangxue/doka-ai/main/docs/assets/logo.png" alt="doka" width="120"></div>
