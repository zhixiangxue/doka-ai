<div align="center">

<img src="https://raw.githubusercontent.com/zhixiangxue/doka-ai/main/docs/assets/logo.png" alt="doka" width="120">

[![PyPI version](https://badge.fury.io/py/dokapy.svg)](https://badge.fury.io/py/dokapy)
[![Python Version](https://img.shields.io/pypi/pyversions/dokapy)](https://pypi.org/project/dokapy/)
[![License](https://img.shields.io/github/license/zhixiangxue/doka-ai)](LICENSE)

**Self-hosted. Pluggable. Agent-ready.**

Secure, isolated sandboxes for AI Agents — without the cloud dependency.

```python
from doka import Sandbox

with Sandbox() as sandbox:
    result = sandbox.commands.run('echo "Hello from Doka!"')
    print(result.stdout)  # Hello from Doka!
```

</div>

---

## What is doka?

doka gives AI Agents a safe place to run code. It provides a programmable, isolated execution environment where developers can run commands, move files, and control resources — without being locked into any Agent framework or cloud provider.

Runs entirely on your own infrastructure. No API key. No usage limit. No data leaving your machine.

---

## Quick Start

### 1. Install

```bash
pip install dokapy
```

### 2. Start Docker

Make sure Docker Desktop (or Docker Engine) is running.

### 3. Run your first sandbox

```python
from doka import Sandbox

with Sandbox() as sandbox:
    result = sandbox.commands.run('echo "Hello from Doka!"')
    print(result.stdout)  # Hello from Doka!
```

### 4. Run an Agent script inside the sandbox

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

---

## Core Features

### Command-first — works with any Agent framework

doka does not try to standardize how Agents start. LangChain, AutoGen, CrewAI, custom scripts, compiled binaries — bring your own Agent, run it with a command.

```python
with Sandbox() as sandbox:
    sandbox.files.write("/workspace/main.py", agent_code)
    result = sandbox.commands.run("python /workspace/main.py")
    output = sandbox.files.read("/workspace/output.json")
```

### File I/O

```python
with Sandbox() as sandbox:
    sandbox.files.write("/tmp/input.txt", "hello")
    sandbox.commands.run("cat /tmp/input.txt > /tmp/output.txt")
    output = sandbox.files.read("/tmp/output.txt")
```

### Streaming output for long-running processes

```python
process = sandbox.commands.run("python -u agent.py", background=True)

for chunk in process.stdout.stream():
    print(chunk, end="")

exit_code = process.wait()
```

### Resource controls

```python
from doka import Limits, Sandbox

with Sandbox(limits=Limits(cpu="1.0", memory="512m", network=False)) as sandbox:
    result = sandbox.commands.run("python agent.py")
```

### Pluggable runtime backends

| Runtime | Status | Isolation |
| --- | --- | --- |
| Docker | Available | Container isolation |
| gVisor | Planned | Userspace kernel sandbox |
| Kata Containers | Planned | Lightweight VM isolation |

The API stays the same regardless of which backend you use.

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

doka is for teams and developers who want a self-hosted sandbox without the overhead of a cloud service:

- **No API key.** Runs on your machine or your server.
- **No usage limits.** Run as many sandboxes as your hardware allows.
- **No lock-in.** Swap the isolation backend as your security requirements grow.
- **No framework assumptions.** Works with any Agent, any stack, any language.


---

<div align="right"><img src="https://raw.githubusercontent.com/zhixiangxue/doka-ai/main/docs/assets/logo.png" alt="doka" width="120"></div>
