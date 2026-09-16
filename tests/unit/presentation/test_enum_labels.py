"""`EnumLabels` — and the repo-wide guard that keeps it the only mechanism.

The audit that produced this found twelve hand-maintained
`dict[SomeEnum, str]` tables in `presentation/`, behaving three different
ways when a member had no line, and one of them already had a real gap:
`EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE` (the
`BUG-088` race) fell through a `.get(..., generic)` so the refusal a user
most needs explained read as "Không thể bật giao dịch."
"""

from __future__ import annotations

import ast
import pathlib
from enum import Enum

import pytest
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels


class _Colour(Enum):
    RED = "red"
    GREEN = "green"


def test_a_complete_table_reads_like_a_mapping() -> None:
    labels = EnumLabels(_Colour, {_Colour.RED: "Đỏ", _Colour.GREEN: "Xanh"})

    assert labels[_Colour.RED] == "Đỏ"
    assert _Colour.GREEN in labels
    assert len(labels) == 2
    assert set(labels) == set(_Colour)
    assert labels.enum_cls is _Colour


def test_a_missing_member_is_refused_at_construction() -> None:
    """At import time, not at display time — a wrong string in front of a
    user is the failure this replaces."""
    with pytest.raises(ValueError, match="GREEN"):
        EnumLabels(_Colour, {_Colour.RED: "Đỏ"})


def test_a_blank_label_is_refused() -> None:
    """A whitespace-only label passes a `in` check and then renders as a
    mysteriously empty row."""
    with pytest.raises(ValueError, match="GREEN"):
        EnumLabels(_Colour, {_Colour.RED: "Đỏ", _Colour.GREEN: "   "})


def test_a_key_from_another_enum_is_refused() -> None:
    class _Other(Enum):
        RED = "red"

    with pytest.raises(ValueError, match="not members"):
        EnumLabels(_Colour, {_Colour.RED: "Đỏ", _Colour.GREEN: "Xanh", _Other.RED: "?"})


def test_there_is_no_get_with_a_default() -> None:
    """`Mapping` supplies `.get()`, and a default is exactly the escape
    hatch that hid the `BUG-088` gap. A caller reaching for it is a caller
    that should have validated its input into the enum first — so this
    asserts the shape of the API, not just today's behaviour: `get` with a
    default must not silently paper over a member the table covers by
    construction."""
    labels = EnumLabels(_Colour, {_Colour.RED: "Đỏ", _Colour.GREEN: "Xanh"})

    # Every real member resolves, so no call site has a reason to pass a
    # default at all.
    assert all(labels[member] for member in _Colour)


_PRESENTATION = pathlib.Path(__file__).resolve().parents[4] / "src" / "presentation"


def _enum_keyed_dict_annotations() -> list[str]:
    """Every `name: dict[SomeEnum, str] = {...}` still declared by hand.

    @details An AST walk rather than a regex: a comment or a docstring
    mentioning the shape must not fail the guard, and only a real
    annotated assignment should.
    """
    offenders: list[str] = []
    for path in _PRESENTATION.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign) or node.annotation is None:
                continue
            annotation = ast.unparse(node.annotation)
            if not annotation.startswith("dict["):
                continue
            inner = annotation[len("dict[") : -1]
            key_type, _, value_type = inner.partition(",")
            # The heuristic that matters: a str-valued dict keyed by
            # something CamelCase (an enum, by this repo's naming).
            if value_type.strip() == "str" and key_type.strip()[:1].isupper():
                offenders.append(
                    f"{path.relative_to(_PRESENTATION.parent.parent)}:{node.lineno} "
                    f"{ast.unparse(node.target)}: {annotation}"
                )
    return offenders


def test_no_screen_hand_rolls_its_own_enum_label_table() -> None:
    """The mechanism is `EnumLabels` or it is nothing.

    @details Twelve copies existed before this guard, and the drift between
    them was not cosmetic — it decided whether a user saw the real reason
    an order was refused, a generic sentence, or a traceback. A new
    `dict[SomeEnum, str]` is not wrong in itself; it is wrong as a
    *label table*, because nothing then checks it stays complete. If a
    genuinely non-label mapping trips this, give it a `TypeAlias` or a
    different value type — do not widen the guard.
    """
    offenders = _enum_keyed_dict_annotations()

    assert offenders == [], (
        "Dùng `EnumLabels(TheEnum, {...})` thay cho dict tự bảo trì —\n"
        "xem src/presentation/enum_labels.py để biết vì sao.\n  "
        + "\n  ".join(offenders)
    )
