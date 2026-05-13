"""Source readers — one pure function per data product.

Each reader returns a tidy ``pandas.DataFrame`` with snake_case columns,
explicit dtypes and date parsing, and observations restricted to the
analytical window (financial years 2021/22 to 2025/26 inclusive).

See ``data/DATA_DICTIONARY.md`` for the canonical source metadata and
``plan/plan.md`` §T2 for the acceptance criteria.
"""

from __future__ import annotations

import re
from pathlib import Path

import openpyxl
import pandas as pd

from pwr_elasticity._constants import (
    TAC_MAINCODE_OTHER_CY,
    TAC_MAINCODE_PERMANENT_CY,
    TAC_MAINCODE_TOTAL_CY,
    TAC_SUBCODE_NET_PAY_CANDIDATES,
    TAC_THOUSANDS_TO_GBP,
    TAC_WORKSHEET_STAFF,
    WINDOW_END_DATE,
    WINDOW_END_FY,
    WINDOW_START_DATE,
    WINDOW_START_FY,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FY_RE = re.compile(r"(\d{4})-(\d{2})")
_QUARTER_RE = re.compile(r"^(\d{4})/\d{2} Q\d")


def _financial_year_from_filename(path: Path) -> str:
    """Extract ``"YYYY/YY"`` from a TAC filename of the form ``...-YYYY-YY.xlsx``."""
    match = _FY_RE.search(path.stem)
    if match is None:
        raise ValueError(f"Could not parse financial year from filename: {path.name}")
    start, end_short = match.groups()
    return f"{start}/{end_short}"


def _in_window_fy(fy: str) -> bool:
    """Return True if ``fy`` (``"YYYY/YY"``) is within the analytical window."""
    return WINDOW_START_FY <= fy <= WINDOW_END_FY


def _find_section_row(df: pd.DataFrame, section: str, column: int = 0) -> int:
    """Locate the first row whose ``column`` cell starts with ``section`` (case-insensitive)."""
    target = section.lower()
    for idx, value in enumerate(df.iloc[:, column]):
        if isinstance(value, str) and value.strip().lower().startswith(target):
            return idx
    raise ValueError(f"Could not find section starting with '{section}' in column {column}")


def _resolve_sheet(path: str | Path, target: str) -> str:
    """Resolve a sheet name in ``path`` case-insensitively (TAC vintages differ in case)."""
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        target_lower = target.lower()
        for name in wb.sheetnames:
            if name.lower() == target_lower:
                return name
    finally:
        wb.close()
    raise ValueError(f"No sheet matching '{target}' in {path}")


def _find_row_any_column(df: pd.DataFrame, section: str) -> int:
    """Locate the first row containing ``section`` (case-insensitive) in any column."""
    target = section.lower()
    for idx in range(len(df)):
        for value in df.iloc[idx].tolist():
            if isinstance(value, str) and value.strip().lower() == target:
                return idx
    raise ValueError(f"Could not find row containing '{section}' in any column")


# ---------------------------------------------------------------------------
# Public readers
# ---------------------------------------------------------------------------


def read_tac(directory: str | Path) -> pd.DataFrame:
    """Read and concatenate the in-window Trust Accounts Consolidation files.

    Parameters
    ----------
    directory : str or Path
        Directory containing TAC XLSX files named
        ``TAC-data-published-in-NHS-trust(s)-accounts-for-YYYY-YY.xlsx`` for
        financial years within the analytical window.

    Returns
    -------
    pandas.DataFrame
        Columns:
        ``org_code`` (string), ``org_name`` (string),
        ``financial_year`` (string, ``"YYYY/YY"``),
        ``substantive_pay_gbp`` (float, £),
        ``other_staff_pay_gbp`` (float, £; Bank + Agency + Contract combined),
        ``total_pay_gbp`` (float, £).

    Notes
    -----
    TAC reports staff cost as Permanent vs Other (with Other comprising
    Bank, Agency and Contract for Services). It does **not** publish the
    Bank-versus-Agency split as a separate line item; for that breakdown,
    individual provider annual report notes or the Provider Workforce
    Return (PWR) must be consulted. See ``data/DATA_DICTIONARY.md`` §3.1.

    Values published in TAC are in £ thousands; this reader scales them
    to £ (full units).
    """
    directory = Path(directory)
    frames: list[pd.DataFrame] = []
    for path in sorted(directory.glob("TAC-data-published-in-NHS-trust*.xlsx")):
        fy = _financial_year_from_filename(path)
        if not _in_window_fy(fy):
            continue
        providers_sheet = _resolve_sheet(path, "list of providers")
        all_data_sheet = _resolve_sheet(path, "all data")
        providers = pd.read_excel(path, sheet_name=providers_sheet)
        providers = providers.rename(
            columns={"Full name of Provider": "org_name", "NHS code": "org_code"}
        )
        providers["org_code"] = providers["org_code"].astype("string").str.strip()
        providers["org_name"] = providers["org_name"].astype("string").str.strip()

        all_data = pd.read_excel(path, sheet_name=all_data_sheet)
        # Vintage 2021/22 names the value column "Value number"; 2022/23+
        # use "Total". The organisation column varies between
        # "OrganisationName" and "Organisation Name".
        value_col = "Total" if "Total" in all_data.columns else "Value number"
        org_col = (
            "OrganisationName" if "OrganisationName" in all_data.columns else "Organisation Name"
        )
        staff = all_data[all_data["WorkSheetName"] == TAC_WORKSHEET_STAFF].copy()
        # Vintage compatibility: 2022/23+ uses STA0366 (Net employee benefits
        # excluding capitalised); earlier vintages stop at STA0360 (Total
        # employee benefits excluding capitalised). Try candidates in order.
        chosen_subcode: str | None = None
        for candidate in TAC_SUBCODE_NET_PAY_CANDIDATES:
            if (staff["SubCode"] == candidate).any():
                chosen_subcode = candidate
                break
        if chosen_subcode is None:
            continue
        staff = staff[staff["SubCode"] == chosen_subcode]

        pivot = (
            staff.pivot_table(
                index=org_col,
                columns="MainCode",
                values=value_col,
                aggfunc="sum",
            )
            .reset_index()
            .rename(columns={org_col: "org_name"})
        )
        pivot["org_name"] = pivot["org_name"].astype("string").str.strip()

        merged = pivot.merge(providers[["org_code", "org_name"]], on="org_name", how="left")
        merged["financial_year"] = fy
        merged["substantive_pay_gbp"] = (
            merged.get(TAC_MAINCODE_PERMANENT_CY, pd.Series(dtype="float")) * TAC_THOUSANDS_TO_GBP
        )
        merged["other_staff_pay_gbp"] = (
            merged.get(TAC_MAINCODE_OTHER_CY, pd.Series(dtype="float")) * TAC_THOUSANDS_TO_GBP
        )
        merged["total_pay_gbp"] = (
            merged.get(TAC_MAINCODE_TOTAL_CY, pd.Series(dtype="float")) * TAC_THOUSANDS_TO_GBP
        )

        frames.append(
            merged[
                [
                    "org_code",
                    "org_name",
                    "financial_year",
                    "substantive_pay_gbp",
                    "other_staff_pay_gbp",
                    "total_pay_gbp",
                ]
            ]
        )

    if not frames:
        return pd.DataFrame(
            columns=[
                "org_code",
                "org_name",
                "financial_year",
                "substantive_pay_gbp",
                "other_staff_pay_gbp",
                "total_pay_gbp",
            ]
        )

    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["financial_year", "org_code"])
        .reset_index(drop=True)
    )


def read_hchs_staff_in_post(path: str | Path) -> pd.DataFrame:
    """Read NHS Workforce Statistics HCHS Staff-in-Post for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to ``Core 1. Staff group - England, NHSE region, ICS and org, Oct-25.csv``.

    Returns
    -------
    pandas.DataFrame
        Provider-level rows (``DATA_LEVEL == "Organisation"``) with
        columns: ``org_code``, ``org_name``, ``ics_code``, ``ics_name``,
        ``nhse_region_code``, ``nhse_region_name``, ``period_month``
        (Timestamp, UTC, normalised to month-end), ``main_staff_group``,
        ``staff_group``, ``fte`` (float), ``headcount`` (Int64).
    """
    df = pd.read_csv(path, parse_dates=["DATA_MONTH"], dtype="string")
    df = df.rename(
        columns={
            "DATA_MONTH": "period_month",
            "NHSE_REGION_CODE": "nhse_region_code",
            "NHSE_REGION_NAME": "nhse_region_name",
            "ICS_CODE": "ics_code",
            "ICS_NAME": "ics_name",
            "ORG_CODE": "org_code",
            "ORG_NAME": "org_name",
            "MAIN_STAFF_GROUP": "main_staff_group",
            "STAFF_GROUP_1": "staff_group",
            "FTE": "fte",
            "HEADCOUNT": "headcount",
        }
    )
    df = df[df["DATA_LEVEL"] == "Organisation"].copy()
    df["period_month"] = pd.to_datetime(df["period_month"], utc=True)
    df["fte"] = pd.to_numeric(df["fte"], errors="coerce")
    df["headcount"] = pd.to_numeric(df["headcount"], errors="coerce").astype("Int64")
    df = df[(df["period_month"] >= WINDOW_START_DATE) & (df["period_month"] <= WINDOW_END_DATE)]
    return df[
        [
            "org_code",
            "org_name",
            "ics_code",
            "ics_name",
            "nhse_region_code",
            "nhse_region_name",
            "period_month",
            "main_staff_group",
            "staff_group",
            "fte",
            "headcount",
        ]
    ].reset_index(drop=True)


def read_hchs_turnover(path: str | Path) -> pd.DataFrame:
    """Read NHS Workforce Statistics turnover series for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to a turnover CSV from the NHSE Digital release.

    Returns
    -------
    pandas.DataFrame
        Columns: ``nhse_region_code``, ``nhse_region_name``,
        ``period_label`` (string, ``"YYYYMM to YYYYMM"`` as published),
        ``period_end_year`` (Int64, derived from the second YYYYMM token),
        ``type`` (string — denominator / leavers etc.),
        ``main_staff_group``, ``staff_group``, ``headcount`` (Int64),
        ``fte`` (float).
    """
    df = pd.read_csv(path, dtype="string")
    df = df.rename(
        columns={
            "PERIOD": "period_label",
            "TYPE": "type",
            "NHSE_REGION_CODE": "nhse_region_code",
            "NHSE_REGION_NAME": "nhse_region_name",
            "MAIN_STAFF_GROUP": "main_staff_group",
            "STAFF_GROUP": "staff_group",
            "HC": "headcount",
            "FTE": "fte",
        }
    )
    df["period_end_year"] = df["period_label"].str.extract(r"to (\d{4})")[0].astype("Int64")
    df["headcount"] = pd.to_numeric(df["headcount"], errors="coerce").astype("Int64")
    df["fte"] = pd.to_numeric(df["fte"], errors="coerce")
    df = df[df["period_end_year"] >= 2022].reset_index(drop=True)
    return df[
        [
            "nhse_region_code",
            "nhse_region_name",
            "period_label",
            "period_end_year",
            "type",
            "main_staff_group",
            "staff_group",
            "headcount",
            "fte",
        ]
    ]


def read_vacancies(path: str | Path) -> pd.DataFrame:
    """Read NHS Vacancy Statistics — region × sector × quarter long-format panel.

    Parameters
    ----------
    path : str or Path
        Path to ``nhs-vac-stats-apr15-dec25-eng-tables.xlsx``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``nhse_region_name`` (string), ``sector`` (string —
        ``Acute`` / ``Ambulance`` / ``Community`` / ``Mental Health`` /
        ``Specialist``), ``period_quarter`` (string, ``"YYYY/YY QN"``),
        ``vacancy_fte`` (float), ``vacancy_rate`` (float in 0–1).

    Notes
    -----
    The published spreadsheet uses wide format with two stacked tables
    (vacancy FTE and vacancy rate). This reader unpivots both, joins
    them on (region, sector, quarter), and applies the analytical-window
    filter to keep quarters whose calendar year falls within 2021–2026.
    Aggregate "Total" rows (region totals, Grand Total) are excluded.
    """
    raw = pd.read_excel(path, sheet_name="Total 2018 onwards", header=None)
    fte_header = _find_section_row(raw, "Total workforce vacancy FTE")
    rate_header = _find_section_row(raw, "Total workforce % vacancy rate")

    fte = _read_vacancy_block(raw, fte_header, rate_header, value_name="vacancy_fte")
    rate = _read_vacancy_block(raw, rate_header, raw.shape[0], value_name="vacancy_rate")

    if rate["vacancy_rate"].max() > 1:
        rate["vacancy_rate"] = rate["vacancy_rate"] / 100.0

    merged = fte.merge(
        rate,
        on=["nhse_region_name", "sector", "period_quarter"],
        how="inner",
    )
    merged = merged[merged["period_quarter"].str.slice(0, 4).astype(int) >= 2021]
    return merged.reset_index(drop=True)


def _read_vacancy_block(
    raw: pd.DataFrame, header_row: int, end_row: int, value_name: str
) -> pd.DataFrame:
    """Parse one wide vacancy table (FTE or rate) into a tidy long frame."""
    # Header is one row below the section label; first column is "Region".
    columns = raw.iloc[header_row + 1].tolist()
    body = raw.iloc[header_row + 2 : end_row].copy()
    body.columns = columns
    body = body[body["Region"].notna() & body["Sector"].notna()]
    body = body[~body["Sector"].astype(str).str.contains("Total", case=False)]
    long = body.melt(id_vars=["Region", "Sector"], var_name="period_quarter", value_name=value_name)
    long = long.rename(columns={"Region": "nhse_region_name", "Sector": "sector"})
    long["nhse_region_name"] = long["nhse_region_name"].astype("string").ffill()
    # Column labels look like "2021/22 Q1 (Jun-21)"; keep the "YYYY/YY QN" prefix only.
    long["period_quarter"] = (
        long["period_quarter"].astype("string").str.extract(r"(\d{4}/\d{2} Q\d)")[0]
    )
    long = long.dropna(subset=["period_quarter"])
    long[value_name] = pd.to_numeric(long[value_name], errors="coerce")
    return long.dropna(subset=[value_name]).reset_index(drop=True)


def read_earnings(path: str | Path) -> pd.DataFrame:
    """Read NHS Staff Earnings Estimates for the analytical window.

    Parameters
    ----------
    path : str or Path
        Path to a Monthly Earnings CSV (England aggregate; the source
        files do not include a provider breakdown).

    Returns
    -------
    pandas.DataFrame
        Columns: ``period_month`` (Timestamp, UTC, month-end),
        ``staff_group`` (string), ``afc_band`` (string, or
        ``"All AfC bands"`` for the all-staff series),
        ``payment_type`` (string), ``mean_basic_pay_gbp`` (float),
        ``sample_size`` (Int64).
    """
    df = pd.read_csv(path, parse_dates=["DATE"], dtype="string")
    df = df.rename(
        columns={
            "DATE": "period_month",
            "STAFF_GROUP": "staff_group",
            "AFC_BAND": "afc_band",
            "PAYMENT_TYPE": "payment_type",
            "AMOUNT": "mean_basic_pay_gbp",
            "SAMPLE_SIZE": "sample_size",
        }
    )
    if "afc_band" not in df.columns:
        df["afc_band"] = "All AfC bands"
    df["period_month"] = pd.to_datetime(df["period_month"], utc=True)
    df["mean_basic_pay_gbp"] = pd.to_numeric(df["mean_basic_pay_gbp"], errors="coerce")
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce").astype("Int64")
    df = df[(df["period_month"] >= WINDOW_START_DATE) & (df["period_month"] <= WINDOW_END_DATE)]
    return df[
        [
            "period_month",
            "staff_group",
            "afc_band",
            "payment_type",
            "mean_basic_pay_gbp",
            "sample_size",
        ]
    ].reset_index(drop=True)


def read_ae(path: str | Path) -> pd.DataFrame:
    """Read the Monthly A&E Time Series (England-aggregate Activity sheet).

    Parameters
    ----------
    path : str or Path
        Path to ``Monthly-AE-Time-Series-March-YYYY.xls``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``period_month`` (Timestamp, UTC),
        ``attendances_type1`` (float — early-period 7-day means may carry
        fractional values), ``total_attendances`` (float),
        ``emergency_admissions_total`` (float), ``wait_4hr_to_12hr``
        (float), ``wait_over_12hr`` (float), ``pct_met_4hr`` (float).

    Notes
    -----
    The downstream provider-level Day 5 dashboard requires a monthly
    provider breakdown; that is published as a separate CSV per month
    on the NHSE statistical-work-area page. This reader handles the
    England-aggregate time series; provider-level integration will be
    introduced in T3 panel assembly.
    """
    raw = pd.read_excel(path, sheet_name="Activity", header=None)
    header_row = _find_row_any_column(raw, "Period")
    table = pd.read_excel(path, sheet_name="Activity", header=header_row)
    table = table.rename(columns=lambda c: str(c).strip())
    period_col = next(c for c in table.columns if c.lower().startswith("period"))
    type1_col = next(c for c in table.columns if "type 1" in c.lower())
    total_att_col = next(
        c for c in table.columns if "total" in c.lower() and "attendance" in c.lower()
    )
    total_em_col = next(
        c
        for c in table.columns
        if "total emergency admissions" in c.lower() and "via a&e" not in c.lower()
    )
    wait4_col = next(c for c in table.columns if ">4" in c or "greater than 4" in c.lower())
    wait12_col = next(c for c in table.columns if ">12" in c or "greater than 12" in c.lower())

    out = pd.DataFrame(
        {
            "period_month": pd.to_datetime(table[period_col], utc=True, errors="coerce"),
            "attendances_type1": pd.to_numeric(table[type1_col], errors="coerce"),
            "total_attendances": pd.to_numeric(table[total_att_col], errors="coerce"),
            "emergency_admissions_total": pd.to_numeric(table[total_em_col], errors="coerce"),
            "wait_4hr_to_12hr": pd.to_numeric(table[wait4_col], errors="coerce"),
            "wait_over_12hr": pd.to_numeric(table[wait12_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["period_month"]).copy()
    out["pct_met_4hr"] = 1 - (out["wait_4hr_to_12hr"] / out["total_attendances"])
    out = out[
        (out["period_month"] >= WINDOW_START_DATE) & (out["period_month"] <= WINDOW_END_DATE)
    ].reset_index(drop=True)
    return out


def read_rtt(path: str | Path) -> pd.DataFrame:
    """Read a Referral to Treatment full-month extract.

    Parameters
    ----------
    path : str or Path
        Path to a single-month full-extract CSV (e.g.
        ``20260228-RTT-February-2026-full-extract.csv``).

    Returns
    -------
    pandas.DataFrame
        Incomplete pathways aggregated to ``org_code`` × ``treatment_function``:
        ``period_month`` (Timestamp, UTC, month-end), ``org_code``,
        ``treatment_function_code``, ``treatment_function_name``,
        ``n_waiting`` (Int64), ``n_waiting_52plus_weeks`` (Int64).

    Notes
    -----
    Only Part_2 (Incomplete Pathways) rows are retained; commissioner
    breakdowns are aggregated up to the provider level. Total-of-totals
    rows (``Treatment Function Code == "C_999"``) are excluded to keep
    the panel additive across treatment functions.
    """
    df = pd.read_csv(path, dtype="string", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df["RTT Part Type"] == "Part_2"]
    df = df[df["Treatment Function Code"] != "C_999"]

    bucket_re = re.compile(r"^Gt (\d+) To (\d+) Weeks SUM 1$")
    over104_col = next((c for c in df.columns if c.strip() == "Gt 104 Weeks SUM 1"), None)
    weekly_buckets = [c for c in df.columns if bucket_re.match(c)]
    over_52_buckets = [
        c for c in weekly_buckets if int(bucket_re.match(c).group(1)) >= 52  # type: ignore[union-attr]
    ]

    all_bucket_cols = weekly_buckets + ([over104_col] if over104_col else [])
    for col in all_bucket_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("Int64")

    # n_waiting is the row-wise sum of all weekly buckets — the source's
    # "Total" column is sometimes blank or non-additive, so recompute.
    df["n_waiting"] = df[all_bucket_cols].sum(axis=1)
    sum_cols = over_52_buckets + ([over104_col] if over104_col else [])
    df["n_waiting_52plus_weeks"] = df[sum_cols].sum(axis=1)

    period = df["Period"].iloc[0]
    period_month = pd.to_datetime(
        period.replace("RTT-", ""), format="%B-%Y", utc=True
    ) + pd.offsets.MonthEnd(0)

    agg = (
        df.groupby(
            [
                "Provider Org Code",
                "Treatment Function Code",
                "Treatment Function Name",
            ],
            dropna=False,
        )[["n_waiting", "n_waiting_52plus_weeks"]]
        .sum()
        .reset_index()
    )
    agg = agg.rename(
        columns={
            "Provider Org Code": "org_code",
            "Treatment Function Code": "treatment_function_code",
            "Treatment Function Name": "treatment_function_name",
        }
    )
    agg.insert(0, "period_month", period_month)
    agg["org_code"] = agg["org_code"].astype("string").str.strip()
    return agg[
        [
            "period_month",
            "org_code",
            "treatment_function_code",
            "treatment_function_name",
            "n_waiting",
            "n_waiting_52plus_weeks",
        ]
    ].reset_index(drop=True)


def read_ods_trusts(path: str | Path) -> pd.DataFrame:
    """Read the ODS NHS Trusts reference (``etr``) CSV.

    Parameters
    ----------
    path : str or Path
        Path to ``etr-nhs-trusts.csv``. The file is headerless; columns
        follow the ODS Data Search and Export specification for the
        ``etr`` report.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code`` (string), ``org_name`` (string),
        ``nhse_region_code`` (string), ``parent_org_code`` (string),
        ``open_date`` (Timestamp, UTC), ``close_date`` (Timestamp, UTC,
        NaT where the provider is currently open),
        ``is_open`` (bool).
    """
    columns = [
        "org_code",
        "org_name",
        "nhse_region_code",
        "parent_org_code",
        "address_line_1",
        "address_line_2",
        "address_line_3",
        "town",
        "county",
        "postcode",
        "open_date",
        "close_date",
        "reserved_13",
        "reserved_14",
        "reserved_15",
        "reserved_16",
        "reserved_17",
        "telephone",
        "reserved_19",
        "reserved_20",
        "reserved_21",
        "amended_record",
        "reserved_23",
        "current_org_type",
        "reserved_25",
        "reserved_26",
        "reserved_27",
    ]
    df = pd.read_csv(path, header=None, names=columns, dtype="string")
    df["open_date"] = pd.to_datetime(df["open_date"], format="%Y%m%d", utc=True, errors="coerce")
    df["close_date"] = pd.to_datetime(df["close_date"], format="%Y%m%d", utc=True, errors="coerce")
    df["is_open"] = df["close_date"].isna()
    return df[
        [
            "org_code",
            "org_name",
            "nhse_region_code",
            "parent_org_code",
            "open_date",
            "close_date",
            "is_open",
        ]
    ].reset_index(drop=True)
