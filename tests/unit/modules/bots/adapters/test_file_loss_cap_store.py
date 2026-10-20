"""`EPIC-026L` — the loss cap's record on disk: exact on the way out, strict and secret-free on the way in."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.file_loss_cap_store import (
    RECORD_SCHEMA,
    FileLossCapStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    LossCapRecordUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    BotDayFigure,
    LossCapLedger,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapRecord,
    LossCapTrip,
    LossCapTripReason,
)

DAY = date(2026, 10, 20)
RUN = datetime(2026, 10, 20, 2, 0, tzinfo=UTC)


def _record(*, tripped: bool) -> LossCapRecord:
    ledger = LossCapLedger(
        DAY,
        {
            "aaa111": BotDayFigure(
                RUN, Decimal(0), Decimal("-312.456789"), Decimal("-1.5")
            ),
            "bbb222": BotDayFigure(None, Decimal(7), Decimal(7), Decimal(0)),
        },
    )
    trip = LossCapTrip(
        LossCapTripReason.LOSS_REACHED,
        RUN,
        DAY,
        Decimal("500.1"),
        "500 USDT",
        "reached",
    )
    return LossCapRecord(ledger, trip if tripped else None)


@pytest.mark.parametrize("tripped", [False, True], ids=["open", "tripped"])
def test_a_record_survives_the_round_trip_exactly(
    tmp_path: Path, tripped: bool
) -> None:
    store = FileLossCapStore(tmp_path / "loss_cap.json")
    store.write(_record(tripped=tripped))

    assert store.read() == _record(tripped=tripped)


def test_no_file_is_no_record(tmp_path: Path) -> None:
    assert FileLossCapStore(tmp_path / "loss_cap.json").read() is None


def test_a_second_write_replaces_the_first_and_leaves_no_temporary_file(
    tmp_path: Path,
) -> None:
    store = FileLossCapStore(tmp_path / "state" / "loss_cap.json")
    store.write(_record(tripped=True))
    store.write(_record(tripped=False))

    assert store.read() == _record(tripped=False)
    assert [p.name for p in (tmp_path / "state").iterdir()] == ["loss_cap.json"]


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        "[]",
        json.dumps(
            {
                "schema": "sew.loss-cap-record/2",
                "day": "2026-10-20",
                "figures": {},
                "trip": None,
            }
        ),
        json.dumps(
            {"schema": RECORD_SCHEMA, "day": "yesterday", "figures": {}, "trip": None}
        ),
        json.dumps({"schema": RECORD_SCHEMA, "day": "2026-10-20", "figures": {}}),
        json.dumps(
            {
                "schema": RECORD_SCHEMA,
                "day": "2026-10-20",
                "figures": {"a": {"last": "1"}},
                "trip": None,
            }
        ),
        json.dumps(
            {
                "schema": RECORD_SCHEMA,
                "day": "2026-10-20",
                "figures": {
                    "a": {
                        "run_started_at": None,
                        "baseline": "NaN",
                        "last": "0",
                        "banked": "0",
                    }
                },
                "trip": None,
            }
        ),
        json.dumps(
            {
                "schema": RECORD_SCHEMA,
                "day": "2026-10-20",
                "figures": {},
                "trip": {
                    "reason": "nonsense",
                    "at": "2026-10-20T02:00:00+00:00",
                    "day": "2026-10-20",
                    "loss": None,
                    "figure": "",
                    "detail": "",
                },
            }
        ),
    ],
    ids=[
        "text",
        "list",
        "schema",
        "day",
        "no trip key",
        "figure fields",
        "nan",
        "reason",
    ],
)
def test_a_record_this_build_cannot_read_is_refused_not_guessed(
    tmp_path: Path, text: str
) -> None:
    path = tmp_path / "loss_cap.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(LossCapRecordUnreadableError):
        FileLossCapStore(path).read()


def test_the_refusal_names_the_file_and_never_the_content(tmp_path: Path) -> None:
    path = tmp_path / "loss_cap.json"
    path.write_text("api-secret-do-not-echo", encoding="utf-8")

    with pytest.raises(LossCapRecordUnreadableError) as refused:
        FileLossCapStore(path).read()

    assert "loss_cap.json" in str(refused.value)
    assert "api-secret-do-not-echo" not in str(refused.value)
