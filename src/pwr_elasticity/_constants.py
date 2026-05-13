"""Shared constants for the analytical pipeline.

Centralising window boundaries and TAC SubCode mappings here keeps the
readers in :mod:`pwr_elasticity.io` free of magic numbers.
"""

from __future__ import annotations

# Analytical window — see plan/plan.md §3 and data/DATA_DICTIONARY.md §1.
WINDOW_START_FY: str = "2021/22"
WINDOW_END_FY: str = "2025/26"
WINDOW_START_DATE: str = "2021-04-01"  # Start of FY 2021/22
WINDOW_END_DATE: str = "2026-03-31"  # End of FY 2025/26

# TAC09 Staff schedule — published "All data" sheet of each annual XLSX.
# Each provider × column-suffix × row carries a £'000 value.
#
# MainCode pattern: ``A09{CY|PY}{NN}{suffix}`` where
#   - CY = current year, PY = prior year
#   - NN = column index within the TAC09 schedule (01, 13, 14, ...)
#   - suffix = (none) = Total, P = Permanent staff, O = Other staff
#       Other staff = Bank + Agency + Contract for Services (combined).
#       TAC does **not** publish the Bank / Agency split separately.
#
# SubCode STA0366 is the published net employee benefits expenditure line —
# the canonical bottom-line pay figure for each (CY, column-suffix) cell.
TAC_WORKSHEET_STAFF: str = "TAC09 Staff"
TAC_MAINCODE_TOTAL_CY: str = "A09CY01"  # Total CY pay
TAC_MAINCODE_PERMANENT_CY: str = "A09CY01P"  # Permanent (substantive) CY pay
TAC_MAINCODE_OTHER_CY: str = "A09CY01O"  # Other (bank + agency + contract) CY pay
# Net-pay subcode preferences. The 2022/23 and later TAC vintages publish
# STA0366 (Net employee benefits expenditure, excluding capitalised costs).
# Earlier vintages (e.g. 2019/20 published April 2021) stop at STA0360
# (Total employee benefits costs, excluding capitalised costs); the gap
# between the two is capitalised employee benefits expenditure (STA0365),
# which is tiny relative to substantive + other staff pay. Readers should
# try these subcodes in order and use the first one that is populated.
TAC_SUBCODE_NET_PAY_CANDIDATES: tuple[str, ...] = ("STA0366", "STA0360")

# Retained for backward compatibility — first preference subcode.
TAC_SUBCODE_NET_PAY: str = TAC_SUBCODE_NET_PAY_CANDIDATES[0]

# TAC values are reported in £ thousands; multiplier to convert to £.
TAC_THOUSANDS_TO_GBP: int = 1_000
