"""Pipeline entry-point and reproducibility-manifest tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pwr_elasticity import manifest, pipeline


def test_parse_args_defaults() -> None:
    args = pipeline.parse_args([])
    assert args.data_dir.name == "data"
    assert args.outputs_dir.name == "outputs"
    assert args.seed == 0
    assert args.placebo_iterations == 24
    assert args.skip_report is False


def test_parse_args_seed_override() -> None:
    args = pipeline.parse_args(["--seed", "42", "--skip-report"])
    assert args.seed == 42
    assert args.skip_report is True


def test_manifest_payload_has_expected_top_level_keys(tmp_path: Path) -> None:
    payload = manifest.build_manifest(
        data_dir=tmp_path / "data",
        outputs_dir=tmp_path / "outputs",
        seed=0,
    )
    for key in (
        "generated_at",
        "git_commit",
        "python_version",
        "platform",
        "package_versions",
        "seed",
        "parameters",
        "input_files",
        "output_files",
    ):
        assert key in payload


def test_manifest_hashes_files_under_supplied_directories(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "sample.txt").write_text("hello world", encoding="utf-8")
    payload = manifest.build_manifest(data_dir=data, outputs_dir=tmp_path / "outputs", seed=0)
    assert "sample.txt" in payload["input_files"]
    # SHA-256 of "hello world".
    assert (
        payload["input_files"]["sample.txt"]
        == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_write_manifest_round_trips_json(tmp_path: Path) -> None:
    path = manifest.write_manifest(
        tmp_path / "manifest.json",
        data_dir=tmp_path,
        outputs_dir=tmp_path,
        seed=0,
        parameters={"placebo_iterations": 24},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["parameters"] == {"placebo_iterations": 24}


def test_main_returns_zero_when_pipeline_runs_against_data() -> None:
    data_dir = Path("data")
    if not data_dir.exists():  # only run when local /data/ is populated
        pytest.skip("local /data/ not populated; pipeline integration test skipped")
    outputs_dir = Path("outputs")
    code = pipeline.main(
        [
            "--data-dir",
            str(data_dir),
            "--outputs-dir",
            str(outputs_dir),
            "--placebo-iterations",
            "24",
            "--skip-report",
        ]
    )
    assert code == 0
    assert (outputs_dir / "manifest.json").exists()
    assert (outputs_dir / "panel" / "provider_year_panel.parquet").exists()
    assert (outputs_dir / "models" / "elasticity_estimates.parquet").exists()
