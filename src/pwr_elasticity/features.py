"""Feature engineering for the elasticity model.

See ``plan/plan.md`` §T4 for the full feature list and acceptance
criteria. Every feature defined here is pinned by a unit test in
``tests/test_features.py``.
"""

from __future__ import annotations

import pandas as pd


def compute_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Derive the analytical features used by the elasticity model.

    Parameters
    ----------
    panel : pandas.DataFrame
        Output of :func:`pwr_elasticity.panel.build_panel`.

    Returns
    -------
    pandas.DataFrame
        ``panel`` enriched with: ``bank_agency_ratio``,
        ``bank_share_of_pay``, ``agency_share_of_pay``,
        ``pay_intensity``, ``policy_intensity_t``, ``policy_shock_t``,
        ``lagged_bank_pay``, ``lagged_agency_pay``,
        ``lagged_vacancy_rate``, ``log_bank_pay``, ``log_agency_pay``,
        ``provider_type``.
    """
    raise NotImplementedError


def encode_policy_intensity(financial_year: pd.Series) -> pd.Series:
    """Encode cumulative in-window agency-rule events as of FY midpoint.

    Parameters
    ----------
    financial_year : pandas.Series of str
        Financial-year labels of the form ``"YYYY/YY"``.

    Returns
    -------
    pandas.Series of int
        Ordinal index counting policy events in force at the midpoint of
        each financial year. See ``data/DATA_DICTIONARY.md`` §3.6 for
        the in-window events list.
    """
    raise NotImplementedError
