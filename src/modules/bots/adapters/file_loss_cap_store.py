"""The loss cap's record as a JSON file beside the bots' folder (`EPIC-026L`).

Written by write-temp-then-rename, as the applied plan is (`file_applied_plan_store.py`), so a
reader sees the old record or the new one and never half of one. Read strictly: a record this
build cannot read is refused with a sentence naming the problem and **none of the content**; the
cap then treats itself as tripped (`LossCapTripReason.RECORD_UNREADABLE`), because a file that may
have said "tripped" and cannot be read must not be read as "not tripped".

@par The document
  schema   "sew.loss-cap-record/1"
  day      the UTC day the figures belong to, `YYYY-MM-DD`
  figures  bot id -> {run_started_at (ISO 8601 with a zone, or null), baseline, last, banked}
           (decimals as text)
  trip     null, or {reason, at, day, loss (text or null), figure, detail}
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    ILossCapStore,
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

RECORD_SCHEMA = "sew.loss-cap-record/1"
_FIGURE_FIELDS = {"run_started_at", "baseline", "last", "banked"}
_TRIP_FIELDS = {"reason", "at", "day", "loss", "figure", "detail"}


class FileLossCapStore(ILossCapStore):
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> LossCapRecord | None:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as exc:
            raise LossCapRecordUnreadableError(
                f"the loss-cap record {self._path.name} cannot be read ({type(exc).__name__})"
            ) from None
        return _parse(text, self._path.name)

    def write(self, record: LossCapRecord) -> None:
        document = {
            "schema": RECORD_SCHEMA,
            "day": record.ledger.day.isoformat(),
            "figures": {
                bot_id: {
                    "run_started_at": (
                        None
                        if figure.run_started_at is None
                        else figure.run_started_at.isoformat()
                    ),
                    "baseline": str(figure.baseline),
                    "last": str(figure.last),
                    "banked": str(figure.banked),
                }
                for bot_id, figure in sorted(record.ledger.figures.items())
            },
            "trip": None if record.trip is None else _trip_document(record.trip),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + ".tmp")
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self._path)


def _trip_document(trip: LossCapTrip) -> dict[str, str | None]:
    return {
        "reason": trip.reason.value,
        "at": trip.at.isoformat(),
        "day": trip.day.isoformat(),
        "loss": None if trip.loss is None else str(trip.loss),
        "figure": trip.figure,
        "detail": trip.detail,
    }


def _parse(text: str, file_name: str) -> LossCapRecord:
    def refuse(why: str) -> LossCapRecordUnreadableError:
        return LossCapRecordUnreadableError(
            f"the loss-cap record {file_name} is not one this build reads: {why}; "
            "acknowledge the cap (`bot loss-cap-ack`) to replace it"
        )

    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        raise refuse("it is not valid JSON") from None
    if not isinstance(raw, dict) or set(raw) != {"schema", "day", "figures", "trip"}:
        raise refuse("it is not an object of schema, day, figures and trip")
    if raw["schema"] != RECORD_SCHEMA:
        raise refuse("its schema is not the one this build writes")
    try:
        day = date.fromisoformat(_text(raw["day"]))
        figures = _figures(raw["figures"])
        trip = None if raw["trip"] is None else _trip(raw["trip"])
    except (TypeError, ValueError, InvalidOperation):
        raise refuse("a field is missing, mistyped or not a date or a number") from None
    return LossCapRecord(LossCapLedger(day, figures), trip)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("text expected")
    return value


def _moment(value: object) -> datetime:
    moment = datetime.fromisoformat(_text(value))
    if moment.tzinfo is None:
        raise ValueError("a moment needs a time zone")
    return moment


def _figures(raw: object) -> dict[str, BotDayFigure]:
    if not isinstance(raw, dict):
        raise TypeError("figures is an object")
    figures: dict[str, BotDayFigure] = {}
    for bot_id, entry in raw.items():
        if not isinstance(entry, dict) or set(entry) != _FIGURE_FIELDS:
            raise TypeError("a figure has exactly its four fields")
        started = entry["run_started_at"]
        figures[_text(bot_id)] = BotDayFigure(
            None if started is None else _moment(started),
            _decimal(entry["baseline"]),
            _decimal(entry["last"]),
            _decimal(entry["banked"]),
        )
    return figures


def _decimal(value: object) -> Decimal:
    number = Decimal(_text(value))
    if not number.is_finite():
        raise ValueError("a number is finite")
    return number


def _trip(raw: object) -> LossCapTrip:
    if not isinstance(raw, dict) or set(raw) != _TRIP_FIELDS:
        raise TypeError("a trip has exactly its six fields")
    loss = raw["loss"]
    return LossCapTrip(
        LossCapTripReason(_text(raw["reason"])),
        _moment(raw["at"]),
        date.fromisoformat(_text(raw["day"])),
        None if loss is None else _decimal(loss),
        _text(raw["figure"]),
        _text(raw["detail"]),
    )
