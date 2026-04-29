from importlib.metadata import PackageNotFoundError, version

from .sandbox import Sandbox
from .limits import Limits

try:
    __version__ = version("dokapy")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

__all__ = ["Sandbox", "Limits", "__version__"]
