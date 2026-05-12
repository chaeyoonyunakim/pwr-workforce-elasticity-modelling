"""Source readers — one pure function per data product.

Each reader returns a tidy ``pandas.DataFrame`` with snake_case columns,
explicit dtypes and date parsing, and observations restricted to the
analytical window (financial years 2021/22 to 2025/26 inclusive).

Schema for each output is documented in the docstring and pinned by the
unit tests in ``tests/test_io.py``. See ``data/DATA_DICTIONARY.md`` for
the canonical source metadata and ``plan/plan.md`` §T2 for the
acceptance criteria.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_tac(directory: str | Path) -> pd.DataFrame:
    """Read and concatenate the four in-window Trust Accounts Consolidation files.

    Parameters
    ----------
    directory : str or Path
        Directory containing ``TAC-data-published-in-NHS-trust*-accounts-for-YYYY-YY.xlsx``
        for financial years 2021/22 through 2024/25.

    Returns
    -------
    pandas.DataFrame
        Long-format frame with columns:
        ``org_code`` (string), ``financial_year`` (string, ``"YYYY/YY"``),
        ``bank_pay_gbp`` (float), ``agency_pay_gbp`` (float),
        ``substantive_pay_gbp`` (float),
        ``total_operating_expense_gbp`` (float).

    Notes
    -----
    Currency values are held in £ (GBP) at full unit precision; £m is a
    presentation choice only.
    """
    raise NotImplementedError


def read_hchs_staff_in_post(path: str | Path) -> pd.DataFrame:
    """Read NHS Workforce Statistics HCHS Staff-in-Post for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to ``Core 1. Staff group - England, NHSE region, ICS and org, Oct-25.csv``.

    Returns
    -------
    pandas.DataFrame
        Long-format frame with columns:
        ``org_code`` (string), ``ics_code`` (string),
        ``nhse_region_code`` (string), ``period_month`` (Timestamp, UTC),
        ``staff_group`` (string), ``fte`` (float), ``headcount`` (int).
    """
    raise NotImplementedError


def read_hchs_turnover(path: str | Path) -> pd.DataFrame:
    """Read NHS Workforce Statistics turnover series for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to the turnover CSV (region × staff group × age band, annual).

    Returns
    -------
    pandas.DataFrame
        Columns: ``nhse_region_code``, ``financial_year``, ``staff_group``,
        ``leaver_rate``.
    """
    raise NotImplementedError


def read_vacancies(path: str | Path) -> pd.DataFrame:
    """Read NHS Vacancy Statistics for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to ``nhs-vac-stats-apr15-dec25-eng-tables.xlsx``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``period_quarter`` (string, ``"YYYY-QN"``),
        ``staff_group`` (string), ``vacancy_rate`` (float, 0–1).
    """
    raise NotImplementedError


def read_earnings(path: str | Path) -> pd.DataFrame:
    """Read NHS Staff Earnings Estimates for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to ``Monthly-Earnings-by-AfC-band-to-Oct2025-NHS-Trusts.csv``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code``, ``period_month`` (Timestamp, UTC),
        ``afc_band`` (string), ``mean_basic_pay_gbp`` (float).
    """
    raise NotImplementedError


def read_ae(path: str | Path) -> pd.DataFrame:
    """Read the Monthly A&E Time Series for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to ``Monthly-AE-Time-Series-March-2026.xls``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code``, ``period_month`` (Timestamp, UTC),
        ``attendances_type1`` (int), ``met_4hr_type1`` (int),
        ``pct_met_4hr`` (float, 0–1).
    """
    raise NotImplementedError


def read_rtt(path: str | Path) -> pd.DataFrame:
    """Read a Referral to Treatment full-month extract.

    Parameters
    ----------
    path : str or Path
        Path to a single-month full-extract CSV.

    Returns
    -------
    pandas.DataFrame
        Aggregated to ``org_code`` × ``treatment_function`` with
        ``n_waiting`` (int) and ``n_waiting_52plus_weeks`` (int).
    """
    raise NotImplementedError


def read_ods_trusts(path: str | Path) -> pd.DataFrame:
    """Read the ODS NHS Trusts reference (``etr``) CSV.

    Parameters
    ----------
    path : str or Path
        Path to ``etr-nhs-trusts.csv``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code`` (string), ``org_name`` (string),
        ``nhse_region_code`` (string), ``open_date`` (Timestamp, UTC),
        ``close_date`` (Timestamp, UTC, NaT where open).
    """
    raise NotImplementedError
