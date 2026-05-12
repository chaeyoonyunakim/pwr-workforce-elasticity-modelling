"""Feature engineering contract tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pwr_elasticity import features


def _panel_fixture() -> pd.DataFrame:
    """Two providers, four years each — minimal but covers lag + share logic."""
    rows = []
    for org, region, mult in [("RXX", "Y56", 1.0), ("RYY", "Y62", 0.5)]:
        for fy_idx, fy in enumerate(("2021/22", "2022/23", "2023/24", "2024/25")):
            rows.append(
                {
                    "org_code": org,
                    "org_name": f"TRUST {org[-1]} NHS TRUST",
                    "financial_year": fy,
                    "ics_code": "QXX",
                    "nhse_region_code": region,
                    "substantive_pay_gbp": (100e6 + fy_idx * 10e6) * mult,
                    "other_staff_pay_gbp": (20e6 + fy_idx * 2e6) * mult,
                    "total_pay_gbp": (120e6 + fy_idx * 12e6) * mult,
                    "staff_in_post_fte": 2000.0 * mult,
                    "vacancy_rate": 0.07 + 0.01 * fy_idx,
                    "turnover_rate": 0.12,
                    "pct_met_4hr": 0.93,
                    "ae_total_attendances": 20_000_000.0,
                    "rtt_n_waiting": pd.NA,
                    "rtt_n_waiting_52plus_weeks": pd.NA,
                }
            )
    return pd.DataFrame(rows)


def test_compute_features_emits_expected_columns() -> None:
    out = features.compute_features(_panel_fixture())
    expected = {
        "other_to_substantive_ratio",
        "other_share_of_pay",
        "substantive_share_of_pay",
        "pay_intensity",
        "policy_intensity_t",
        "policy_shock_t",
        "lagged_other_staff_pay",
        "lagged_substantive_pay",
        "lagged_vacancy_rate",
        "log_other_staff_pay",
        "log_substantive_pay",
        "log_total_pay",
        "provider_type",
    }
    assert expected.issubset(out.columns)


def test_compute_features_ratio_and_share_arithmetic() -> None:
    out = features.compute_features(_panel_fixture())
    rxx_22 = out[(out["org_code"] == "RXX") & (out["financial_year"] == "2021/22")].iloc[0]
    # other / substantive = 20 / 100 = 0.2
    assert abs(float(rxx_22["other_to_substantive_ratio"]) - 0.2) < 1e-9
    # other / total = 20 / 120 ≈ 0.1667
    assert abs(float(rxx_22["other_share_of_pay"]) - (20.0 / 120.0)) < 1e-9
    # shares sum to 1 (within float tolerance)
    assert (
        abs(float(rxx_22["other_share_of_pay"]) + float(rxx_22["substantive_share_of_pay"]) - 1.0)
        < 1e-9
    )


def test_compute_features_lags_within_provider() -> None:
    out = features.compute_features(_panel_fixture())
    rxx = out[out["org_code"] == "RXX"].sort_values("financial_year")
    # First-year lag must be NaN (no prior observation).
    assert pd.isna(rxx.iloc[0]["lagged_other_staff_pay"])
    # Second-year lag = first-year value.
    assert float(rxx.iloc[1]["lagged_other_staff_pay"]) == float(rxx.iloc[0]["other_staff_pay_gbp"])


def test_compute_features_policy_intensity_monotone() -> None:
    out = features.compute_features(_panel_fixture())
    intensities = (
        out[["financial_year", "policy_intensity_t"]]
        .drop_duplicates()
        .sort_values("financial_year")
    )
    assert list(intensities["policy_intensity_t"]) == [0, 1, 2, 3]


def test_compute_features_policy_shock_zero_in_2021_22() -> None:
    out = features.compute_features(_panel_fixture())
    pre = out[out["financial_year"] == "2021/22"]
    assert (pre["policy_shock_t"] == 0).all()
    post = out[out["financial_year"] == "2022/23"]
    assert (post["policy_shock_t"] == 1).all()


def test_compute_features_log_uses_offset() -> None:
    out = features.compute_features(_panel_fixture())
    rxx_22 = out[(out["org_code"] == "RXX") & (out["financial_year"] == "2021/22")].iloc[0]
    expected = np.log(20e6 + 1.0)
    assert abs(float(rxx_22["log_other_staff_pay"]) - expected) < 1e-6


def test_compute_features_empty_input_preserves_schema() -> None:
    out = features.compute_features(pd.DataFrame())
    for col in (
        "other_to_substantive_ratio",
        "policy_intensity_t",
        "log_other_staff_pay",
        "provider_type",
    ):
        assert col in out.columns


@pytest.mark.parametrize(
    "name,expected",
    [
        ("NORTHERN ACUTE NHS TRUST", "acute"),
        ("EAST LONDON MENTAL HEALTH TRUST", "mental_health"),
        ("LONDON AMBULANCE SERVICE NHS TRUST", "ambulance"),
        ("SOLENT COMMUNITY NHS TRUST", "community"),
        ("ROYAL MARSDEN NHS FOUNDATION TRUST", "specialist"),
        ("MOORFIELDS EYE HOSPITAL NHS FOUNDATION TRUST", "specialist"),
        ("THE CHRISTIE NHS FOUNDATION TRUST", "specialist"),
        # Unknown / generic names should default to acute.
        ("SOME NEW TRUST 2026", "acute"),
    ],
)
def test_encode_provider_type_handles_known_patterns(name: str, expected: str) -> None:
    out = features.encode_provider_type(pd.Series([name]))
    assert out.iloc[0] == expected


def test_encode_policy_intensity_unknown_fy_returns_na() -> None:
    out = features.encode_policy_intensity(pd.Series(["2099/00", "2021/22"]))
    assert pd.isna(out.iloc[0])
    assert int(out.iloc[1]) == 0
