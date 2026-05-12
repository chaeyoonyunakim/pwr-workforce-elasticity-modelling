"""End-to-end orchestration: data → panel → features → models → report.

Entry point invoked by ``pwr-pipeline`` (see ``pyproject.toml``
``[project.scripts]``) and by ``python -m pwr_elasticity.pipeline``.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the pipeline entry point."""
    parser = argparse.ArgumentParser(
        prog="pwr-pipeline",
        description="Run the PWR workforce elasticity pipeline end-to-end.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing the open-data substitute set (default: ./data).",
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory to write panel, features, model and report artefacts (default: ./outputs).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic random seed for placebo and Random Forest stages.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline end-to-end and return a POSIX exit code."""
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
