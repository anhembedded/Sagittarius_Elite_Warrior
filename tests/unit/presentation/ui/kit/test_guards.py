"""Tests for `widgets.guards` — the QtWidgets counterparts to
`tokens.qml_literal_guard`/`kit.raw_primitive_guard`."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui.kit.guards import (
    find_bare_qt_base_widgets,
    find_inline_stylesheets,
    find_unscoped_container_stylesheets,
    format_unscoped_container_findings,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------- #
# find_inline_stylesheets
# ---------------------------------------------------------------------- #


def test_finds_a_hex_literal_in_a_setstylesheet_call(tmp_path: Path):
    _write(
        tmp_path / "some_widget.py",
        'widget.setStyleSheet("background-color: #111318;")\n',
    )

    findings = find_inline_stylesheets(tmp_path)

    assert len(findings) == 1
    assert findings[0].matched == "#111318"
    assert findings[0].file.name == "some_widget.py"


def test_does_not_flag_style_py_itself(tmp_path: Path):
    _write(
        tmp_path / "style.py",
        'widget.setStyleSheet("background-color: #111318;")\n',
    )

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


def test_respects_the_token_exempt_marker(tmp_path: Path):
    _write(
        tmp_path / "legacy.py",
        'widget.setStyleSheet("color: #ffffff;")  # token-exempt: migration leftover\n',
    )

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


def test_ignores_comment_only_lines(tmp_path: Path):
    _write(tmp_path / "note.py", "# was #111318 before the token migration\n")

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


def test_clean_file_produces_no_findings(tmp_path: Path):
    _write(
        tmp_path / "clean_widget.py",
        "from .style import StyleRole, apply_role\n"
        "apply_role(self, StyleRole.SURFACE)\n",
    )

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


# ---------------------------------------------------------------------- #
# find_bare_qt_base_widgets
# ---------------------------------------------------------------------- #


def test_finds_a_class_directly_subclassing_qframe(tmp_path: Path):
    _write(tmp_path / "custom.py", "class MyPanel(QFrame):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QFrame"


def test_finds_a_class_directly_subclassing_qdialog(tmp_path: Path):
    _write(tmp_path / "custom.py", "class MyDialog(QDialog):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QDialog"


def test_does_not_flag_surface_py_or_overlay_py(tmp_path: Path):
    _write(tmp_path / "surface.py", "class Surface(QFrame):\n    pass\n")
    _write(tmp_path / "overlay.py", "class Overlay(QDialog):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_does_not_flag_a_class_extending_surface_or_overlay(tmp_path: Path):
    _write(tmp_path / "card.py", "class Card(Surface):\n    pass\n")
    _write(tmp_path / "confirm.py", "class ConfirmOverlay(Overlay):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_does_not_flag_controls_extending_their_own_qt_base(tmp_path: Path):
    _write(
        tmp_path / "controls.py",
        "class StyledButton(QPushButton):\n    pass\n\n\n"
        "class DateTimeField(QDateTimeEdit):\n    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_finds_a_class_directly_subclassing_qwidget(tmp_path: Path):
    """EPIC-007A: the gap that let 9 of the consuming app's surfaces through.
    A `class X(QWidget)` is the same "authored a raw primitive" mistake as
    `class X(QFrame)`; only the spelling differed."""
    _write(
        tmp_path / "log_panel_widget.py", "class LogPanelWidget(QWidget):\n    x=1\n"
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QWidget"


def test_base_exempt_marker_with_a_reason_waives_the_finding(tmp_path: Path):
    _write(
        tmp_path / "base_view.py",
        "class BaseView(QWidget):  # base-exempt: an MVC view root, not a surface\n"
        "    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_base_exempt_marker_without_a_reason_does_not_waive(tmp_path: Path):
    """Deliberately stricter than `token-exempt`/`card-exempt`, which match on
    presence alone — see `_BASE_EXEMPT_RE`'s note. A bare marker is an
    exemption nobody justified, so it does not count as one."""
    _write(
        tmp_path / "sneaky.py",
        "class Sneaky(QWidget):  # base-exempt:\n    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QWidget"


def test_token_exempt_does_not_silence_the_base_class_guard(tmp_path: Path):
    """The two markers are separate on purpose: one axis is a literal colour
    value, the other a base class. An exemption reviewed for one must not
    wave the other through."""
    _write(
        tmp_path / "wrong_marker.py",
        "class MyPanel(QFrame):  # token-exempt: migration leftover\n    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QFrame"


def test_a_consuming_apps_palette_module_can_be_named_as_a_colour_source(
    tmp_path: Path,
):
    """EPIC-007D: an app's colours live in its own palette module, not in a
    file called `style.py`. Before this, that module was reported for
    containing the very tokens it exists to define, so "zero findings" was
    unreachable for any consumer."""
    _write(tmp_path / "palette.py", 'BG_CARD = "#111318"\n')
    _write(tmp_path / "screen.py", 'w.setStyleSheet("background: #111318;")\n')

    findings = find_inline_stylesheets(tmp_path, colour_source_names=("palette.py",))

    assert len(findings) == 1
    assert findings[0].file.name == "screen.py"


def test_naming_a_colour_source_does_not_excuse_a_lookalike(tmp_path: Path):
    _write(tmp_path / "palette_helpers.py", 'BG = "#111318"\n')

    findings = find_inline_stylesheets(tmp_path, colour_source_names=("palette.py",))

    assert len(findings) == 1


def test_style_py_is_still_skipped_without_being_named(tmp_path: Path):
    """The package's own convention keeps working for callers that pass
    nothing — this parameter is additive, not a replacement."""
    _write(tmp_path / "style.py", 'QSS = "color: #ffffff;"\n')

    assert find_inline_stylesheets(tmp_path) == []


# --------------------------------------------------------------------------- #
# find_unscoped_container_stylesheets — BUG-008's guard
# --------------------------------------------------------------------------- #


def _screen(tmp_path, body: str):
    (tmp_path / "screen.py").write_text(body, encoding="utf-8")
    return tmp_path


def test_a_container_styled_without_a_selector_is_reported(tmp_path):
    """The exact shape of `BUG-008`: a bare property list is Qt's universal
    selector, so this tile hands its border to all three labels inside it."""
    root = _screen(
        tmp_path,
        """
tile = QFrame()
tile.setStyleSheet("background-color: #111318; border: 1px solid #282c3f;")
layout = QVBoxLayout(tile)
""",
    )

    findings = find_unscoped_container_stylesheets(root)

    assert len(findings) == 1
    assert findings[0].target == "tile"
    assert findings[0].properties == ("border", "background")


def test_a_leaf_styled_the_same_way_is_not_reported(tmp_path):
    """Styling one widget that has no children is the ordinary way to style
    a widget. Reporting those would bury the real findings — in the
    reference app 63 unscoped sheets narrow to 16 containers."""
    root = _screen(
        tmp_path,
        """
label = QLabel("Stored KLines Records")
label.setStyleSheet("background: transparent; border: none;")
""",
    )

    assert find_unscoped_container_stylesheets(root) == []


def test_a_scoped_container_is_not_reported(tmp_path):
    root = _screen(
        tmp_path,
        """
tile = QFrame()
tile.setStyleSheet("QFrame { background-color: #111318; border: 1px solid #282c3f; }")
layout = QVBoxLayout(tile)
""",
    )

    assert find_unscoped_container_stylesheets(root) == []


def test_set_layout_also_makes_a_widget_a_container(tmp_path):
    """The other way a widget acquires children."""
    root = _screen(
        tmp_path,
        """
host = QWidget()
host.setStyleSheet("border: 1px solid #282c3f;")
host.setLayout(row)
""",
    )

    assert len(find_unscoped_container_stylesheets(root)) == 1


def test_colour_alone_is_not_a_leak(tmp_path):
    """Text colour inherits in Qt regardless of selectors — a container
    setting it once for its labels is idiomatic, not a mistake."""
    root = _screen(
        tmp_path,
        """
card = QFrame()
card.setStyleSheet("color: #e8e9ec;")
layout = QVBoxLayout(card)
""",
    )

    assert find_unscoped_container_stylesheets(root) == []


def test_an_f_string_is_read_through_its_literal_parts(tmp_path):
    """Every real call builds its sheet from tokens. Interpolated values are
    skipped rather than guessed at — a token is a colour, never a selector,
    so dropping it cannot flip the verdict either way."""
    root = _screen(
        tmp_path,
        """
card = QFrame()
card.setStyleSheet(f"background-color: {Palette.BG_CARD}; border: 1px solid {Palette.BORDER};")
layout = QVBoxLayout(card)
""",
    )

    assert len(find_unscoped_container_stylesheets(root)) == 1


def test_a_reasoned_exemption_is_honoured(tmp_path):
    root = _screen(
        tmp_path,
        """
card = QFrame()
card.setStyleSheet("border: 1px solid #282c3f;")  # cascade-exempt: on purpose
layout = QVBoxLayout(card)
""",
    )

    assert find_unscoped_container_stylesheets(root) == []


def test_findings_format_with_file_line_and_what_leaks(tmp_path):
    root = _screen(
        tmp_path,
        """
tile = QFrame()
tile.setStyleSheet("border: 1px solid #282c3f;")
layout = QVBoxLayout(tile)
""",
    )

    text = format_unscoped_container_findings(find_unscoped_container_stylesheets(root))

    assert "screen.py:3" in text
    assert "tile leaks border" in text


def test_self_is_resolved_per_class_not_per_file(tmp_path):
    """A class that lays itself out must not vouch for its neighbours.

    Resolved module-wide, `LeafWidget` below was reported because
    `CardWidget` in the same file happens to call `QVBoxLayout(self)` — and
    that is a real leaf in the reference app, styled correctly. A guard's
    first false positive is how it gets switched off.
    """
    root = _screen(
        tmp_path,
        """
class CardWidget(QFrame):
    def __init__(self):
        layout = QVBoxLayout(self)

class LeafWidget(QFrame):
    def __init__(self):
        self.setStyleSheet("background-color: #ff000080;")
""",
    )

    assert find_unscoped_container_stylesheets(root) == []


def test_a_class_that_lays_itself_out_is_still_reported(tmp_path):
    root = _screen(
        tmp_path,
        """
class CardWidget(QFrame):
    def __init__(self):
        self.setStyleSheet("border: 1px solid #282c3f;")
        layout = QVBoxLayout(self)
""",
    )

    findings = find_unscoped_container_stylesheets(root)

    assert len(findings) == 1
    assert findings[0].target == "self"


def test_a_widget_that_holds_children_without_a_layout_is_a_container(tmp_path):
    """`QStackedWidget` and friends hold children directly, so the
    layout-owner check never sees them.

    Not hypothetical: the reference app styled the stack holding **every
    screen** with a bare property list, and the guard walked past the
    largest cascade in the whole application — a dark rectangle behind
    every label on every screen that had no background rule of its own.
    """
    root = _screen(
        tmp_path,
        """
stacked = QStackedWidget()
stacked.setStyleSheet("background-color: #0a0a0c; color: #e8e9ec;")
""",
    )

    findings = find_unscoped_container_stylesheets(root)

    assert len(findings) == 1
    assert findings[0].target == "stacked"


def test_a_scoped_stack_is_not_reported(tmp_path):
    root = _screen(
        tmp_path,
        """
stacked = QStackedWidget()
stacked.setStyleSheet("QStackedWidget { background-color: #0a0a0c; }")
""",
    )

    assert find_unscoped_container_stylesheets(root) == []
