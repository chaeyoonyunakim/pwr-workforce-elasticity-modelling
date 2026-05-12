"""Model estimator contract tests.

The estimators delegate to ``linearmodels.PanelOLS`` and
``sklearn.ensemble.RandomForestRegressor``; these tests verify the
project-specific wiring (column selection, FY-to-integer conversion,
robustness variants, heterogeneity stratification) rather than the
upstream numerics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pwr_elasticity import models


def _features_fixture(n_orgs: int = 20, n_years: int = 4, seed: int = 0) -> pd.DataFrame:
    """A synthetic feature panel large enough to estimate the TWFE spec."""
    rng = np.random.default_rng(seed)
    fys = ("2021/22", "2022/23", "2023/24", "2024/25")[:n_years]
    rows = []
    for org_idx in range(n_orgs):
        provider_type = "acute" if org_idx % 2 else "mental_health"
        substantive_base = 100e6 + rng.normal(0, 5e6)
        for fy_idx, fy in enumerate(fys):
            policy = fy_idx  # 0, 1, 2, 3
            # Allow substantive pay to drift over time within each provider
            # so log_substantive_pay is not collinear with provider FE.
            substantive = substantive_base * (1.0 + 0.03 * fy_idx + rng.normal(0, 0.01))
            log_other = (
                np.log(substantive + rng.normal(0, 1e6)) - 0.3 * policy + rng.normal(0, 0.05)
            )
            rows.append(
                {
                    "org_code": f"R{org_idx:03d}",
                    "org_name": f"TRUST {org_idx:03d} NHS TRUST",
                    "financial_year": fy,
                    "ics_code": f"Q{org_idx % 3:02d}",
                    "nhse_region_code": "Y56",
                    "provider_type": provider_type,
                    "substantive_pay_gbp": substantive,
                    "other_staff_pay_gbp": np.exp(log_other),
                    "total_pay_gbp": substantive + np.exp(log_other),
                    "staff_in_post_fte": 1500.0,
                    "vacancy_rate": 0.07 + 0.01 * policy + rng.normal(0, 0.005),
                    "turnover_rate": 0.12 + rng.normal(0, 0.01),
                    "pct_met_4hr": 0.94 - 0.005 * policy + rng.normal(0, 0.003),
                    "log_substantive_pay": np.log(substantive),
                    "log_other_staff_pay": log_other,
                    "policy_intensity_t": pd.NA,  # set below in Int64
                }
            )
    df = pd.DataFrame(rows)
    df["policy_intensity_t"] = (
        df["financial_year"].str.split("/").str[0].astype(int) - 2021
    ).astype("Int64")
    return df


# ---------------------------------------------------------------------------
# estimate_twfe
# ---------------------------------------------------------------------------


def test_estimate_twfe_returns_estimate_with_expected_fields() -> None:
    est = models.estimate_twfe(_features_fixture())
    assert isinstance(est, models.ElasticityEstimate)
    assert est.specification == "twfe_primary"
    assert est.coefficient_name == "policy_intensity_t"
    assert est.std_error > 0
    assert est.ci_lower < est.coefficient < est.ci_upper
    assert est.n_observations == 20 * 4
    assert est.n_clusters >= 1


def test_estimate_twfe_recovers_negative_policy_sign() -> None:
    # Fixture is generated with a true β = -0.3 on policy_intensity_t.
    est = models.estimate_twfe(_features_fixture(seed=42))
    assert est.coefficient < 0
    # Recovery should be within a generous tolerance given the synthetic noise.
    assert abs(est.coefficient - (-0.3)) < 0.2


def test_estimate_twfe_time_effects_returns_an_estimate_with_drop_absorbed() -> None:
    # With both entity and time effects on a four-year panel,
    # policy_intensity_t may be absorbed (or near-absorbed); we simply
    # require the call to return an estimate. The coefficient_name
    # field documents what was reportable.
    est = models.estimate_twfe(_features_fixture(seed=1), time_effects=True, drop_absorbed=True)
    assert isinstance(est, models.ElasticityEstimate)
    assert est.n_observations > 0


# ---------------------------------------------------------------------------
# estimate_rf_nonlinearity
# ---------------------------------------------------------------------------


def test_estimate_rf_nonlinearity_returns_partial_dependence() -> None:
    pdp = models.estimate_rf_nonlinearity(_features_fixture())
    assert set(pdp.columns) == {"feature", "grid_value", "predicted_outcome"}
    assert set(pdp["feature"].unique()) <= {"policy_intensity_t", "log_substantive_pay"}
    assert len(pdp) > 0


# ---------------------------------------------------------------------------
# estimate_heterogeneity
# ---------------------------------------------------------------------------


def test_estimate_heterogeneity_strata_have_expected_columns() -> None:
    het = models.estimate_heterogeneity(_features_fixture(n_orgs=40))
    assert set(het.columns) >= {
        "stratum",
        "coefficient",
        "std_error",
        "ci_lower",
        "ci_upper",
        "n_observations",
    }
    # Two provider_types in the fixture should both appear.
    assert set(het["stratum"]) == {"acute", "mental_health"}


def test_estimate_heterogeneity_skips_small_strata() -> None:
    df = _features_fixture(n_orgs=4)  # only 16 rows total
    # Set min_observations above the per-stratum count to verify the skip.
    het = models.estimate_heterogeneity(df, min_observations=100)
    assert het.empty


# ---------------------------------------------------------------------------
# run_robustness
# ---------------------------------------------------------------------------


def test_run_robustness_emits_expected_specifications() -> None:
    out = models.run_robustness(_features_fixture(n_orgs=40))
    assert set(out["specification"]) >= {
        "levels",
        "drop_2021_22",
        "drop_rec_trusts",
        "cluster_at_provider",
        "twfe_drop_absorbed",
    }


def test_run_robustness_drop_rec_trusts_matches_full_panel_when_none_present() -> None:
    # Synthetic fixture contains no REC case-study trusts — the drop
    # specification should therefore reproduce the primary panel.
    out = models.run_robustness(_features_fixture(seed=2, n_orgs=40))
    primary = out[out["specification"] == "cluster_at_provider"].iloc[0]
    dropped = out[out["specification"] == "drop_rec_trusts"].iloc[0]
    # Same observation count (no rows excluded).
    assert dropped["n_observations"] == primary["n_observations"]
