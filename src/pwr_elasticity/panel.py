"""Provider × financial-year panel assembly.

Combines outputs from :mod:`pwr_elasticity.io` into a single tidy panel
keyed on ``(org_code, financial_year)`` over the analytical window. See
``plan/plan.md`` §T3 for acceptance criteria; merger handling and the
2022 ICS reorganisation are explicit decisions captured in the
``provider_exclusions`` log returned alongside the panel.
"""

from __future__ import annotations

import pandas as pd

# Financial-year start / end months in the UK NHS calendar.
FY_START_MONTH: int = 4
FY_END_MONTH: int = 3

# Cohort identifiers used in turnover-rate computation.
TURNOVER_DENOMINATOR_TYPE: str = "Denominator at end of period"
TURNOVER_LEAVERS_TYPE: str = "Leavers"

# Sentinel category used when the source data does not break down by
# staff group (e.g. when only the "All staff groups" total is requested).
ALL_STAFF_GROUPS_LABEL: str = "All staff groups"


def build_panel(
    tac: pd.DataFrame,
    hchs: pd.DataFrame,
    turnover: pd.DataFrame,
    vacancies: pd.DataFrame,
    ae: pd.DataFrame,
    rtt: pd.DataFrame,
    ods: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble the provider × financial-year analytical panel.

    Parameters
    ----------
    tac, hchs, turnover, vacancies, ae, rtt, ods : pandas.DataFrame
        Outputs of the corresponding :mod:`pwr_elasticity.io` readers,
        each restricted to the analytical window.

    Returns
    -------
    pandas.DataFrame
        One row per ``(org_code, financial_year)`` with columns:

        - ``org_code`` (string), ``org_name`` (string),
          ``financial_year`` (string ``"YYYY/YY"``);
        - ``ics_code`` (string), ``nhse_region_code`` (string);
        - TAC pay split: ``substantive_pay_gbp``, ``other_staff_pay_gbp``,
          ``total_pay_gbp``;
        - Workforce stock: ``staff_in_post_fte`` (annual mean,
          ``All staff groups``);
        - Operational pressure: ``vacancy_rate`` (within-FY mean,
          provider-region × all-sector aggregate), ``turnover_rate``
          (region × All staff group annual rate), ``pct_met_4hr``
          (FY mean, England aggregate broadcast),
          ``ae_total_attendances`` (FY total, England aggregate
          broadcast);
        - Elective backlog: ``rtt_n_waiting``,
          ``rtt_n_waiting_52plus_weeks`` (latest FY-end snapshot
          available; NaN where no in-FY RTT extract exists).

    Notes
    -----
    The panel is the cross-product of the TAC provider set with the
    in-window financial years. Joins are left-outer from TAC so the panel
    coverage matches the audited financial dataset.
    Provider mergers and the 2022 ICS reorganisation are recorded in the
    exclusions log returned by :func:`provider_exclusions`; cells that
    cannot be safely populated are left as NaN here rather than dropped,
    so downstream code (T4 features) can choose its own exclusion
    threshold.
    """
    if tac.empty:
        return _empty_panel()

    # Drop TAC rows whose organisation name did not resolve to an org_code
    # (typically aggregate rows like national totals). The remaining
    # frame guarantees the (org_code, financial_year) contract.
    panel = tac.dropna(subset=["org_code"]).copy()

    # Region must be attached before vacancy / turnover joins so those
    # broadcasts honour the provider's geography.
    panel = _attach_ods_metadata(panel, ods)
    panel = _attach_hchs_workforce(panel, hchs)
    panel = _attach_vacancies(panel, vacancies)
    panel = _attach_turnover(panel, turnover)
    panel = _attach_ae(panel, ae)
    panel = _attach_rtt(panel, rtt)

    return panel.sort_values(["financial_year", "org_code"]).reset_index(drop=True)


def provider_exclusions(panel_inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return the exclusions log derived from the input frames.

    Parameters
    ----------
    panel_inputs : dict
        Mapping of reader name to its DataFrame. Expected keys:
        ``"tac"``, ``"hchs"``, ``"ods"``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code``, ``financial_year``, ``reason``.
        ``reason`` is one of:

        - ``"merger_transition"`` — provider open or closed within the
          financial year (per ``ods.open_date`` / ``ods.close_date``);
        - ``"missing_hchs"`` — TAC reports the provider for that FY but
          no HCHS Staff-in-Post row exists in the FY window;
        - ``"ics_reorganisation"`` — provider's ICS code changes
          mid-FY (the July-2022 reorganisation cohort).
    """
    tac = panel_inputs.get("tac", pd.DataFrame())
    hchs = panel_inputs.get("hchs", pd.DataFrame())
    ods = panel_inputs.get("ods", pd.DataFrame())

    rows: list[dict[str, str]] = []

    if not tac.empty and not ods.empty:
        rows.extend(_detect_merger_exclusions(tac, ods))
    if not tac.empty:
        rows.extend(_detect_missing_hchs(tac, hchs))
        rows.extend(_detect_ics_reorganisation(tac, hchs))

    if not rows:
        return pd.DataFrame(columns=["org_code", "financial_year", "reason"])
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


# ---------------------------------------------------------------------------
# Internal helpers — financial-year arithmetic
# ---------------------------------------------------------------------------


def _financial_year_to_start(fy: str) -> pd.Timestamp:
    """Map ``"YYYY/YY"`` to the FY start Timestamp (1 April of YYYY, UTC)."""
    start_year = int(fy.split("/")[0])
    return pd.Timestamp(year=start_year, month=FY_START_MONTH, day=1, tz="UTC")


def _financial_year_to_end(fy: str) -> pd.Timestamp:
    """Map ``"YYYY/YY"`` to the FY end Timestamp (31 March of YYYY+1, UTC)."""
    start_year = int(fy.split("/")[0])
    return pd.Timestamp(year=start_year + 1, month=FY_END_MONTH, day=31, tz="UTC")


def _date_to_financial_year(ts: pd.Timestamp) -> str:
    """Map a date to its ``"YYYY/YY"`` financial year label."""
    if pd.isna(ts):
        return ""
    year = ts.year if ts.month >= FY_START_MONTH else ts.year - 1
    return f"{year}/{(year + 1) % 100:02d}"


def _quarter_to_financial_year(period_quarter: str) -> str:
    """Map ``"YYYY/YY QN"`` to the matching ``"YYYY/YY"`` FY label."""
    return period_quarter.split(" ")[0]


def _empty_panel() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "org_code",
            "org_name",
            "financial_year",
            "ics_code",
            "nhse_region_code",
            "substantive_pay_gbp",
            "other_staff_pay_gbp",
            "total_pay_gbp",
            "staff_in_post_fte",
            "vacancy_rate",
            "turnover_rate",
            "pct_met_4hr",
            "ae_total_attendances",
            "rtt_n_waiting",
            "rtt_n_waiting_52plus_weeks",
        ]
    )


# ---------------------------------------------------------------------------
# Internal helpers — joins
# ---------------------------------------------------------------------------


def _attach_hchs_workforce(panel: pd.DataFrame, hchs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate HCHS Staff-in-Post to FY mean FTE and attach to the panel."""
    if hchs.empty:
        for col in ("staff_in_post_fte", "ics_code"):
            panel[col] = pd.NA
        return panel

    workforce = hchs[hchs["staff_group"] == ALL_STAFF_GROUPS_LABEL].copy()
    workforce = workforce[workforce["main_staff_group"] == ALL_STAFF_GROUPS_LABEL]
    workforce["financial_year"] = workforce["period_month"].map(_date_to_financial_year)

    annual = (
        workforce.groupby(["org_code", "financial_year"], dropna=False)
        .agg(staff_in_post_fte=("fte", "mean"), ics_code=("ics_code", "first"))
        .reset_index()
    )
    return panel.merge(annual, on=["org_code", "financial_year"], how="left")


def _attach_vacancies(panel: pd.DataFrame, vacancies: pd.DataFrame) -> pd.DataFrame:
    """Attach within-FY mean vacancy rate from the region × sector × quarter panel.

    The published vacancy series carries an NHSE region *name*; the panel
    uses the ODS region *code* on its left-hand side. We translate names
    to codes via :func:`_NHSE_REGION_NAME_TO_CODE` before joining so the
    join key is consistent.
    """
    if vacancies.empty:
        panel["vacancy_rate"] = pd.NA
        return panel

    vac = vacancies.copy()
    vac["financial_year"] = vac["period_quarter"].map(_quarter_to_financial_year)
    vac["nhse_region_code"] = vac["nhse_region_name"].map(_NHSE_REGION_NAME_TO_CODE)
    annual = (
        vac.dropna(subset=["nhse_region_code"])
        .groupby(["nhse_region_code", "financial_year"], dropna=False)["vacancy_rate"]
        .mean()
        .reset_index()
    )
    return panel.merge(annual, on=["nhse_region_code", "financial_year"], how="left")


# NHSE region-name to region-code lookup, derived from the ODS reference
# (etr) data. The vacancy series labels regions with their friendly name;
# everywhere else the codebase joins on the code.
_NHSE_REGION_NAME_TO_CODE: dict[str, str] = {
    "East of England": "Y61",
    "London": "Y56",
    "Midlands": "Y60",
    "North East and Yorkshire": "Y63",
    "North West": "Y62",
    "South East": "Y59",
    "South West": "Y58",
}


def _attach_turnover(panel: pd.DataFrame, turnover: pd.DataFrame) -> pd.DataFrame:
    """Compute leaver rate at region × FY × All-staff-groups and broadcast.

    Joins on (``nhse_region_code``, ``financial_year``) so each provider
    inherits its region's annual turnover. Providers with no region code
    in ODS receive NaN.
    """
    if turnover.empty:
        panel["turnover_rate"] = pd.NA
        return panel

    base = turnover[turnover["staff_group"] == ALL_STAFF_GROUPS_LABEL].copy()
    if base.empty:
        panel["turnover_rate"] = pd.NA
        return panel

    pivot = base.pivot_table(
        index=["nhse_region_code", "period_end_year"],
        columns="type",
        values="headcount",
        aggfunc="sum",
    ).reset_index()

    if TURNOVER_LEAVERS_TYPE not in pivot.columns or TURNOVER_DENOMINATOR_TYPE not in pivot.columns:
        panel["turnover_rate"] = pd.NA
        return panel

    pivot["turnover_rate"] = pivot[TURNOVER_LEAVERS_TYPE].astype("Float64") / pivot[
        TURNOVER_DENOMINATOR_TYPE
    ].astype("Float64")
    pivot["financial_year"] = (pivot["period_end_year"].astype("Int64") - 1).astype("string") + (
        "/" + (pivot["period_end_year"].astype("Int64") % 100).astype("string").str.zfill(2)
    )
    return panel.merge(
        pivot[["nhse_region_code", "financial_year", "turnover_rate"]],
        on=["nhse_region_code", "financial_year"],
        how="left",
    )


def _attach_ae(panel: pd.DataFrame, ae: pd.DataFrame) -> pd.DataFrame:
    """Attach FY-mean A&E performance (England aggregate broadcast)."""
    if ae.empty:
        panel["pct_met_4hr"] = pd.NA
        panel["ae_total_attendances"] = pd.NA
        return panel

    ae_fy = ae.copy()
    ae_fy["financial_year"] = ae_fy["period_month"].map(_date_to_financial_year)
    annual = (
        ae_fy.groupby("financial_year")
        .agg(
            pct_met_4hr=("pct_met_4hr", "mean"),
            ae_total_attendances=("total_attendances", "sum"),
        )
        .reset_index()
    )
    return panel.merge(annual, on="financial_year", how="left")


def _attach_rtt(panel: pd.DataFrame, rtt: pd.DataFrame) -> pd.DataFrame:
    """Attach the latest in-FY RTT stock by provider (sum across treatment functions)."""
    if rtt.empty:
        panel["rtt_n_waiting"] = pd.NA
        panel["rtt_n_waiting_52plus_weeks"] = pd.NA
        return panel

    rtt_fy = rtt.copy()
    rtt_fy["financial_year"] = rtt_fy["period_month"].map(_date_to_financial_year)
    provider_fy = (
        rtt_fy.groupby(["org_code", "financial_year"])
        .agg(
            rtt_n_waiting=("n_waiting", "sum"),
            rtt_n_waiting_52plus_weeks=("n_waiting_52plus_weeks", "sum"),
        )
        .reset_index()
    )
    return panel.merge(provider_fy, on=["org_code", "financial_year"], how="left")


def _attach_ods_metadata(panel: pd.DataFrame, ods: pd.DataFrame) -> pd.DataFrame:
    """Attach NHSE region code from the ODS reference.

    The ``etr`` extract does not carry a region *name* — only the code —
    so downstream code that needs a human-readable name should look it up
    against :data:`_NHSE_REGION_NAME_TO_CODE`. Region name is omitted
    here rather than fabricated.
    """
    if ods.empty:
        panel["nhse_region_code"] = pd.NA
        return panel
    keep = ods[["org_code", "nhse_region_code"]].copy()
    return panel.merge(keep, on="org_code", how="left")


# ---------------------------------------------------------------------------
# Internal helpers — exclusions
# ---------------------------------------------------------------------------


def _detect_merger_exclusions(tac: pd.DataFrame, ods: pd.DataFrame) -> list[dict[str, str]]:
    """Flag provider-FY cells where the org opened or closed within the financial year."""
    out: list[dict[str, str]] = []
    ods_lookup = ods.set_index("org_code")[["open_date", "close_date"]]
    for _, row in tac.iterrows():
        org = row["org_code"]
        if pd.isna(org) or org not in ods_lookup.index:
            continue
        open_date = ods_lookup.loc[org, "open_date"]
        close_date = ods_lookup.loc[org, "close_date"]
        fy_start = _financial_year_to_start(row["financial_year"])
        fy_end = _financial_year_to_end(row["financial_year"])
        opened_mid_fy = pd.notna(open_date) and fy_start <= open_date <= fy_end
        closed_mid_fy = pd.notna(close_date) and fy_start <= close_date <= fy_end
        if opened_mid_fy or closed_mid_fy:
            out.append(
                {
                    "org_code": org,
                    "financial_year": row["financial_year"],
                    "reason": "merger_transition",
                }
            )
    return out


def _detect_missing_hchs(tac: pd.DataFrame, hchs: pd.DataFrame) -> list[dict[str, str]]:
    """Flag provider-FY cells where TAC has data but no HCHS workforce row exists."""
    if hchs.empty:
        return [
            {
                "org_code": str(r["org_code"]),
                "financial_year": str(r["financial_year"]),
                "reason": "missing_hchs",
            }
            for _, r in tac.iterrows()
            if pd.notna(r["org_code"])
        ]

    hchs_with_fy = hchs.copy()
    hchs_with_fy["financial_year"] = hchs_with_fy["period_month"].map(_date_to_financial_year)
    seen = set(zip(hchs_with_fy["org_code"], hchs_with_fy["financial_year"], strict=False))
    return [
        {
            "org_code": str(r["org_code"]),
            "financial_year": str(r["financial_year"]),
            "reason": "missing_hchs",
        }
        for _, r in tac.iterrows()
        if pd.notna(r["org_code"]) and (str(r["org_code"]), str(r["financial_year"])) not in seen
    ]


def _detect_ics_reorganisation(tac: pd.DataFrame, hchs: pd.DataFrame) -> list[dict[str, str]]:
    """Flag provider-FY cells where the ICS code is non-unique within the FY (reorganisation)."""
    if hchs.empty:
        return []

    hchs_with_fy = hchs.copy()
    hchs_with_fy["financial_year"] = hchs_with_fy["period_month"].map(_date_to_financial_year)
    grouped = (
        hchs_with_fy.groupby(["org_code", "financial_year"])["ics_code"]
        .nunique(dropna=True)
        .reset_index(name="n_ics")
    )
    flagged = grouped[grouped["n_ics"] > 1]
    return [
        {
            "org_code": str(r["org_code"]),
            "financial_year": str(r["financial_year"]),
            "reason": "ics_reorganisation",
        }
        for _, r in flagged.iterrows()
    ]
