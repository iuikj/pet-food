"""Application version - single source of truth.

Version is read from pyproject.toml at import time.
CI updates pyproject.toml when a git tag (v*.*.*) is pushed.
"""

import tomllib
from pathlib import Path

_pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

try:
    with open(_pyproject_path, "rb") as f:
        _pyproject = tomllib.load(f)
    __version__ = _pyproject["project"]["version"]
except Exception:
    # Fallback if pyproject.toml is missing or malformed
    __version__ = "0.0.0-dev"


