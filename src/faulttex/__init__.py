from importlib.metadata import PackageNotFoundError, version

from .cli import app, main
from .core import AppliedChange, apply_change, inspect_mutation, load_mutation
from .models import MutationSpec
from .runner import run_mutation

try:
    __version__ = version("faulttex")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = (
    "MutationSpec",
    "AppliedChange",
    "__version__",
    "app",
    "apply_change",
    "inspect_mutation",
    "load_mutation",
    "main",
    "run_mutation",
)
