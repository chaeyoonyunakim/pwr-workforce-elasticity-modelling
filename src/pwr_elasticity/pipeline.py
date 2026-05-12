"""End-to-end orchestration: data → panel → features → models → report.

Entry point invoked by ``pwr-pipeline`` (see ``pyproject.toml``
``[project.scripts]``) and by ``python -m pwr_elasticity.pipeline``.
Writes all artefacts under ``outputs/`` and a reproducibility manifest
at ``outputs/manifest.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from pwr_elasticity import diagnostics, features, io, manifest, models, panel, report


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
        help="Directory to write panel, features, model and report artefacts.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic random seed for placebo and Random Forest stages.",
    )
    parser.add_argument(
        "--placebo-iterations",
        type=int,
        default=24,
        help="Number of placebo permutations (default 24 = full enumeration for 4 FYs).",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip the HTML report (useful for fast iteration during development).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
    """Run the pipeline end-to-end and return a POSIX exit code."""
    args = parse_args(argv)
    data_dir = args.data_dir
    outputs_dir = args.outputs_dir

    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "panel").mkdir(exist_ok=True)
    (outputs_dir / "features").mkdir(exist_ok=True)
    (outputs_dir / "models").mkdir(exist_ok=True)
    (outputs_dir / "diagnostics").mkdir(exist_ok=True)

    print("[1/8] reading sources...", flush=True)
    tac = io.read_tac(data_dir / "tac_provider_accounts")
    hchs = io.read_hchs_staff_in_post(
        data_dir
        / "workforce_stats"
        / "hchs_oct_2025"
        / "Core 1. Staff group - England, NHSE region, ICS and org, Oct-25.csv"
    )
    turnover = io.read_hchs_turnover(
        data_dir
        / "workforce_stats"
        / "turnover_oct_2025"
        / "Turnover 1. Staff group - NHSE region, annual, Sep-09 to Oct-25.csv"
    )
    vacancies = io.read_vacancies(
        data_dir / "vacancy_stats" / "nhs-vac-stats-apr15-dec25-eng-tables.xlsx"
    )
    ae = io.read_ae(data_dir / "ae_performance" / "Monthly-AE-Time-Series-March-2026.xls")
    rtt = io.read_rtt(
        data_dir / "rtt_performance" / "feb26" / "20260228-RTT-February-2026-full-extract.csv"
    )
    ods = io.read_ods_trusts(data_dir / "reference" / "etr-nhs-trusts.csv")

    print("[2/8] building panel...", flush=True)
    panel_df = panel.build_panel(tac, hchs, turnover, vacancies, ae, rtt, ods)
    exclusions = panel.provider_exclusions({"tac": tac, "hchs": hchs, "ods": ods})
    panel_df.to_parquet(outputs_dir / "panel" / "provider_year_panel.parquet", index=False)
    exclusions.to_parquet(outputs_dir / "panel" / "exclusions.parquet", index=False)

    print("[3/8] computing features...", flush=True)
    feature_df = features.compute_features(panel_df)
    feature_df.to_parquet(outputs_dir / "features" / "features.parquet", index=False)

    print("[4/8] estimating primary TWFE...", flush=True)
    estimate = models.estimate_twfe(feature_df)
    estimate_dict = asdict(estimate)
    pd.DataFrame([estimate_dict]).to_parquet(
        outputs_dir / "models" / "elasticity_estimates.parquet", index=False
    )

    print("[5/8] heterogeneity and robustness...", flush=True)
    heterogeneity = models.estimate_heterogeneity(feature_df)
    robustness = models.run_robustness(feature_df)
    heterogeneity.to_parquet(outputs_dir / "models" / "heterogeneity.parquet", index=False)
    robustness.to_parquet(outputs_dir / "models" / "robustness.parquet", index=False)

    print("[6/8] diagnostics (pre-trend, placebo, VIF)...", flush=True)
    pre_trend = diagnostics.pre_trend_check(feature_df)
    placebo = diagnostics.placebo_test(
        feature_df, n_iterations=args.placebo_iterations, seed=args.seed
    )
    vif = diagnostics.variance_inflation(feature_df)
    pre_trend.to_parquet(outputs_dir / "diagnostics" / "pre_trend.parquet", index=False)
    placebo.to_parquet(outputs_dir / "diagnostics" / "placebo.parquet", index=False)
    vif.to_parquet(outputs_dir / "diagnostics" / "vif.parquet", index=False)

    print("[7/8] risk scores...", flush=True)
    risk_scores = report.compute_risk_scores(feature_df)
    risk_scores.to_parquet(outputs_dir / "risk_scores.parquet", index=False)

    if args.skip_report:
        print("[8/8] report skipped (--skip-report)...", flush=True)
    else:
        print("[8/8] rendering HTML report...", flush=True)
        report.build_report(
            feature_df,
            outputs_dir / "report.html",
            estimate=estimate,
            heterogeneity=heterogeneity,
            robustness=robustness,
            pre_trend=pre_trend,
            placebo=placebo,
            risk_scores=risk_scores,
        )

    manifest_path = manifest.write_manifest(
        outputs_dir / "manifest.json",
        data_dir=data_dir,
        outputs_dir=outputs_dir,
        seed=args.seed,
        parameters={
            "placebo_iterations": args.placebo_iterations,
            "skip_report": args.skip_report,
        },
    )

    summary = {
        "headline_coefficient": estimate.coefficient,
        "headline_ci": [estimate.ci_lower, estimate.ci_upper],
        "n_observations": estimate.n_observations,
        "manifest": str(manifest_path),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
