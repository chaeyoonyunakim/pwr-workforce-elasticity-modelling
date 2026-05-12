"""Panel assembly contract tests.

Each test constructs minimal in-memory frames (no I/O) that mimic the
output schemas of :mod:`pwr_elasticity.io`, then asserts the relevant
panel-assembly behaviour. Tests are deliberately independent so a
failure points to a single join.
"""

from __future__ import annotations

import pandas as pd

from pwr_elasticity import panel

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _tac_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "org_code": "RXX",
                "org_name": "TRUST X",
                "financial_year": "2022/23",
                "substantive_pay_gbp": 180e6,
                "other_staff_pay_gbp": 20e6,
                "total_pay_gbp": 200e6,
            },
            {
                "org_code": "RYY",
                "org_name": "TRUST Y",
                "financial_year": "2022/23",
                "substantive_pay_gbp": 95e6,
                "other_staff_pay_gbp": 10e6,
                "total_pay_gbp": 105e6,
            },
            # Aggregate-style row with no org_code — must be dropped.
            {
                "org_code": pd.NA,
                "org_name": "ALL ENGLAND",
                "financial_year": "2022/23",
                "substantive_pay_gbp": 1e9,
                "other_staff_pay_gbp": 1e8,
                "total_pay_gbp": 1.1e9,
            },
        ]
    )


def _ods_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "org_code": "RXX",
                "org_name": "TRUST X",
                "nhse_region_code": "Y56",  # London
                "parent_org_code": pd.NA,
                "open_date": pd.Timestamp("2010-04-01", tz="UTC"),
                "close_date": pd.NaT,
                "is_open": True,
            },
            {
                "org_code": "RYY",
                "org_name": "TRUST Y",
                "nhse_region_code": "Y62",  # North West
                "parent_org_code": pd.NA,
                # Mid-FY open — should trigger a merger_transition exclusion.
                "open_date": pd.Timestamp("2022-10-01", tz="UTC"),
                "close_date": pd.NaT,
                "is_open": True,
            },
        ]
    )


def _hchs_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for org, region_code, ics in [("RXX", "Y56", "QXX"), ("RYY", "Y62", "QYY")]:
        for month in ("2022-04-30", "2022-10-31", "2023-03-31"):
            rows.append(
                {
                    "org_code": org,
                    "org_name": f"TRUST {org[-1]}",
                    "ics_code": ics,
                    "ics_name": ics,
                    "nhse_region_code": region_code,
                    "nhse_region_name": region_code,
                    "period_month": pd.Timestamp(month, tz="UTC"),
                    "main_staff_group": panel.ALL_STAFF_GROUPS_LABEL,
                    "staff_group": panel.ALL_STAFF_GROUPS_LABEL,
                    "fte": 1000.0 if org == "RXX" else 500.0,
                    "headcount": pd.NA,
                }
            )
    return pd.DataFrame(rows)


def _turnover_frame() -> pd.DataFrame:
    rows = []
    for region_code, denom, leavers in [("Y56", 100_000, 12_000), ("Y62", 80_000, 10_000)]:
        rows.append(
            {
                "nhse_region_code": region_code,
                "nhse_region_name": region_code,
                "period_label": "202204 to 202303",
                "period_end_year": 2023,
                "type": panel.TURNOVER_DENOMINATOR_TYPE,
                "main_staff_group": panel.ALL_STAFF_GROUPS_LABEL,
                "staff_group": panel.ALL_STAFF_GROUPS_LABEL,
                "headcount": denom,
                "fte": pd.NA,
            }
        )
        rows.append(
            {
                "nhse_region_code": region_code,
                "nhse_region_name": region_code,
                "period_label": "202204 to 202303",
                "period_end_year": 2023,
                "type": panel.TURNOVER_LEAVERS_TYPE,
                "main_staff_group": panel.ALL_STAFF_GROUPS_LABEL,
                "staff_group": panel.ALL_STAFF_GROUPS_LABEL,
                "headcount": leavers,
                "fte": pd.NA,
            }
        )
    return pd.DataFrame(rows)


def _vacancies_frame() -> pd.DataFrame:
    rows = []
    for region_name, rate_q1, rate_q4 in [("London", 0.08, 0.10), ("North West", 0.05, 0.07)]:
        for quarter, rate in (("2022/23 Q1", rate_q1), ("2022/23 Q4", rate_q4)):
            rows.append(
                {
                    "nhse_region_name": region_name,
                    "sector": "Acute",
                    "period_quarter": quarter,
                    "vacancy_fte": 1000.0,
                    "vacancy_rate": rate,
                }
            )
    return pd.DataFrame(rows)


def _ae_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "period_month": pd.Timestamp(month, tz="UTC"),
                "attendances_type1": 1_000_000.0,
                "total_attendances": 1_500_000.0,
                "emergency_admissions_total": 300_000.0,
                "wait_4hr_to_12hr": 100_000.0,
                "wait_over_12hr": 1_000.0,
                "pct_met_4hr": 1 - 100_000.0 / 1_500_000.0,
            }
            for month in ("2022-04-01", "2022-10-01", "2023-03-01")
        ]
    )


def _rtt_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "period_month": pd.Timestamp("2023-02-28", tz="UTC"),
                "org_code": "RXX",
                "treatment_function_code": "C_101",
                "treatment_function_name": "Urology",
                "n_waiting": 10_000,
                "n_waiting_52plus_weeks": 500,
            },
            {
                "period_month": pd.Timestamp("2023-02-28", tz="UTC"),
                "org_code": "RXX",
                "treatment_function_code": "C_110",
                "treatment_function_name": "Trauma & Orthopaedics",
                "n_waiting": 15_000,
                "n_waiting_52plus_weeks": 800,
            },
        ]
    )


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_build_panel_keys_are_unique_and_drop_aggregate_rows() -> None:
    p = panel.build_panel(
        tac=_tac_frame(),
        hchs=_hchs_frame(),
        turnover=_turnover_frame(),
        vacancies=_vacancies_frame(),
        ae=_ae_frame(),
        rtt=_rtt_frame(),
        ods=_ods_frame(),
    )
    # NaN-org_code row dropped; the panel keeps one row per (org, FY).
    assert len(p) == 2
    assert p.duplicated(["org_code", "financial_year"]).sum() == 0
    assert set(p["org_code"]) == {"RXX", "RYY"}


def test_build_panel_attaches_workforce_fte() -> None:
    p = panel.build_panel(
        tac=_tac_frame(),
        hchs=_hchs_frame(),
        turnover=_turnover_frame(),
        vacancies=_vacancies_frame(),
        ae=_ae_frame(),
        rtt=_rtt_frame(),
        ods=_ods_frame(),
    )
    rxx = p[p["org_code"] == "RXX"].iloc[0]
    # Three monthly observations, all = 1000; the FY mean is 1000.
    assert rxx["staff_in_post_fte"] == 1000.0


def test_build_panel_vacancy_join_respects_region() -> None:
    p = panel.build_panel(
        tac=_tac_frame(),
        hchs=_hchs_frame(),
        turnover=_turnover_frame(),
        vacancies=_vacancies_frame(),
        ae=_ae_frame(),
        rtt=_rtt_frame(),
        ods=_ods_frame(),
    )
    # London (Y56) mean of (0.08, 0.10) = 0.09; North West (Y62) = 0.06.
    rxx = p[p["org_code"] == "RXX"].iloc[0]
    ryy = p[p["org_code"] == "RYY"].iloc[0]
    assert abs(rxx["vacancy_rate"] - 0.09) < 1e-9
    assert abs(ryy["vacancy_rate"] - 0.06) < 1e-9


def test_build_panel_turnover_join_respects_region() -> None:
    p = panel.build_panel(
        tac=_tac_frame(),
        hchs=_hchs_frame(),
        turnover=_turnover_frame(),
        vacancies=_vacancies_frame(),
        ae=_ae_frame(),
        rtt=_rtt_frame(),
        ods=_ods_frame(),
    )
    rxx = p[p["org_code"] == "RXX"].iloc[0]
    ryy = p[p["org_code"] == "RYY"].iloc[0]
    # London: 12000 / 100000 = 0.12. North West: 10000 / 80000 = 0.125.
    assert abs(rxx["turnover_rate"] - 0.12) < 1e-9
    assert abs(ryy["turnover_rate"] - 0.125) < 1e-9


def test_build_panel_rtt_aggregates_across_treatment_functions() -> None:
    p = panel.build_panel(
        tac=_tac_frame(),
        hchs=_hchs_frame(),
        turnover=_turnover_frame(),
        vacancies=_vacancies_frame(),
        ae=_ae_frame(),
        rtt=_rtt_frame(),
        ods=_ods_frame(),
    )
    rxx = p[p["org_code"] == "RXX"].iloc[0]
    # 10_000 + 15_000 = 25_000; 500 + 800 = 1_300.
    assert int(rxx["rtt_n_waiting"]) == 25_000
    assert int(rxx["rtt_n_waiting_52plus_weeks"]) == 1_300


def test_build_panel_empty_tac_returns_empty_with_schema() -> None:
    empty = pd.DataFrame()
    p = panel.build_panel(empty, empty, empty, empty, empty, empty, empty)
    assert p.empty
    assert "org_code" in p.columns


# ---------------------------------------------------------------------------
# provider_exclusions
# ---------------------------------------------------------------------------


def test_provider_exclusions_flags_mid_fy_open() -> None:
    exclusions = panel.provider_exclusions(
        {"tac": _tac_frame(), "hchs": _hchs_frame(), "ods": _ods_frame()}
    )
    # RYY opened on 2022-10-01 — within FY 2022/23.
    assert ((exclusions["org_code"] == "RYY") & (exclusions["reason"] == "merger_transition")).any()


def test_provider_exclusions_flags_missing_hchs() -> None:
    tac = _tac_frame()
    hchs = _hchs_frame().iloc[:0]  # empty
    exclusions = panel.provider_exclusions({"tac": tac, "hchs": hchs, "ods": _ods_frame()})
    missing = exclusions[exclusions["reason"] == "missing_hchs"]
    # Only org_code-having TAC rows produce the missing_hchs flag.
    assert set(missing["org_code"]) == {"RXX", "RYY"}


def test_provider_exclusions_handles_empty_inputs() -> None:
    exclusions = panel.provider_exclusions({})
    assert exclusions.empty
    assert list(exclusions.columns) == ["org_code", "financial_year", "reason"]


# ---------------------------------------------------------------------------
# Smoke check
# ---------------------------------------------------------------------------


def test_build_panel_is_callable() -> None:
    assert callable(panel.build_panel)
    assert callable(panel.provider_exclusions)
