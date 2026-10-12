"""The exchange-status text is byte-identical to what it was before the report renderer (`EPIC-038B`).

The fixtures in `golden/` were written from `format_exchange_connection_status`
and `format_order_preview` as they were **before** their string building moved
into `TextReportRenderer`. A moved space, a lost trailing blank or a changed
glyph fails here with the case's name; re-recording a fixture to make it pass
is the failure this test exists to make visible in a diff.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_formatter import (
    format_exchange_connection_status,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_formatter import (
    format_order_preview,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    EXCHANGE_STATUS_CASES,
    GOLDEN_DIR,
    ORDER_PREVIEW_CASES,
    golden_text,
)


@pytest.mark.parametrize("name", sorted(EXCHANGE_STATUS_CASES))
def test_exchange_status_text_is_unchanged(name: str) -> None:
    text = format_exchange_connection_status(EXCHANGE_STATUS_CASES[name])

    assert text == golden_text("exchange-status", name)


@pytest.mark.parametrize("name", sorted(ORDER_PREVIEW_CASES))
def test_order_preview_text_is_unchanged(name: str) -> None:
    text = format_order_preview(ORDER_PREVIEW_CASES[name])

    assert text == golden_text("order-preview", name)


def test_golden_cases_cover_every_failure_kind() -> None:
    """A kind added without a golden case would ship unpinned."""
    covered = {
        status.failure
        for status in EXCHANGE_STATUS_CASES.values()
        if status.failure is not None
    }

    assert covered == set(ConnectionFailureKind)


def test_every_fixture_belongs_to_a_case() -> None:
    """An orphaned fixture is a case someone deleted without deleting its proof."""
    expected = {f"exchange-status__{n}.txt" for n in EXCHANGE_STATUS_CASES} | {
        f"order-preview__{n}.txt" for n in ORDER_PREVIEW_CASES
    }

    assert {p.name for p in GOLDEN_DIR.iterdir()} == expected
