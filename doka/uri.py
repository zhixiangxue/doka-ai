"""
doka runtime URI parser.

Format:  <driver>[:<variant>]

Examples
--------
    "docker"           → driver="docker", variant=None
    "docker:gvisor"    → driver="docker", variant="gvisor"
    "cube"             → driver="cube",   variant=None

Rules
-----
- driver   : required, lowercase, alphanumeric + hyphens
- variant  : optional, same character set as driver
- At most one colon separator
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_SEGMENT_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")

# Known drivers and their allowed variants (None = no variant supported)
_KNOWN: dict[str, set[str] | None] = {
    "docker": {"gvisor"},
    "cube": None,
    "kata": None,
}


@dataclass(frozen=True)
class RuntimeURI:
    """Parsed representation of a runtime URI string."""

    driver: str
    variant: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.driver}:{self.variant}" if self.variant else self.driver


def parse(uri: str) -> RuntimeURI:
    """
    Parse a runtime URI string into a RuntimeURI.

    Raises
    ------
    ValueError
        If the URI is malformed or references an unknown driver / variant.
    """
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError(f"Runtime URI must be a non-empty string, got: {uri!r}")

    parts = uri.strip().split(":")
    if len(parts) > 2:
        raise ValueError(
            f"Invalid runtime URI {uri!r}: at most one ':' separator is allowed. "
            f"Expected format: '<driver>' or '<driver>:<variant>'"
        )

    driver = parts[0]
    variant = parts[1] if len(parts) == 2 else None

    if not _SEGMENT_RE.match(driver):
        raise ValueError(
            f"Invalid driver {driver!r} in runtime URI {uri!r}: "
            f"must be lowercase alphanumeric (hyphens allowed, must start with a letter or digit)"
        )

    if variant is not None and not _SEGMENT_RE.match(variant):
        raise ValueError(
            f"Invalid variant {variant!r} in runtime URI {uri!r}: "
            f"must be lowercase alphanumeric (hyphens allowed, must start with a letter or digit)"
        )

    if driver not in _KNOWN:
        known_drivers = list(_KNOWN.keys())
        raise ValueError(
            f"Unknown driver {driver!r} in runtime URI {uri!r}. "
            f"Available drivers: {known_drivers}"
        )

    allowed_variants = _KNOWN[driver]
    if variant is not None:
        if allowed_variants is None:
            raise ValueError(
                f"Driver {driver!r} does not support variants, "
                f"but got variant {variant!r} in runtime URI {uri!r}"
            )
        if variant not in allowed_variants:
            raise ValueError(
                f"Unknown variant {variant!r} for driver {driver!r} in runtime URI {uri!r}. "
                f"Available variants: {sorted(allowed_variants)}"
            )

    return RuntimeURI(driver=driver, variant=variant)
