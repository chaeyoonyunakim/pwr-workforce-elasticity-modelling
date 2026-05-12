"""Pipeline entry-point smoke tests."""

from __future__ import annotations

import pytest

from pwr_elasticity import pipeline


def test_parse_args_defaults() -> None:
    args = pipeline.parse_args([])
    assert args.data_dir.name == "data"
    assert args.outputs_dir.name == "outputs"
    assert args.seed == 0


def test_parse_args_seed_override() -> None:
    args = pipeline.parse_args(["--seed", "42"])
    assert args.seed == 42


def test_main_is_currently_a_stub() -> None:
    with pytest.raises(NotImplementedError):
        pipeline.main([])
