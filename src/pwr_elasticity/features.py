"""Feature engineering for the elasticity model.

See ``plan/PLAN.md`` §T4 for the full feature list and acceptance
criteria. Every feature defined here is pinned by a unit test in
``tests/test_features.py``.

Adaptation note. The plan §T4 feature list was specified before T2
inspection revealed that the Trust Accounts Consolidation publication
does not separate Bank pay from Agency pay — the two are reported as a
combined "Other staff" line (see ``data/DATA_DICTIONARY.md`` §3.1).
The features here therefore operate on the available
``other_staff_pay_gbp`` measure rather than on a bank-vs-agency split.
The two `Bank_Agency_Ratio` and `bank_share_of_pay` features in the plan
are recast as ``other_to_substantive_ratio`` and
``other_share_of_pay`` respectively; their economic interpretation
remains the elasticity of non-substantive workforce expenditure with
respect to agency-restriction policy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# In-window agency-rule policy events (financial years; see
# data/DATA_DICTIONARY.md §3.6). policy_intensity_t = cumulative count
# of events in force as of the FY midpoint.
POLICY_EVENT_YEARS: dict[str, int] = {
    "2021/22": 0,
    "2022/23": 1,  # Sep 2022 expenditure-ceiling re-introduction
    "2023/24": 2,  # 2023/24 agency-rule revisions
    "2024/25": 3,  # 2024/25 agency-rule revisions
    "2025/26": 5,  # 1 Jul 2025 CEO sign-off + 2026 30% mandate
}

# Years in which a fresh policy event came into force.
POLICY_SHOCK_YEARS: set[str] = {"2022/23", "2023/24", "2024/25", "2025/26"}

# Provider-type heuristics applied to ``org_name``. The first pattern
# that matches wins; the default category is "acute".
_PROVIDER_TYPE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("ambulance", "ambulance"),
    ("mental health", "mental_health"),
    ("mh ", "mental_health"),
    ("community", "community"),
    ("partnership", "community"),
    ("foundation trust for children", "specialist"),
    ("royal marsden", "specialist"),
    ("moorfields", "specialist"),
    ("royal brompton", "specialist"),
    ("great ormond street", "specialist"),
    ("papworth", "specialist"),
    ("liverpool heart and chest", "specialist"),
    ("the walton centre", "specialist"),
    ("royal national orthopaedic", "specialist"),
    ("the christie", "specialist"),
    ("guy's and st thomas'", "specialist"),
)
_DEFAULT_PROVIDER_TYPE: str = "acute"

# Small positive constant added before logging strictly-positive
# financial columns. The default reserved-decision (plan §9.3) is £1;
# at the scale of provider pay (hundreds of millions of pounds) this is
# numerically negligible.
_LOG_OFFSET_GBP: float = 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Derive the analytical features used by the elasticity model.

    Parameters
    ----------
    panel : pandas.DataFrame
        Output of :func:`pwr_elasticity.panel.build_panel`.

    Returns
    -------
    pandas.DataFrame
        ``panel`` enriched with the features listed in this module's
        docstring, in addition to the panel's original columns:

        - ``other_to_substantive_ratio`` — other-staff pay ÷ substantive pay
          (proxies the plan's ``bank_agency_ratio``)
        - ``other_share_of_pay`` — other-staff pay ÷ total pay
        - ``substantive_share_of_pay`` — substantive pay ÷ total pay
        - ``pay_intensity`` — other-staff pay ÷ staff_in_post_fte (£ / FTE)
        - ``policy_intensity_t`` — Int64 ordinal index (see §T4)
        - ``policy_shock_t`` — Int8 binary indicator (0 / 1)
        - ``lagged_other_staff_pay``, ``lagged_substantive_pay``,
          ``lagged_vacancy_rate`` — one-FY lag within ``org_code``
        - ``log_other_staff_pay``, ``log_substantive_pay``,
          ``log_total_pay`` — natural log of pay + £1
        - ``provider_type`` — categorical, see :func:`encode_provider_type`
    """
    if panel.empty:
        out = panel.copy()
        for col in _FEATURE_COLUMNS:
            out[col] = pd.NA
        return out

    out = panel.sort_values(["org_code", "financial_year"]).copy()

    out["other_to_substantive_ratio"] = out["other_staff_pay_gbp"].astype("Float64") / out[
        "substantive_pay_gbp"
    ].astype("Float64")
    out["other_share_of_pay"] = out["other_staff_pay_gbp"].astype("Float64") / out[
        "total_pay_gbp"
    ].astype("Float64")
    out["substantive_share_of_pay"] = out["substantive_pay_gbp"].astype("Float64") / out[
        "total_pay_gbp"
    ].astype("Float64")
    out["pay_intensity"] = out["other_staff_pay_gbp"].astype("Float64") / out[
        "staff_in_post_fte"
    ].astype("Float64")

    out["policy_intensity_t"] = encode_policy_intensity(out["financial_year"])
    out["policy_shock_t"] = (
        out["financial_year"].map(lambda fy: 1 if fy in POLICY_SHOCK_YEARS else 0).astype("Int8")
    )

    # Lags within provider — sort already by org_code, financial_year above.
    for col, lag_name in (
        ("other_staff_pay_gbp", "lagged_other_staff_pay"),
        ("substantive_pay_gbp", "lagged_substantive_pay"),
        ("vacancy_rate", "lagged_vacancy_rate"),
    ):
        out[lag_name] = out.groupby("org_code", dropna=False)[col].shift(1)

    out["log_other_staff_pay"] = np.log(
        out["other_staff_pay_gbp"].astype("float64") + _LOG_OFFSET_GBP
    )
    out["log_substantive_pay"] = np.log(
        out["substantive_pay_gbp"].astype("float64") + _LOG_OFFSET_GBP
    )
    out["log_total_pay"] = np.log(out["total_pay_gbp"].astype("float64") + _LOG_OFFSET_GBP)

    out["provider_type"] = encode_provider_type(out["org_name"])

    return out.reset_index(drop=True)


def encode_policy_intensity(financial_year: pd.Series) -> pd.Series:
    """Encode cumulative in-window agency-rule events as of FY midpoint.

    Parameters
    ----------
    financial_year : pandas.Series of str
        Financial-year labels of the form ``"YYYY/YY"``.

    Returns
    -------
    pandas.Series of Int64
        Ordinal index. Unknown FY labels return ``pd.NA``.
    """
    return financial_year.map(POLICY_EVENT_YEARS).astype("Int64")


def encode_provider_type(org_name: pd.Series) -> pd.Series:
    """Classify a provider into {acute, mental_health, community, specialist, ambulance}.

    Heuristic, name-pattern based. The first matching pattern in
    :data:`_PROVIDER_TYPE_PATTERNS` wins; the default category is
    ``"acute"``. Specialist trusts are matched by an explicit named
    allow-list because they cannot be inferred from generic keywords.
    """
    name_lower = org_name.astype("string").str.lower().fillna("")
    out = pd.Series(
        [_DEFAULT_PROVIDER_TYPE] * len(name_lower), index=name_lower.index, dtype="string"
    )
    for pattern, category in _PROVIDER_TYPE_PATTERNS:
        mask = name_lower.str.contains(pattern, regex=False)
        out = out.where(~mask, category)
    return out


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

# Schema kept in sync with the assignments inside :func:`compute_features`.
# Used to populate empty-input output with the expected column set.
_FEATURE_COLUMNS: tuple[str, ...] = (
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
)
