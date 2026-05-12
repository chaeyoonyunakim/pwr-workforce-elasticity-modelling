"""Provider × financial-year panel assembly.

Combines outputs from :mod:`pwr_elasticity.io` into a single tidy panel
keyed on ``(org_code, financial_year)`` over the analytical window. See
``plan/plan.md`` §T3 for acceptance criteria, in particular merger
handling and the 2022 ICS reorganisation discontinuity.
"""

from __future__ import annotations

import pandas as pd


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
        One row per ``(org_code, financial_year)`` with TAC pay totals,
        annual-mean substantive FTE, vacancy rate, turnover, financial-
        year A&E mean performance, end-of-year RTT stock, and provider
        descriptors (ICS code, NHSE region, provider type).

    Notes
    -----
    Mergers are handled using ``ods.open_date`` and ``ods.close_date``;
    provider-year cells where the organisation existed for less than a
    full financial year are dropped and recorded in the exclusions log
    returned by :func:`provider_exclusions`.
    """
    raise NotImplementedError


def provider_exclusions(
    panel_inputs: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Return the exclusions log produced during panel assembly.

    Parameters
    ----------
    panel_inputs : dict
        Mapping of reader name to its DataFrame, as supplied to
        :func:`build_panel`.

    Returns
    -------
    pandas.DataFrame
        Columns: ``org_code``, ``financial_year``, ``reason``.
        ``reason`` is one of {``"merger_transition"``,
        ``"missing_tac"``, ``"missing_hchs"``, ``"ics_reorganisation"``}.
    """
    raise NotImplementedError
