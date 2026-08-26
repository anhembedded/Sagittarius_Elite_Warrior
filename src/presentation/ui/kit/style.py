"""
@brief Composition-based styling for the app's widget kit — the QtWidgets
replacement for the QML kit's `Sagittarius/UI/` (EPIC-006, see
`Sagittarius_Elite_Warrior/Tasks/epics/EPIC-006_drop_qml/
DECISION_2026-08-24_widget_architecture.md`).

@details
`Surface`/`Card`/`Overlay` and each `Styled*` control share no common base
beyond their own single Qt lineage (`QFrame`/`QDialog`/`QPushButton`/...) —
PySide6/Shiboken forbids a class inheriting two QObject-derived bases, which
rules out a shared styling mixin across those lineages. `apply_role()` is
the composition that replaces it: every widget in this package calls it
once, in its own `__init__`, instead of inheriting styling behaviour.

This module is the ONLY place in the kit permitted to build a
stylesheet string from token values — the guard counterpart to the QML
kit's `tokens.qml_literal_guard` (`widgets.guards.find_inline_stylesheets`)
enforces that no other file in this package (or a consuming app's own
widgets, once it starts using this base) calls `setStyleSheet()` with a
hex literal or token value baked in directly.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc.tokens.theme_bridge import (
    get_theme_bridge,
)


class StyleRole(Enum):
    """
    @brief What a widget IS, not how it looks — `apply_role()` resolves the
    actual QSS from the role + the app's own token values.

    @details One entry per genuinely distinct visual treatment this package
    ships, not one per concrete widget class — `Surface`/`Card`/`Panel`/
    `Overlay` all read as the same "raised, bordered surface on the app
    background" in this app's existing dark theme (confirmed against
    EPIC-005's own dialogs, which all used `Palette.BG_CARD` +
    `Palette.TEXT_PRIMARY` for exactly this), so they share `SURFACE`
    rather than each inventing its own near-identical role.
    """

    SURFACE = auto()
    #: A `Surface` that is also clickable and can be the user's current
    #: choice among siblings (`SelectableCard`) — e.g. one row of a picker
    #: list. Distinct from `SURFACE` because it needs a `WidgetState.SELECTED`
    #: rendering `SURFACE` has no reason to define.
    SELECTABLE_CARD = auto()
    PRIMARY_BUTTON = auto()
    SECONDARY_BUTTON = auto()
    DANGER_BUTTON = auto()
    CHECKBOX = auto()
    FIELD = auto()

    # --- EPIC-007B ----------------------------------------------------- #
    # Every one below needs its own `if` branch in `_build_qss()`. There is
    # no default: the function ends in a dict lookup over the three button
    # roles, so a role added here without a branch raises `KeyError` the
    # first time a widget is constructed, not when the enum is defined.
    # That fail-fast is `controls.py`'s deliberate choice, kept — but it
    # means "add the enum entry" is half the change, never all of it.

    #: A small pill carrying a count or a short status word, sitting beside
    #: a label (`LogPanel`'s "340 EVENTS", a `TabBar` tab's count). Reads
    #: `SELECTED` as its emphasised form.
    BADGE = auto()
    #: The three banner severities. Separate roles rather than one `BANNER`
    #: role plus a severity argument, because `apply_role()` takes a role and
    #: a `WidgetState`, and severity is not a state — a banner does not
    #: transition between info and danger the way a button transitions
    #: between normal and disabled.
    BANNER_INFO = auto()
    BANNER_WARN = auto()
    BANNER_DANGER = auto()
    #: Added late, and only because a consumer needed it: `Banner`'s own
    #: docstring listed a "success/danger switched at runtime" audit banner
    #: among the four it covers, while `Severity` offered no success at all.
    #: The class could not carry the consumer it named.
    BANNER_SUCCESS = auto()
    #: A small muted heading over a group of content — bold and letter-
    #: spaced, no tick. Two of the reference consumer's three section
    #: headings look exactly like this.
    SECTION_LABEL = auto()
    #: The same heading with an accent tick down its leading edge. Its own
    #: role rather than a flag on `SECTION_LABEL`, because only one of the
    #: three headings has the tick — defaulting it on would give the other
    #: two a visual element they never had, and `apply_role`'s second
    #: parameter is a `WidgetState`, which a tick is not.
    SECTION_LABEL_TICKED = auto()
    #: Muted secondary text, neither bold nor letter-spaced — a stat card's
    #: unit suffix or its caption line. Split from `SECTION_LABEL` because a
    #: quiet line of explanatory text should not compete with the heading
    #: above it.
    CAPTION = auto()
    #: The column-header strip of a `TableCard`.
    TABLE_HEADER = auto()
    PROGRESS = auto()

    # --- EPIC-007F ----------------------------------------------------- #
    # Both added from measured consumers in the reference app, not from a
    # guess at what a text kit "should" have — the count is recorded beside
    # each so a later reader can tell a real shape from a speculative one.

    #: Ordinary body text at full contrast — a form field's label, a
    #: checkbox's caption. Distinct from `CAPTION`, which is deliberately
    #: quieter (muted, one size down) so it recedes behind a heading; this
    #: one is the text a user actually reads to operate the screen, so it
    #: must not recede. 4 real consumers, across 3 screens.
    BODY_LABEL = auto()
    #: An accent-coloured bold heading naming a panel or dialog — larger and
    #: louder than `SECTION_LABEL`, which is a muted, letter-spaced label
    #: over a *group inside* a panel. 3 real consumers, which between them
    #: used two near-identical sizes (13px and 14px); collapsing that pair
    #: onto one token is exactly what this epic exists to do.
    #:
    #: Reads `fontSizeLg`, not `fontSizeMd`. It was first written on
    #: `fontSizeMd` — the same token `BODY_LABEL` reads — which made the two
    #: impossible to separate: an app cannot have 12px body labels and 14px
    #: headings when both resolve through one token. A heading is the large
    #: tier by definition; that is the tier it must name.
    HEADING = auto()
    #: A `StatCard`'s headline figure — the one number the card exists to
    #: show. Carries size and weight only; its **colour** is per-instance
    #: (`set_value(tone=...)`), which is the case `semantic_colour()`'s
    #: docstring describes and `apply_role()` cannot express.
    #:
    #: The card shipped without this: the value had no font rule at all, so
    #: the "headline" rendered at the widget default while the caption
    #: beside it was explicitly sized. Nobody chose that — the scale simply
    #: had no display tier to name.
    STAT_VALUE = auto()
    #: A `Surface` that lifts under the pointer. Separate from `SURFACE`
    #: because most surfaces in a screen are not hoverable and giving them
    #: all a hover response would be a visible change to every card in the
    #: app; separate from `SELECTABLE_CARD` because that role also carries a
    #: `SELECTED` state, and a stat card is never "the user's current
    #: choice" — it just acknowledges the pointer.
    STAT_CARD = auto()

    # --- EPIC-007F, second pass ------------------------------------------ #
    # All three come from measuring the reference app's three table-row
    # widgets against `DataRow`, which could not carry any of them without
    # the consumer hand-writing QSS again. The counts below are cells and
    # buttons actually on screen today, not an estimate of what a table kit
    # "should" have.

    #: One cell of a data row: full-contrast text at the small step.
    #: 10 real cells across the 3 row widgets. Distinct from `BODY_LABEL`,
    #: which is one step larger because it labels a control a user reads
    #: once — a column of figures is scanned in bulk and is set smaller
    #: everywhere it appears today. Distinct from `CAPTION`, which is muted:
    #: a cell that recedes uses `CAPTION` and several deliberately do.
    TABLE_CELL = auto()
    #: The same cell emphasised — the column that identifies the row, or the
    #: figure the row exists to report. 5 real cells. Its own role rather
    #: than a `WidgetState`, because a cell does not *transition* into being
    #: the key column; same reasoning that split `SECTION_LABEL_TICKED`.
    TABLE_CELL_STRONG = auto()
    #: A small outlined action at the end of a row: transparent body, accent
    #: text, accent border. 5 real buttons across 2 row widgets, every one
    #: hand-written as an outline.
    #:
    #: The three existing button roles are all *filled*, and that is the
    #: point of the split rather than an oversight to correct: one filled
    #: button per row turns a 40-row table into a wall of colour, which is
    #: why not one of those 5 was written that way. Its colour is
    #: per-instance where a row needs it (`DataRow.set_action_tone`), the
    #: same escape hatch `STAT_VALUE` uses.
    #:
    #: The only button role that names a font size. The three filled ones
    #: leave it to the widget default because they sit in footers and
    #: toolbars at whatever the app's base size is; a row action is
    #: deliberately smaller than the data beside it, and all 5 measured
    #: originals set a size by hand to get that.
    GHOST_BUTTON = auto()
    #: A scrolling body sitting inside a surface — a log's list, a table's
    #: scroll area, a picker's item column. Contributes no chrome of its
    #: own: transparent, no frame, text at full contrast.
    #:
    #: Three of these shipped with **no styling at all** and looked right
    #: only because the card around them was leaking its background down
    #: (`BUG-008`). Scoping that leak correctly turned them white — which is
    #: how a missing rule shows up once the accidental one is gone.
    LIST_SURFACE = auto()


class WidgetState(Enum):
    """Structural state `apply_role()` renders differently. Not every role
    uses every state — a `FIELD` has no hover-vs-idle distinction the way a
    `PRIMARY_BUTTON` does, `_build_qss()` simply ignores states a role's
    QSS block has no rule for."""

    NORMAL = auto()
    DISABLED = auto()
    #: Rendered only by `StyleRole.SELECTABLE_CARD` — "this is the user's
    #: current choice among its siblings," an accent border/background, not
    #: to be confused with keyboard/mouse `:hover` (Qt's own pseudo-state,
    #: still expressed via a `:hover` selector in that role's QSS block).
    SELECTED = auto()


def apply_role(
    widget: QWidget, role: StyleRole, *, state: WidgetState = WidgetState.NORMAL
) -> None:
    """
    @brief Applies token-driven QSS for `role` to `widget`.

    @details The only call a widget in this package makes to get styled —
    no widget here inherits styling behaviour from a shared base. Reads
    from the same `get_theme_bridge()` singleton QML's `Theme.*` bindings
    already read from, so a QtWidgets screen and a QML screen in the same
    app process render from one source of truth, not two independently
    maintained copies.

    @param widget Any QWidget — this package's own base classes call it on
    themselves; a consuming app's derived widget may call it again after
    `super().__init__()` to apply a different role than its base class did
    (e.g. a `DangerCard(Card)` re-applying `DANGER_BUTTON`-flavoured chrome
    to an internal action button `Card` itself doesn't know about).
    @param role Which visual treatment to apply.
    @param state Structural state to render — `WidgetState.DISABLED` is a
    static style choice for widgets whose disabled look needs more than
    Qt's default `:disabled` pseudo-state selector can express; ordinary
    `setEnabled(False)` should still be used for interaction disabling,
    this parameter only controls which QSS block `apply_role()` builds.

    @raise ValueError If no palette has been supplied yet — the app must
    call `sagittarius_engine.extensions.pyside_mvc.tokens.get_theme_bridge()`
    with its palette once at bootstrap (today: a side effect of
    `configure_app_qml()` + constructing the first QML-hosted view; a
    QtWidgets-only app with no QML screens at all must call
    `get_theme_bridge(palette)` directly itself instead — see
    `Sagittarius_Elite_Warrior`'s `EPIC-006C` for that wiring once it
    exists) before constructing any widget from this package.
    """
    widget.setStyleSheet(_scope_qss(widget, _build_qss(role, state)))


def _scope_qss(widget: QWidget, qss: str) -> str:
    """
    @brief Confines `qss` to `widget` itself — the `BUG-008` fix, corrected.

    @details Qt applies a stylesheet set via `setStyleSheet()` to the widget
    it was set on **and** to every descendant with no stylesheet of its own.
    A bare property list — no selector at all — is the universal selector,
    so a `Card`'s background and border used to repaint its whole subtree.

    Scoping to the widget's own runtime class fixed that, and was still not
    enough. **A Qt type selector matches subclasses**, and `QLabel` is a
    `QFrame` subclass — so on a consumer's plain `QFrame()` container, the
    resulting `QFrame { border: ... }` still drew a box around every label
    inside it. The original fix reasoned that subclass matching "only ever
    reaches a further subclass of this same widget — never an unrelated
    sibling elsewhere in the tree". That holds for `Card` or `Panel`; it is
    false for the bare Qt classes a consumer is free to pass, where
    "a further subclass" is every `QLabel` on the screen. Measured, not
    argued: with a red border and a `QFrame` selector, a child `QLabel`
    paints the border and a `QLineEdit` and `QPushButton` do not — exactly
    the subclass relation.

    So the selector is the **exact-class** form, `.ClassName`. Safe for
    every widget here because `apply_role()` is always called with the real
    instance, so the name is already the most derived class (`.ChartCard`,
    not `.Card`, when `ChartCard(Card)` calls it) — the subclass matching
    the dot suppresses is matching this package never relied on.

    A role needing a pseudo-state or sub-control writes its own selector as
    `_SELF`, filled in here rather than hardcoded: a literal `QFrame` in
    `SELECTABLE_CARD` and `STAT_CARD` was the same defect in a second
    place, where scoping could not reach it.
    """
    name = type(widget).__name__
    if _SELF in qss:
        return qss.replace(_SELF, f".{name}")
    if "{" in qss:
        return qss
    return f".{name} {{ {qss} }}"


class Tone(Enum):
    """
    @brief Whether a figure reads as good, bad, or merely a number.

    @details A semantic name, not a colour. The reference consumer computes
    `BULL_COLOR if net_profit >= 0 else BEAR_COLOR` upstream and hands its
    widgets a raw hex string — the "literal with extra steps" pattern the
    token vocabulary exists to end. The comparison stays upstream, where the
    domain knowledge is; only its *answer* crosses into a widget, and this
    module decides what green means.

    Lives here rather than beside its first consumer because it turned out
    to have three: a stat card's headline figure, that card's badge, and a
    data row's status pill. Every one of them is really asking positive /
    negative / neutral, including the ones that look like they need an
    arbitrary colour — the app's long-vs-short and profit-vs-loss badges
    are exactly this question with hardcoded greens and reds.
    """

    NEUTRAL = auto()
    POSITIVE = auto()
    NEGATIVE = auto()


#: Which semantic colour token each tone resolves to.
TONE_TOKENS: dict[Tone, str] = {
    Tone.NEUTRAL: "textPrimary",
    Tone.POSITIVE: "success",
    Tone.NEGATIVE: "danger",
}


def tone_colour(tone: Tone) -> str:
    """@brief The live palette value for a tone."""
    return _token(TONE_TOKENS[tone])


def banner_accent(severity: StyleRole) -> str:
    """
    @brief The live colour of one banner severity.

    @details `Banner` needs it for its message label: the severity's QSS is
    scoped to the panel, so it does not reach the text inside — the text has
    to be told the same colour explicitly. Reads the one mapping the QSS
    itself reads, rather than a second copy that could drift from it.

    @raise KeyError If `severity` is not one of the three banner roles.
    """
    return _token(_BANNER_ACCENTS[severity])


def semantic_colour(name: str) -> str:
    """
    @brief Reads one semantic colour token by name.

    @details The escape hatch for the case `apply_role()` cannot express: a
    colour chosen per *instance* rather than per *role*. `StatCard`'s value
    is the motivating one — whether a figure reads positive or negative is
    decided per card at runtime, and encoding it as roles would mean a
    `POSITIVE_VALUE`/`NEGATIVE_VALUE`/`NEUTRAL_VALUE` triple for every place
    that ever needs a tone.

    Returns a token value, never a literal, so `guards.find_inline_stylesheets`
    stays satisfied and a palette change still reaches every caller. Prefer
    `apply_role()` wherever the colour is a property of what the widget *is*.

    @raise KeyError If no such token exists — same fail-fast as an unknown
    role, rather than rendering a widget with an empty colour.
    """
    return _token(name)


def _token(name: str) -> str:
    """Reads one token value from the shared theme bridge as a string —
    every token this module reads is either a colour (already `str`) or a
    spacing/radius pixel value (`float`, needs `px` appended for QSS).

    Raises on an unknown name. `QQmlPropertyMap.value()` answers a missing
    key with an invalid variant, which `str()` turns into the text `"None"`
    — so a typo rendered `color: None;`, a declaration Qt drops in silence,
    leaving the widget uncoloured with nothing reported anywhere.
    `semantic_colour()` has promised this `KeyError` in its docstring since
    it was written; this is where it starts being true.
    """
    bridge = get_theme_bridge()
    if not bridge.contains(name):
        raise KeyError(f"no theme token named {name!r}")
    return str(bridge.value(name))


def _px(name: str) -> str:
    return f"{_token(name)}px"


#: Which semantic colour token each banner severity reads. A mapping rather
#: than three near-identical `if` bodies — the three banners differ only in
#: this one token, and writing them out separately invites the drift where
#: one severity quietly grows a rule the other two lack.
_BANNER_ACCENTS: dict[StyleRole, str] = {
    StyleRole.BANNER_INFO: "accent",
    StyleRole.BANNER_WARN: "warning",
    StyleRole.BANNER_DANGER: "danger",
    StyleRole.BANNER_SUCCESS: "success",
}


#: Stands in for the widget's own selector inside a role's QSS. `apply_role`
#: substitutes it with the exact-class form once it knows the instance.
#: Roles that need a pseudo-state or a sub-control (`:hover`,
#: `::chunk`) have to write their own selector, and a literal one is what
#: made `QFrame { ... }` reach every `QLabel` inside a card.
_SELF = "__SELF__"


def _build_qss(role: StyleRole, state: WidgetState) -> str:
    disabled = state is WidgetState.DISABLED

    if role is StyleRole.SURFACE:
        return (
            f"background-color: {_token('bgCard')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusMd')};"
            f"color: {_token('textPrimary')};"
        )

    if role is StyleRole.SELECTABLE_CARD:
        selected = state is WidgetState.SELECTED
        border_color = _token("accent") if selected else _token("border")
        background = _token("stateActiveTint") if selected else "transparent"
        return (
            f"{_SELF} {{"
            f"background-color: {background};"
            f"border: 1px solid {border_color};"
            f"border-radius: {_px('radiusMd')};"
            f"}}"
            f"{_SELF}:hover {{background-color: {_token('stateHoverBg')};}}"
        )

    if role is StyleRole.CHECKBOX:
        return f"color: {_token('textPrimary')};"

    if role is StyleRole.FIELD:
        return (
            f"background-color: {_token('stateIdleBg')};"
            f"color: {_token('textPrimary')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusSm')};"
            f"padding: 0 {_px('spaceSm')};"
        )

    if role is StyleRole.BADGE:
        emphasised = state is WidgetState.SELECTED
        return (
            f"background-color: "
            f"{_token('stateActiveTint') if emphasised else _token('stateIdleBg')};"
            f"border: 1px solid "
            f"{_token('accent') if emphasised else _token('border')};"
            f"border-radius: {_px('radiusSm')};"
            f"color: {_token('accent') if emphasised else _token('muted')};"
            f"padding: 0 {_px('spaceXs')};"
        )

    if role in _BANNER_ACCENTS:
        banner_accent = _token(_BANNER_ACCENTS[role])
        return (
            f"background-color: {_token('bgCardHeader')};"
            f"border: 1px solid {banner_accent};"
            f"border-radius: {_px('radiusMd')};"
            f"color: {banner_accent};"
        )

    if role in (StyleRole.SECTION_LABEL, StyleRole.SECTION_LABEL_TICKED):
        # `3px` and `0.8px` are written as literals, like the `1px` borders
        # every other branch here uses: this file is where measurements
        # live, and the guard `find_inline_stylesheets` polices colour
        # literals, not lengths. Both match the consumer's existing heading.
        base = (
            f"background-color: transparent;"
            f"color: {_token('muted')};"
            f"font-size: {_px('fontSizeSm')};"
            f"font-weight: bold;"
            f"letter-spacing: 0.8px;"
        )
        if role is StyleRole.SECTION_LABEL:
            return base
        # The accent tick as a `border-left`, not a child widget — EPIC-007C
        # required trying the QSS form and recording the outcome rather than
        # assuming equivalence. The consumer builds a `QHBoxLayout` holding
        # a 3x12px `QFrame` beside the text purely to draw this line: three
        # objects per heading for what one property expresses.
        #
        # It is not pixel-identical, and that is the recorded difference: a
        # border spans the label's full height, where the old frame was a
        # fixed 12px regardless. A single-line 11px heading looks the same;
        # a wrapped two-line one now gets a tick as tall as it is, which the
        # old version could not do. Judged an improvement, not a regression
        # — but it is a change, so it is written down here rather than
        # discovered later.
        return base + (
            f"border-left: 3px solid {_token('accent')};padding-left: {_px('spaceSm')};"
        )

    if role is StyleRole.CAPTION:
        return (
            f"background-color: transparent;"
            f"color: {_token('muted')};"
            f"font-size: {_px('fontSizeSm')};"
        )

    if role is StyleRole.BODY_LABEL:
        return (
            f"background-color: transparent;"
            f"color: {_token('textPrimary')};"
            f"font-size: {_px('fontSizeMd')};"
        )

    if role is StyleRole.HEADING:
        return (
            f"background-color: transparent;"
            f"color: {_token('accent')};"
            f"font-size: {_px('fontSizeLg')};"
            f"font-weight: bold;"
        )

    if role is StyleRole.STAT_VALUE:
        # No `color` on purpose — the figure's colour is decided per card at
        # runtime by `StatCard.set_value(tone=...)`. Naming a colour here
        # would be a default every caller then has to override.
        return (
            f"background-color: transparent;"
            f"font-size: {_px('fontSizeXl')};"
            f"font-weight: bold;"
        )

    if role is StyleRole.STAT_CARD:
        return (
            f"{_SELF} {{"
            f"background-color: {_token('bgCard')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusMd')};"
            f"color: {_token('textPrimary')};"
            f"}}"
            f"{_SELF}:hover {{"
            f"background-color: {_token('stateHoverBg')};"
            f"border: 1px solid {_token('stateNavBorder')};"
            f"}}"
        )

    if role in (StyleRole.TABLE_CELL, StyleRole.TABLE_CELL_STRONG):
        return (
            f"background-color: transparent;"
            f"color: {_token('textPrimary')};"
            f"font-size: {_px('fontSizeSm')};"
            f"font-weight: "
            f"{'bold' if role is StyleRole.TABLE_CELL_STRONG else 'normal'};"
        )

    if role is StyleRole.GHOST_BUTTON:
        # `spaceSm` horizontally, not `spaceMd` like the filled buttons: a
        # row fits four of these beside six columns of data, and the filled
        # roles' padding is sized for a footer where two buttons have the
        # width to themselves.
        outline = _token("muted") if disabled else _token("accent")
        return (
            f"{_SELF} {{"
            f"background-color: transparent;"
            f"color: {outline};"
            f"border: 1px solid {outline};"
            f"border-radius: {_px('radiusSm')};"
            f"font-size: {_px('fontSizeSm')};"
            f"padding: {_px('spaceXs')} {_px('spaceSm')};"
            f"}}"
            f"{_SELF}:hover {{background-color: {_token('stateHoverBg')};}}"
        )

    if role is StyleRole.LIST_SURFACE:
        return (
            f"background-color: transparent;"
            f"border: none;"
            f"color: {_token('textPrimary')};"
        )

    if role is StyleRole.TABLE_HEADER:
        return (
            f"background-color: {_token('bgCardHeader')};"
            f"border-radius: {_px('radiusSm')};"
            f"color: {_token('muted')};"
        )

    if role is StyleRole.PROGRESS:
        return (
            f"{_SELF} {{"
            f"background-color: {_token('stateIdleBg')};"
            f"border: 1px solid {_token('border')};"
            f"border-radius: {_px('radiusSm')};"
            f"color: {_token('textPrimary')};"
            f"text-align: center;"
            f"}}"
            f"{_SELF}::chunk {{"
            f"background-color: {_token('muted') if disabled else _token('accent')};"
            f"border-radius: {_px('radiusSm')};"
            f"}}"
        )

    accent = {
        StyleRole.PRIMARY_BUTTON: _token("accent"),
        StyleRole.SECONDARY_BUTTON: _token("border"),
        StyleRole.DANGER_BUTTON: _token("danger"),
    }[role]
    text_color = (
        _token("textPrimary") if role is StyleRole.SECONDARY_BUTTON else _token("bg")
    )
    background = _token("muted") if disabled else accent
    hover_background = (
        _token("stateHoverBg") if role is StyleRole.SECONDARY_BUTTON else background
    )
    return (
        f"{_SELF} {{"
        f"background-color: {background};"
        f"color: {text_color};"
        f"border: 1px solid {accent};"
        f"border-radius: {_px('radiusSm')};"
        f"padding: {_px('spaceXs')} {_px('spaceMd')};"
        f"}}"
        f"{_SELF}:hover {{background-color: {hover_background};}}"
    )
