from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of a command executed inside the sandbox."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0
