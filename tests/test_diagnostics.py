"""Model diagnostics contract tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pwr_elasticity import diagnostics


def _features_fixture(n_orgs: int = 20, n_years: int = 4, seed: int = 0) -> pd.DataFrame:
    """Synthetic panel mirroring the feature-frame contract."""
    rng = np.random.default_rng(seed)
    fys = ("2021/22", "2022/23", "2023/24", "2024/25")[:n_years]
    rows = []
    for org_idx in range(n_orgs):
        substantive_base = 100e6 + rng.normal(0, 5e6)
        # Per-provider baselines so covariates are not perfectly collinear
        # with year (which would break the PanelOLS rank check).
        vacancy_int = rng.normal(0.07, 0.015)
        turnover_int = rng.normal(0.12, 0.01)
        ae_int = rng.normal(0.94, 0.02)
        for fy_idx, fy in enumerate(fys):
            substantive = substantive_base * (1.0 + 0.03 * fy_idx + rng.normal(0, 0.01))
            log_other = (
                np.log(substantive + rng.normal(0, 1e6)) - 0.3 * fy_idx + rng.normal(0, 0.05)
            )
            rows.append(
                {
                    "org_code": f"R{org_idx:03d}",
                    "org_name": f"TRUST {org_idx:03d}",
                    "financial_year": fy,
                    "ics_code": f"Q{org_idx % 3:02d}",
                    "substantive_pay_gbp": substantive,
                    "other_staff_pay_gbp": np.exp(log_other),
                    "total_pay_gbp": substantive + np.exp(log_other),
                    "staff_in_post_fte": 1500.0 + rng.normal(0, 50),
                    "vacancy_rate": vacancy_int + 0.01 * fy_idx + rng.normal(0, 0.005),
                    "turnover_rate": turnover_int + rng.normal(0, 0.01),
                    "pct_met_4hr": ae_int - 0.005 * fy_idx + rng.normal(0, 0.005),
                    "log_substantive_pay": np.log(substantive),
                    "log_other_staff_pay": log_other,
                    "policy_intensity_t": fy_idx,
                }
            )
    df = pd.DataFrame(rows)
    df["policy_intensity_t"] = df["policy_intensity_t"].astype("Int64")
    return df


def test_residual_diagnostics_returns_per_observation_rows() -> None:
    f = _features_fixture()
    out = diagnostics.residual_diagnostics(f)
    assert len(out) == len(f)
    assert set(out.columns) >= {
        "residual",
        "standardised_residual",
        "fitted",
        "influence_flag",
    }
    # Residuals are mean-zero by construction of OLS.
    assert abs(out["residual"].mean()) < 0.05


def test_pre_trend_check_emits_event_study_table() -> None:
    f = _features_fixture()
    out = diagnostics.pre_trend_check(f, event_year="2022/23")
    expected_cols = {
        "financial_year",
        "relative_period",
        "coefficient",
        "std_error",
        "ci_lower",
        "ci_upper",
        "significant",
    }
    assert expected_cols.issubset(out.columns)
    # Baseline year is omitted; the rest of the panel's FYs are present.
    assert set(out["financial_year"]) == {"2021/22", "2023/24", "2024/25"}


def test_placebo_test_emits_iteration_distribution() -> None:
    f = _features_fixture()
    out = diagnostics.placebo_test(f, n_iterations=12, seed=0)
    assert set(out.columns) == {"iteration", "placebo_coefficient"}
    assert len(out) == 12
    # Most placebo coefficients should be finite.
    assert out["placebo_coefficient"].notna().sum() > 0


def test_placebo_pvalue_is_in_unit_interval() -> None:
    f = _features_fixture()
    plc = diagnostics.placebo_test(f, n_iterations=12, seed=1)
    pv = diagnostics.placebo_pvalue(0.5, plc)
    assert 0.0 <= pv <= 1.0


def test_variance_inflation_factors_shape() -> None:
    f = _features_fixture()
    out = diagnostics.variance_inflation(f)
    assert set(out.columns) == {"feature", "vif"}
    assert len(out) == len(diagnostics._DEFAULT_CONTROLS)
    # All VIFs are non-negative.
    assert (out["vif"] >= 0).all()
