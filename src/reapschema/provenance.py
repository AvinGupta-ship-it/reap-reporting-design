"""Output provenance: checksums, configuration hashes and JSON sidecars."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

_TRACKED_PACKAGES = (
    "numpy",
    "pandas",
    "scipy",
    "statsmodels",
    "pvlib",
    "linopy",
    "highspy",
    "linkml",
    "pydantic",
    "matplotlib",
    "SALib",
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_hash(config: Any) -> str:
    """Hash of a JSON-serializable configuration (key order independent)."""
    return sha256_text(json.dumps(config, sort_keys=True, default=str))


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for name in _TRACKED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def write_sidecar(
    output: Path,
    *,
    config: Any,
    seed: int | None,
    inputs: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write ``<output>.meta.json`` recording how ``output`` was produced."""
    record: dict[str, Any] = {
        "output": output.name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "config_hash": config_hash(config),
        "seed": seed,
        "input_checksums": inputs or {},
        "package_versions": package_versions(),
    }
    if extra:
        record.update(extra)
    sidecar = output.with_name(output.name + ".meta.json")
    sidecar.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return sidecar
