"""Reproducibility manifest builder.

See ``plan/PLAN.md`` §T9 — captures source-file SHA-256 hashes, package
versions, git commit, run timestamp, random seeds, and the resolved
parameter set. Written to ``outputs/manifest.json`` by the pipeline.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

# Runtime packages whose versions are pinned in the manifest.
_TRACKED_PACKAGES: tuple[str, ...] = (
    "pwr-workforce-elasticity-modelling",
    "pandas",
    "numpy",
    "pyarrow",
    "openpyxl",
    "statsmodels",
    "linearmodels",
    "scikit-learn",
    "matplotlib",
)


def build_manifest(
    data_dir: str | Path,
    outputs_dir: str | Path,
    seed: int,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a serialisable manifest describing the current run.

    Parameters
    ----------
    data_dir : str or Path
        Directory whose contents are hashed for input traceability.
    outputs_dir : str or Path
        Destination directory; hashed *after* the rest of the pipeline
        has written its artefacts.
    seed : int
        Random seed passed to placebo and Random Forest stages.
    parameters : dict, optional
        Resolved parameter set (e.g. CLI overrides). Embedded verbatim
        in the manifest under ``parameters``.

    Returns
    -------
    dict
        Manifest payload, JSON-serialisable.
    """
    data_dir = Path(data_dir)
    outputs_dir = Path(outputs_dir)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "package_versions": _package_versions(),
        "seed": seed,
        "parameters": parameters or {},
        "input_files": _hash_tree(data_dir),
        "output_files": _hash_tree(outputs_dir),
    }


def write_manifest(
    path: str | Path,
    data_dir: str | Path,
    outputs_dir: str | Path,
    seed: int,
    parameters: dict[str, Any] | None = None,
) -> Path:
    """Build the manifest and write it as JSON.

    Returns
    -------
    pathlib.Path
        Path to the written manifest file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_manifest(data_dir, outputs_dir, seed, parameters)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_commit() -> str:
    """Return the current HEAD commit SHA, or ``"unknown"`` if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _package_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for pkg in _TRACKED_PACKAGES:
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = "not_installed"
    return out


def _hash_tree(directory: Path) -> dict[str, str]:
    """Return a {relative_path: sha256} map over all files in ``directory``."""
    out: dict[str, str] = {}
    if not directory.exists():
        return out
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = "unreadable"
        out[str(path.relative_to(directory)).replace("\\", "/")] = digest
    return out
