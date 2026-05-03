<div align="center">

<img src="https://raw.githubusercontent.com/zhixiangxue/doka-ai/main/docs/assets/logo.png" alt="doka" width="120">

[![PyPI version](https://badge.fury.io/py/dokapy.svg)](https://badge.fury.io/py/dokapy)
[![Python Version](https://img.shields.io/pypi/pyversions/dokapy)](https://pypi.org/project/dokapy/)
[![License](https://img.shields.io/github/license/zhixiangxue/doka-ai)](LICENSE)

**Self-hosted. Pluggable. Agent-ready.**

Secure, isolated sandboxes for AI Agents — without the cloud dependency.

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

with Sandbox(limits=Limits(cpu=1, memory="512m", network=False)) as sandbox:
    result = sandbox.commands.run("python agent.py")
```

### Pluggable runtime backends

The `runtime` parameter accepts a URI of the form `<driver>[:<variant>]`.

| URI | Status | Isolation | Requirements |
| --- | --- | --- | --- |
| `docker` | Available | Container (runc) | Docker Engine running locally |
| `docker:gvisor` | Available | Userspace kernel (gVisor Sentry) | Docker Engine + gVisor installed (see below) |
| `cube` | Available | KVM MicroVM | KVM-enabled x86_64 Linux + [CubeSandbox](https://github.com/TencentCloud/CubeSandbox) service running locally |
| `kata` | Available | KVM MicroVM | KVM-enabled x86_64 Linux + Kata Containers + nerdctl + CNI plugins (see below) |

#### OS support

| URI | Linux | macOS | Windows |
| --- | --- | --- | --- |
| `docker` | ✅ | ✅ | ✅ |
| `docker:gvisor` | ✅ | ❌ | ❌ |
| `cube` | ✅ (bare-metal / KVM-enabled VM only) | ❌ | ❌ |
| `kata` | ✅ (bare-metal / KVM-enabled VM only) | ❌ | ❌ |

#### Which runtime should I use?

| Situation | Recommended runtime |
| --- | --- |
| Just getting started, or developing on Windows / macOS | `docker` |
| Linux server, want stronger isolation without setting up a VM stack | `docker:gvisor` |
| Already running CubeSandbox in your infra (e.g. Tencent Cloud) | `cube` |
| Bare-metal Linux, want hardware VM isolation independent of Docker | `kata` |

As a rule of thumb: **start with `docker`, upgrade to `docker:gvisor` when you need stronger isolation, and reach for `kata` when you want full VM-level security on bare metal.**

The API stays the same regardless of which backend you use:

```python
# All four work identically from the caller's perspective
Sandbox(runtime="docker",        image="python:3.11-slim")
Sandbox(runtime="docker:gvisor", image="python:3.11-slim")
Sandbox(runtime="cube",          image="tpl-abc123")
Sandbox(runtime="kata",          image="python:3.11-slim")
```

#### Installing CubeSandbox

CubeSandbox runs each sandbox in a KVM MicroVM managed by a local service.
See the official repository for installation and setup instructions:
👉 **[TencentCloud/CubeSandbox](https://github.com/TencentCloud/CubeSandbox)**

#### Installing gVisor

gVisor intercepts all syscalls inside a userspace kernel (Sentry), so a
container exploit cannot reach the real host kernel directly.

```bash
# 1. Add the gVisor apt repository
curl -fsSL https://gvisor.dev/archive.key \
    | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] \
    https://storage.googleapis.com/gvisor/releases release main" \
    | sudo tee /etc/apt/sources.list.d/gvisor.list

# 2. Install and register as a Docker runtime
sudo apt-get update && sudo apt-get install -y runsc
sudo runsc install && sudo systemctl restart docker

# 3. Verify
runsc --version
docker info | grep runsc   # should show "runsc" under Runtimes
```

Once installed, switch any existing sandbox to gVisor with a one-word change:

```python
# Before
Sandbox(runtime="docker", ...)

# After — stronger isolation, identical API
Sandbox(runtime="docker:gvisor", ...)
```

#### Installing Kata Containers

Kata Containers runs each sandbox inside a KVM MicroVM with a dedicated
guest kernel (`6.x`), providing hardware-enforced VM isolation independent
of Docker.

```bash
# 1. Download and install Kata static bundle
#    https://github.com/kata-containers/kata-containers/releases
#    Choose: kata-static-<version>-amd64.tar.zst
sudo tar -C / -xf kata-static-*-amd64.tar.zst

# 2. Link the containerd shim into PATH
sudo ln -sf /opt/kata/bin/containerd-shim-kata-v2 /usr/local/bin/

# 3. Install nerdctl (Docker-compatible CLI for containerd)
#    https://github.com/containerd/nerdctl/releases  (non-full build, ~20 MB)
sudo tar -C /usr/local/bin -xzf nerdctl-*-linux-amd64.tar.gz nerdctl

# 4. Install CNI network plugins (Linux amd64 version)
#    https://github.com/containernetworking/plugins/releases
sudo mkdir -p /opt/cni/bin
sudo tar -C /opt/cni/bin -xzf cni-plugins-linux-amd64-*.tgz

# 5. Allow nerdctl to run without a password (nerdctl needs root for system containerd)
echo "$USER ALL=(root) NOPASSWD: /usr/local/bin/nerdctl" \
    | sudo tee /etc/sudoers.d/nerdctl

# 6. Verify
sudo nerdctl run --rm --runtime=io.containerd.kata.v2 python:3.11-slim uname -r
# Expected output: 6.x.x  (Kata guest kernel, not the host kernel)
```

---

## API Reference

### Sandbox(runtime="docker", limits=None, image=None)

Creates an isolated sandbox environment.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| runtime | str | `"docker"` | Runtime URI: `"docker"`, `"docker:gvisor"`, `"cube"`, or `"kata"`. |
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
| cpu | Union[int, float] | `1` | CPU quota. Supports fractional values, e.g. `0.5`, `1`, `2`. |
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
