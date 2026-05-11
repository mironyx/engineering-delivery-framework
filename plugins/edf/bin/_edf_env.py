"""Shared helpers for reading EDF environment variables.

EDF scripts honor OS environment variables (highest precedence), then fall back
to a `.env` file in the repo root. This module centralizes that lookup so all
scripts behave consistently.
"""

import os
import pathlib


def read_dotenv(root: pathlib.Path) -> dict[str, str]:
    """Read KEY=value pairs from .env in the repo root (if it exists)."""
    env_file = root / ".env"
    if not env_file.exists():
        return {}
    result: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip("\"'")
    return result


def resolve(key: str, root: pathlib.Path) -> str | None:
    """Return the value of `key` from OS env, falling back to .env in `root`."""
    value = os.environ.get(key)
    if value:
        return value
    return read_dotenv(root).get(key) or None


def prom_dir(root: pathlib.Path) -> pathlib.Path:
    """Resolve the Prometheus textfile directory.

    Precedence: $EDF_FEATURE_PROM_DIR → `.env` key EDF_FEATURE_PROM_DIR
    → `<root>/monitoring/textfile_collector`.
    """
    override = resolve("EDF_FEATURE_PROM_DIR", root)
    if override:
        return pathlib.Path(override)
    return root / "monitoring" / "textfile_collector"
