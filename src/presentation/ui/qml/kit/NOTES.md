# qml/kit — shared QML primitives

Seven components now. The first four came from a design-system spec the user
provided 2026-08-30: `PanelHeader`, `Button`, `LogPanel`, `DialogShell`. Each
replaces a pattern every widget built so far this session (`SymbolPicker`,
`DatabaseStatusTable`, `KlineInspectorTable`, ...) was hand-rolling slightly
differently — the spec's own annotations name the resulting drift ("Was:
accent bar on some, none on others; three label sizes", "Was: gold fill,
green outline, red fill and bare text all on one screen"). `StatusPill` and
`ProgressBanner` were added the same day from a second spec image (cards
88/89/10: stat card, sidebar & nav, "trạng thái đang chạy" — the user chose
to build the running-state/WS-pill card first, since it was the one area
with **no** shared component anywhere yet; StatCard already exists and
already scopes P&L colour to just the number, `kit/surfaces/stat_card.py`,
and Sidebar already is one widget with two modes, `components/sidebar/sidebar.py`
— both real "redesign an existing widget" work, saved for later).

**Pure QML, no Python VM for any of the six** — `qml-rule.md` §1.3: a
component with nothing to derive, only properties a caller sets, does not
get one. `__init__.py` exists only so `tests/` resolves to a unique package
path, not to re-export anything.

## `StatusPill` / `ProgressBanner` — the real state behind the mockup

`screens/dashboard/dev_board_panel.py`'s WS badge (a bare `QLabel` + a
colour-square `QLabel`, styled inline, no dedicated class) is **not** dead —
`dashboard_presenter.py`'s `_WS_STATUS_BY_MODE` genuinely drives it through
all 4 FSM states (`IDLE`→muted, `LOCKED`→"SYNCING"/accent, `LIVE`→success,
`ERROR`→danger) as the real stream lifecycle changes. `StatusPill.tone`
mirrors those same four states (`idle`/`active`/`success`/`danger`) so a
future host wires it to the same states it already has, not a new vocabulary.

`components/app_progress_bar.py`'s `AppProgressBar` already tracks a real
percentage every tick (`backtest_top_panel.py` calls
`set_value(int(vm.backtestProgressPercent))`) but never renders it —
`setTextVisible` stays off by design, so the number is computed and then
thrown away. `ProgressBanner`'s `percent` property is that same number,
finally shown — not a new metric invented for the mockup. `indeterminate`
covers the one phase that genuinely has no percentage: "Đang hủy an
toàn..." (`set_indeterminate(True)`, no known duration for a safe cancel).

## `StatCard` — a port of an existing widget, not a new shape

`kit/surfaces/stat_card.py`'s `StatCard` (QtWidgets) already has every slot
the mockup needs — title/value/suffix/badge/caption — and already scopes
tone colour to just the value label (`set_value(value, tone=...)`), so the
spec's own annotation ("Was: colour applied to labels too") does not
describe this widget; whatever it was comparing against is not in this
codebase. What the QML port actually changes: a single 22px value size
(the QtWidgets role already used one fixed size, just not this one), and
extending tone-scoping to the `caption` line — the mockup's "TỔNG LÃI/LỖ"
example colours both `"-8,193.54 USD"` and `"-81.94%"` together, since
together they express one P&L figure; its two non-P&L examples ("Tỷ lệ
thắng", "Stored klines") leave both lines untouched, which is what a
caller gets by simply never setting `tone`.

`backtest_top_panel.py`'s real call site (`_sync_stat_cards`,
`primaryStatCards`) sets `badgeText`/`badgeTone`, never `caption` — so
today's real backtest cards render a pill for their sub-line, not the
plain text line the mockup shows. `StatCard.qml` keeps both slots (`caption`
already existed on the QtWidgets widget for its other two real call sites)
rather than picking one and dropping a working feature; which slot a
future host uses for which card is that host's decision, not this
component's.

Font "tabular figures" (fixed-width digits, so a column of numbers aligns)
is not implemented — QML's `Text.font` has no documented OpenType-feature
toggle for it, and no widget in this app has ever needed one before. The
value renders at a plain 22px instead; revisit only if columns of these
cards are ever laid out one under another where uneven digit widths would
visibly misalign.

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

## `progress_banner_widget.py` — the first inline host in this package

Every other `.qml` here is reached only through `preview.py` or a modal
(`QmlOverlay`, `SymbolPickerModal`) — this directory itself stayed "pure
QML, no Python" per `qml-rule.md` §1.3. `EPIC-015` Phase 2 breaks that for
exactly one component: `ProgressBanner.qml` is now embedded inline in
`DataManagementView`'s own `QVBoxLayout` (replacing `AppProgressBar` + a
standalone Cancel `QPushButton`), and an inline, non-modal embed needs
*some* Python object to sit in that layout slot — a bare `.qml` file has no
Qt Widgets identity to add to a layout. `ProgressBannerWidget` is that
object: a thin `QQuickWidget` subclass, not a ViewModel (it derives
nothing — every value it sets on the QML root is already computed by
`DataManagementViewModel`), so it is not the kind of "widget-VM" §1.3
warns against needing a reason to exist. See its own docstring for why it
is component-specific rather than a generic inline-QML base.

## `status_pill_widget.py` — Phase 4, the first `kit/` embed beside the live chart

`StatusPillWidget` replaces `screens/dashboard/dev_board_panel.py`'s bare
`QLabel` + colour-square `QFrame` WS badge (the state this file's own
"`StatusPill` / `ProgressBanner`" section above already described as real,
4-state-driven, just not reusable) with `StatusPill.qml` embedded inline
in `DevBoardPanel`'s header row — same non-modal, no-`QmlOverlay` shape as
`ProgressBannerWidget`, and the same two plain setters
(`set_text`/`set_tone`) `_sync_ws_status()` already called on the old
widgets. The tone (`"idle"|"active"|"success"|"danger"`) is derived from
`UIMode`, not from `wsStatusColor`'s raw hex string — `dashboard_presenter.py`'s
`_WS_STATUS_BY_MODE` now carries a third tuple element per mode instead of
a second switch statement, and `DashboardQmlViewModel.wsStatusTone` exposes
it alongside `wsStatusText`/`wsStatusColor`.

**This is the highest-risk widget built under `EPIC-015` to date** — it is
the first `kit/` component embedded in the same top-level window as the
live pyqtgraph chart (`qml-rule.md` §0's "Panel QML cạnh chart" row, only
previously *measured* in a spike, never shipped). See the epic's own §6
stop condition (chart flicker/no-render/FPS drop) — this was built and
fully unit-tested in a headless (`QT_QPA_PLATFORM=offscreen`) sandbox that
cannot observe chart rendering quality at all; a human must verify the
real running app before this counts as done.
