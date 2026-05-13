"""Out-of-sample evaluation against pre-window data.

Runs the full pipeline with the analytical window shifted backward by
three financial years (2018/19 to 2020/21) to verify the model's
structural correctness against data the production model never saw.

The 2018/19 TAC vintage was published by the old NHS Improvement and is
no longer hosted as a direct download under NHS England (the legacy
URL redirects to the site root). Holdout panel coverage is therefore
2019/20 and 2020/21 only; that limitation is recorded in the output
manifest.

Usage
-----
    python scripts/evaluate_holdout.py

Requires:
    - ``data/eval_holdout/tac_provider_accounts/`` populated with the
      pre-window TAC XLSXs;
    - ``data/`` populated with the production-window source files,
      because HCHS, vacancy, A&E, earnings and ODS are reused (their
      time series cover both windows).

Outputs land in ``outputs/eval_holdout/`` with a parallel structure to
the production ``outputs/`` tree, plus an evaluation summary printed
to stdout.
"""

from __future__ import annotations

import json
import sys
import warnings
from dataclasses import asdict
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

# Patch the analytical-window constants BEFORE importing any modules
# that bind their values at import time (io, panel, features, …).
from pwr_elasticity import _constants  # noqa: E402

_HOLDOUT_WINDOW = {
    "WINDOW_START_FY": "2019/20",
    "WINDOW_END_FY": "2020/21",
    "WINDOW_START_DATE": "2019-04-01",
    "WINDOW_END_DATE": "2021-03-31",
}
for key, value in _HOLDOUT_WINDOW.items():
    setattr(_constants, key, value)

from pwr_elasticity import diagnostics, features, io, manifest, models, panel, report  # noqa: E402

# Patch the policy calendar so encode_policy_intensity covers the holdout FYs.
# In the holdout window the only in-effect agency-rule event is the
# 16 Sep 2019 admin & estates substitution rule — a step change between
# 2019/20 and 2020/21.
features.POLICY_EVENT_YEARS = {
    "2019/20": 0,  # baseline; September 2019 rule comes in mid-year
    "2020/21": 1,  # full year under the admin & estates rule
}
features.POLICY_SHOCK_YEARS = {"2020/21"}

PROD_DATA = Path("data")
HOLDOUT_TAC = Path("data/eval_holdout/tac_provider_accounts")
OUTPUTS = Path("outputs/eval_holdout")
SEED = 0


def run_evaluation() -> dict[str, Any]:  # noqa: PLR0915 — long but linear orchestrator
    """Execute the holdout pipeline and return a summary dict."""
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "panel").mkdir(exist_ok=True)
    (OUTPUTS / "features").mkdir(exist_ok=True)
    (OUTPUTS / "models").mkdir(exist_ok=True)
    (OUTPUTS / "diagnostics").mkdir(exist_ok=True)

    print("[1/8] reading sources from holdout + production paths...", flush=True)
    tac = io.read_tac(HOLDOUT_TAC)
    hchs = io.read_hchs_staff_in_post(
        PROD_DATA
        / "workforce_stats"
        / "hchs_oct_2025"
        / "Core 1. Staff group - England, NHSE region, ICS and org, Oct-25.csv"
    )
    turnover = io.read_hchs_turnover(
        PROD_DATA
        / "workforce_stats"
        / "turnover_oct_2025"
        / "Turnover 1. Staff group - NHSE region, annual, Sep-09 to Oct-25.csv"
    )
    vacancies = io.read_vacancies(
        PROD_DATA / "vacancy_stats" / "nhs-vac-stats-apr15-dec25-eng-tables.xlsx"
    )
    ae = io.read_ae(PROD_DATA / "ae_performance" / "Monthly-AE-Time-Series-March-2026.xls")
    # RTT pre-2026 extracts are not downloaded for the holdout; pass an
    # empty frame so panel.build_panel surfaces NaN for the RTT columns.
    rtt = io.read_rtt(
        PROD_DATA / "rtt_performance" / "feb26" / "20260228-RTT-February-2026-full-extract.csv"
    )
    ods = io.read_ods_trusts(PROD_DATA / "reference" / "etr-nhs-trusts.csv")
    print(
        f"  shapes: tac={tac.shape} hchs={hchs.shape} turnover={turnover.shape} "
        f"vac={vacancies.shape} ae={ae.shape} rtt={rtt.shape} ods={ods.shape}",
        flush=True,
    )

    print("[2/8] building panel...", flush=True)
    panel_df = panel.build_panel(tac, hchs, turnover, vacancies, ae, rtt, ods)
    exclusions = panel.provider_exclusions({"tac": tac, "hchs": hchs, "ods": ods})
    panel_df.to_parquet(OUTPUTS / "panel" / "provider_year_panel.parquet", index=False)
    exclusions.to_parquet(OUTPUTS / "panel" / "exclusions.parquet", index=False)
    print(f"  panel: {panel_df.shape}; exclusions: {len(exclusions)} rows", flush=True)

    print("[3/8] computing features...", flush=True)
    feature_df = features.compute_features(panel_df)
    feature_df.to_parquet(OUTPUTS / "features" / "features.parquet", index=False)

    summary: dict[str, Any] = {
        "window": _HOLDOUT_WINDOW,
        "policy_calendar": dict(features.POLICY_EVENT_YEARS),
        "panel_rows": len(panel_df),
        "feature_rows": len(feature_df),
        "providers": int(panel_df["org_code"].nunique() if not panel_df.empty else 0),
        "financial_years": sorted(panel_df["financial_year"].unique().tolist()),
    }

    print("[4/8] estimating primary TWFE...", flush=True)
    try:
        estimate = models.estimate_twfe(feature_df)
        summary["primary_estimate"] = asdict(estimate)
        pd.DataFrame([summary["primary_estimate"]]).to_parquet(
            OUTPUTS / "models" / "elasticity_estimates.parquet", index=False
        )
    except Exception as exc:
        summary["primary_estimate"] = {"error": str(exc)}

    print("[5/8] heterogeneity and robustness...", flush=True)
    try:
        het = models.estimate_heterogeneity(feature_df)
        het.to_parquet(OUTPUTS / "models" / "heterogeneity.parquet", index=False)
        summary["heterogeneity_strata"] = len(het)
    except Exception as exc:
        summary["heterogeneity_error"] = str(exc)
    try:
        rob = models.run_robustness(feature_df)
        rob.to_parquet(OUTPUTS / "models" / "robustness.parquet", index=False)
        summary["robustness_specifications"] = len(rob)
    except Exception as exc:
        summary["robustness_error"] = str(exc)

    print("[6/8] diagnostics (pre-trend, placebo, VIF)...", flush=True)
    try:
        pt = diagnostics.pre_trend_check(feature_df, event_year="2020/21")
        pt.to_parquet(OUTPUTS / "diagnostics" / "pre_trend.parquet", index=False)
        summary["pre_trend_rows"] = len(pt)
    except Exception as exc:
        summary["pre_trend_error"] = str(exc)
    try:
        plc = diagnostics.placebo_test(feature_df, n_iterations=2, seed=SEED)
        plc.to_parquet(OUTPUTS / "diagnostics" / "placebo.parquet", index=False)
        summary["placebo_iterations"] = int(plc["placebo_coefficient"].notna().sum())
    except Exception as exc:
        summary["placebo_error"] = str(exc)
    try:
        vif = diagnostics.variance_inflation(feature_df)
        vif.to_parquet(OUTPUTS / "diagnostics" / "vif.parquet", index=False)
    except Exception as exc:
        summary["vif_error"] = str(exc)

    print("[7/8] risk scores...", flush=True)
    try:
        risk = report.compute_risk_scores(feature_df)
        risk.to_parquet(OUTPUTS / "risk_scores.parquet", index=False)
        summary["risk_score_providers"] = len(risk)
    except Exception as exc:
        summary["risk_score_error"] = str(exc)

    print("[8/8] manifest...", flush=True)
    manifest.write_manifest(
        OUTPUTS / "manifest.json",
        data_dir=HOLDOUT_TAC,
        outputs_dir=OUTPUTS,
        seed=SEED,
        parameters={
            "evaluation": "pre_window_holdout",
            "window": _HOLDOUT_WINDOW,
            "policy_calendar": dict(features.POLICY_EVENT_YEARS),
        },
    )

    return summary


if __name__ == "__main__":
    import pandas as pd

    result = run_evaluation()
    print()
    print("=== Holdout evaluation summary ===")
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0)
