from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Limits:
    """Resource constraints for the sandbox."""

    # CPU quota, e.g. "1.0" = 1 core, "0.5" = half a core
    cpu: str = "1.0"

    # Memory limit, e.g. "512m", "1g"
    memory: str = "512m"

    # Execution timeout in seconds; None means no limit
    timeout: Optional[int] = None

    # Whether to allow network access inside the sandbox
    network: bool = True

    # Whether to mount the root filesystem as read-only
    fs_readonly: bool = False
