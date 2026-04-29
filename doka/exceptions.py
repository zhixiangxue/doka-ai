class DokaError(Exception):
    """Base exception for all doka errors."""


class SandboxNotStartedError(DokaError):
    """Raised when an operation is attempted on a sandbox that has not been started."""


class SandboxAlreadyClosedError(DokaError):
    """Raised when an operation is attempted on a sandbox that has already been closed."""


class CommandTimeoutError(DokaError):
    """Raised when a command execution exceeds the configured timeout."""


class RuntimeError(DokaError):
    """Raised when the underlying sandbox runtime encounters an error."""
