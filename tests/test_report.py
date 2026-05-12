"""Report and risk-score contract tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pwr_elasticity import report


def _features_fixture(n_orgs: int = 30, n_years: int = 4, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    fys = ("2021/22", "2022/23", "2023/24", "2024/25")[:n_years]
    rows = []
    for org_idx in range(n_orgs):
        substantive_base = 100e6 + rng.normal(0, 5e6)
        vacancy_int = rng.normal(0.07, 0.015)
        turnover_int = rng.normal(0.12, 0.01)
        ae_int = rng.normal(0.94, 0.02)
        provider_type = ("acute", "mental_health", "community", "ambulance")[org_idx % 4]
        for fy_idx, fy in enumerate(fys):
            substantive = substantive_base * (1.0 + 0.03 * fy_idx + rng.normal(0, 0.01))
            other = substantive * (0.15 + 0.02 * rng.normal())
            log_other = np.log(other + 1) - 0.3 * fy_idx + rng.normal(0, 0.05)
            rows.append(
                {
                    "org_code": f"R{org_idx:03d}",
                    "org_name": f"TRUST {org_idx:03d} NHS TRUST",
                    "financial_year": fy,
                    "ics_code": f"Q{org_idx % 3:02d}",
                    "nhse_region_code": ("Y56", "Y62", "Y60")[org_idx % 3],
                    "provider_type": provider_type,
                    "substantive_pay_gbp": substantive,
                    "other_staff_pay_gbp": other,
                    "total_pay_gbp": substantive + other,
                    "staff_in_post_fte": 1500.0 + rng.normal(0, 50),
                    "other_to_substantive_ratio": other / substantive,
                    "vacancy_rate": vacancy_int + 0.01 * fy_idx + rng.normal(0, 0.005),
                    "turnover_rate": turnover_int + rng.normal(0, 0.01),
                    "pct_met_4hr": ae_int - 0.005 * fy_idx + rng.normal(0, 0.005),
                    "pay_intensity": other / (1500.0 + rng.normal(0, 50)),
                    "log_substantive_pay": np.log(substantive),
                    "log_other_staff_pay": log_other,
                    "policy_intensity_t": fy_idx,
                }
            )
    df = pd.DataFrame(rows)
    df["policy_intensity_t"] = df["policy_intensity_t"].astype("Int64")
    return df


# ---------------------------------------------------------------------------
# compute_risk_scores
# ---------------------------------------------------------------------------


def test_compute_risk_scores_emits_provider_level_rows() -> None:
    f = _features_fixture()
    out = report.compute_risk_scores(f)
    assert set(out.columns) >= {
        "org_code",
        "org_name",
        "provider_type",
        "nhse_region_code",
        "cost_inversion",
        "vacancy_pressure",
        "operational_pressure",
        "policy_exposure",
        "risk_score",
    }
    assert len(out) == 30
    # Composite score is in [0, 1] (each component is min-max
    # normalised; weights sum to 1).
    assert ((out["risk_score"] >= 0) & (out["risk_score"] <= 1)).all()


def test_compute_risk_scores_sorted_desc() -> None:
    out = report.compute_risk_scores(_features_fixture())
    assert (out["risk_score"].diff().dropna() <= 0).all()


def test_compute_risk_scores_empty_returns_schema() -> None:
    out = report.compute_risk_scores(pd.DataFrame())
    assert out.empty
    assert "risk_score" in out.columns


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


def test_build_report_writes_html(tmp_path: Path) -> None:
    out = report.build_report(_features_fixture(), tmp_path / "out" / "report.html")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # Headline coefficient and a section header appear in the rendered HTML.
    assert "Headline estimate" in content
    assert "Heterogeneity" in content
    assert "data:image/png;base64" in content
