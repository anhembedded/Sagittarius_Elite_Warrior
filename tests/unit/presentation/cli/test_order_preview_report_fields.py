"""`order-preview --json` keeps the field names scripts read (`EPIC-038B`)."""

from __future__ import annotations

import json

from Sagittarius_Elite_Warrior.src.presentation.cli.order_preview_formatter import (
    order_preview_report,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    ORDER_PREVIEW_CASES,
)

_PINNED_FIELDS = {
    "order",
    "raw_quantity",
    "estimated_notional",
    "min_notional",
    "step_size",
    "notional_check",
}
_PINNED_ORDER_FIELDS = {
    "client_order_id",
    "symbol",
    "side",
    "order_type",
    "quantity",
    "status",
    "price",
    "stop_price",
    "time_in_force",
    "reduce_only",
}


def test_order_preview_json_has_the_pinned_fields() -> None:
    report = order_preview_report(ORDER_PREVIEW_CASES["ready_rounded_down"])

    assert report.schema == "sew.order-preview/1"
    assert set(report.payload) == _PINNED_FIELDS
    order = report.payload["order"]
    assert isinstance(order, dict)
    assert set(order) == _PINNED_ORDER_FIELDS


def test_order_preview_payload_is_plain_json() -> None:
    payload = order_preview_report(ORDER_PREVIEW_CASES["rejected_min_notional"]).payload

    assert json.loads(json.dumps(payload)) == payload
