# qml/kit — shared QML primitives

Four components from a design-system spec the user provided 2026-08-30:
`PanelHeader`, `Button`, `LogPanel`, `DialogShell`. Each replaces a pattern
every widget built so far this session (`SymbolPicker`, `DatabaseStatusTable`,
`KlineInspectorTable`, ...) was hand-rolling slightly differently — the
spec's own annotations name the resulting drift ("Was: accent bar on some,
none on others; three label sizes", "Was: gold fill, green outline, red
fill and bare text all on one screen").

**Pure QML, no Python VM for any of the four** — `qml-rule.md` §1.3: a
component with nothing to derive, only properties a caller sets, does not
get one. `__init__.py` exists only so `tests/` resolves to a unique package
path, not to re-export anything.

## Deliberately a NEW design, not a QML port of `kit/style.py`

Investigated first (`kit/overlay.py`, `kit/style.py`,
`kit/controls/styled_button.py`, `components/app_log_panel.py`) so this
would be built from real values, not guesses. What came back: the
QtWidgets `kit/` package does **not** already implement this spec — it has
the same inconsistency the spec is correcting:

- **Buttons**: `StyledButton`'s `PRIMARY_BUTTON`/`DANGER_BUTTON` are
  **filled** (`background-color: accent/danger`), not outlined. `Button.qml`
  here follows the spec (outline, not fill) — a real, deliberate deviation
  from `StyledButton`, not an oversight. `kit/style.py` is unchanged; this
  is a QML-only design, not a retroactive change to the QtWidgets app (that
  would be a visible regression across every screen still on QtWidgets).
- **Panel header**: `Card`'s header (`kit/surface.py`) is a bare `QLabel`,
  no accent mark, no fixed height. The accent-tick pattern exists
  (`StyleRole.SECTION_LABEL_TICKED`) but is a 3px `border-left`, not a
  2×14px rectangle, and is not wired into `Card` at all — exactly the
  "accent bar on some, none on others" the spec names.
- **Log panel**: `AppLogPanel`/`LogPanel` (QtWidgets) already is the one
  shared component the spec asks for, structurally — header, count badge,
  Copy/Clear, one list. Two things it does NOT already do that this QML
  version does: monospace body text, and Copy/Clear as visually
  borderless ("ghost") rather than `SECONDARY_BUTTON`.
- **Dialog**: `Overlay` already is the one shell — header, body, optional
  footer. Its title is plain `SECTION_LABEL` by default, not the ticked
  accent heading; `DialogShell.qml` makes the accent mark the default
  instead of an opt-in.

No numbered token scale ("accent-900", "neutral-600") exists anywhere in
this codebase — `Palette` is flat, single-value tokens. They map 1:1 to
`Palette.ACCENT`/`Palette.MUTED` here; nothing new was added to `Palette`
or the theme bridge.

## `LogPanel.model` — plain list, not a live `QAbstractListModel`

Expects `{timestampText, message, isError}` dicts, matching every other
"structural pass" widget's boundary this session (`TradeLogTable`,
`DatabaseStatusTable`, ...). A host holding the app's real
`runtime.log_list_model.LogListModel` converts to this shape; `LogPanel.qml`
does not read Qt model roles directly the way `DatabaseStatusRow.qml` does
for `DatabaseStatusTableModel` — unlike that model, `LogListModel` is not
already declared "for QML" in its own docstring, so no equivalent
role-name contract was assumed here without checking first.

## Retrofit — 2026-08-30, same pass

`DatabaseStatusTable.qml` and `KlineInspectorTable.qml` now build their
header row from `PanelHeader` instead of a hand-written `RowLayout` +
accent `Rectangle` + `Text`. `DatabaseStatusActionButton.qml` is retired in
favour of `kit/Button.qml`.

`TimeRangePicker.qml`, `TimeframePicker.qml`/`TimeframeToolbar.qml`, and
`TradeLogTable.qml` are **not** retrofitted: none of them render their own
title row today (they are `QmlOverlay`-hosted bodies whose header comes
from `Overlay`'s `title` parameter, per `qml-rule.md` §0.1 — there is no
header in the QML file itself to replace). `TimeframeToolbar`'s pills and
`TradeLogTable`'s filter tabs are a different shape (selection chips, not
action buttons) and are left as they are, not force-fit onto `Button`.

**`SymbolPicker.qml` is deliberately excluded, not missed.** Every `kit/`
component reads the global `Theme` context singleton directly
(`Theme.accent`, ...) — the same thing `Capital`/`SelectList`/`StatGrid`/
`CheckboxList` already do, since they only ever run inside this app.
`SymbolPicker` is the one component with a stated, different goal: its own
`NOTES.md` says it must stay portable to another Qt application with no
dependency on this app's anything, which is why it takes an injected
`theme` property instead of reading `Theme` at all. Routing its header
through `kit/PanelHeader` would reintroduce exactly that dependency and
silently break the one guarantee that component exists to keep. Giving
`kit/` an optional theme-override property just for this one caller was
considered and rejected — a shared primitive gaining a parameter only one
of six consumers ever sets is the "viết bản sao gần giống" shape
`qml-rule.md` §0.2 warns against, just moved one level up.

## `preview.py` shows all four in one window

Mirrors the spec image's own layout: each component next to a short label,
so a change to any of the four is visible without opening six other
widgets to spot-check consistency.
