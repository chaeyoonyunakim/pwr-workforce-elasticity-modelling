"""Source reader contract tests.

These tests pin the public API of :mod:`pwr_elasticity.io`. Each reader
must currently raise :class:`NotImplementedError`; that constraint will
be replaced with schema and row-count assertions in T2.
"""

from __future__ import annotations

import pytest

from pwr_elasticity import io


def test_module_exposes_expected_readers() -> None:
    expected = {
        "read_tac",
        "read_hchs_staff_in_post",
        "read_hchs_turnover",
        "read_vacancies",
        "read_earnings",
        "read_ae",
        "read_rtt",
        "read_ods_trusts",
    }
    assert expected.issubset(dir(io))


@pytest.mark.parametrize(
    "reader_name",
    [
        "read_tac",
        "read_hchs_staff_in_post",
        "read_hchs_turnover",
        "read_vacancies",
        "read_earnings",
        "read_ae",
        "read_rtt",
        "read_ods_trusts",
    ],
)
def test_reader_is_currently_a_stub(reader_name: str) -> None:
    reader = getattr(io, reader_name)
    with pytest.raises(NotImplementedError):
        reader("does/not/matter")
