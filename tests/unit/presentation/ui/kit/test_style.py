"""Tests for `widgets.style.apply_role()` — the composition point that
replaces a shared styling base class (see EPIC-006's architecture ADR §3
for why no such base exists)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    StyleRole,
    WidgetState,
    apply_role,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge


def test_apply_role_sets_a_non_empty_stylesheet(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.SURFACE)

    assert widget.styleSheet() != ""


def test_surface_role_uses_the_live_bgcard_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.SURFACE)

    live_bg_card = str(get_theme_bridge().value("bgCard"))
    assert live_bg_card in widget.styleSheet()


def test_field_role_uses_the_live_border_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.FIELD)

    live_border = str(get_theme_bridge().value("border"))
    assert live_border in widget.styleSheet()


def test_disabled_state_produces_different_qss_than_normal_for_buttons(
    qtbot, fake_theme_bridge
):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.PRIMARY_BUTTON, state=WidgetState.NORMAL)
    normal_qss = widget.styleSheet()

    apply_role(widget, StyleRole.PRIMARY_BUTTON, state=WidgetState.DISABLED)
    disabled_qss = widget.styleSheet()

    assert normal_qss != disabled_qss


def test_disabled_button_uses_the_live_muted_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.DANGER_BUTTON, state=WidgetState.DISABLED)

    live_muted = str(get_theme_bridge().value("muted"))
    assert live_muted in widget.styleSheet()


def test_selectable_card_selected_state_uses_the_live_accent_token(qtbot):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.SELECTABLE_CARD, state=WidgetState.SELECTED)

    live_accent = str(get_theme_bridge().value("accent"))
    assert live_accent in widget.styleSheet()


def test_selectable_card_normal_vs_selected_produce_different_qss(
    qtbot, fake_theme_bridge
):
    widget = QFrame()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.SELECTABLE_CARD, state=WidgetState.NORMAL)
    normal_qss = widget.styleSheet()

    apply_role(widget, StyleRole.SELECTABLE_CARD, state=WidgetState.SELECTED)
    selected_qss = widget.styleSheet()

    assert normal_qss != selected_qss


def test_checkbox_and_field_roles_ignore_disabled_state():
    """These two roles' QSS blocks have no disabled-state branch (see
    style._build_qss) — asserting that explicitly, so a future change
    that silently drops disabled handling for buttons doesn't also
    silently claim these roles handle it when they never did."""
    from PySide6.QtWidgets import QWidget

    checkbox_widget = QWidget()
    field_widget = QWidget()

    apply_role(checkbox_widget, StyleRole.CHECKBOX, state=WidgetState.NORMAL)
    normal_checkbox_qss = checkbox_widget.styleSheet()
    apply_role(checkbox_widget, StyleRole.CHECKBOX, state=WidgetState.DISABLED)
    assert checkbox_widget.styleSheet() == normal_checkbox_qss

    apply_role(field_widget, StyleRole.FIELD, state=WidgetState.NORMAL)
    normal_field_qss = field_widget.styleSheet()
    apply_role(field_widget, StyleRole.FIELD, state=WidgetState.DISABLED)
    assert field_widget.styleSheet() == normal_field_qss


# ---------------------------------------------------------------------- #
# EPIC-007B roles
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize("role", list(StyleRole))
def test_every_role_renders_without_falling_through(qtbot, role):
    """`_build_qss` ends in a dict lookup over the three button roles, with
    no default branch. A role added to the enum without its own `if` reaches
    that lookup and raises `KeyError` at construction time — not at import,
    and not in any test that does not happen to use it. This parametrises
    over `StyleRole` itself, so the enum entry and the branch cannot be added
    apart."""
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)

    apply_role(widget, role)

    assert widget.styleSheet() != ""


@pytest.mark.parametrize(
    ("role", "token"),
    [
        (StyleRole.BANNER_INFO, "accent"),
        (StyleRole.BANNER_WARN, "warning"),
        (StyleRole.BANNER_DANGER, "danger"),
    ],
)
def test_each_banner_severity_uses_its_own_semantic_token(
    qtbot, fake_theme_bridge, role, token
):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)

    apply_role(widget, role)

    assert f"<{token}>" in widget.styleSheet()


def test_the_three_banner_severities_are_visually_distinct(qtbot, fake_theme_bridge):
    """The reason `warning` was added to the required token vocabulary at
    all: the reference consumer renders a warning banner directly beside an
    accent-coloured info banner, so the two must not collapse."""
    from PySide6.QtWidgets import QWidget

    rendered = set()
    for role in (
        StyleRole.BANNER_INFO,
        StyleRole.BANNER_WARN,
        StyleRole.BANNER_DANGER,
    ):
        widget = QWidget()
        qtbot.addWidget(widget)
        apply_role(widget, role)
        rendered.add(widget.styleSheet())

    assert len(rendered) == 3


def test_badge_selected_state_differs_from_normal(qtbot, fake_theme_bridge):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.BADGE, state=WidgetState.NORMAL)
    normal = widget.styleSheet()
    apply_role(widget, StyleRole.BADGE, state=WidgetState.SELECTED)

    assert widget.styleSheet() != normal


# ---------------------------------------------------------------------- #
# EPIC-007F roles
# ---------------------------------------------------------------------- #


def test_body_label_is_full_contrast_where_caption_is_muted(qtbot, fake_theme_bridge):
    """The distinction that justifies BODY_LABEL existing beside CAPTION: a
    form field's label is text the user reads to operate the screen, so it
    must not recede the way an explanatory caption deliberately does."""
    from PySide6.QtWidgets import QWidget

    body = QWidget()
    qtbot.addWidget(body)
    caption = QWidget()
    qtbot.addWidget(caption)

    apply_role(body, StyleRole.BODY_LABEL)
    apply_role(caption, StyleRole.CAPTION)

    assert "<textPrimary>" in body.styleSheet()
    assert "<muted>" in caption.styleSheet()
    assert body.styleSheet() != caption.styleSheet()


def test_heading_is_accent_and_bold_where_section_label_is_muted(
    qtbot, fake_theme_bridge
):
    """HEADING names a whole panel or dialog; SECTION_LABEL labels a group
    inside one. Collapsing them would make a dialog title recede to the same
    weight as the group headings underneath it."""
    from PySide6.QtWidgets import QWidget

    heading = QWidget()
    qtbot.addWidget(heading)
    section = QWidget()
    qtbot.addWidget(section)

    apply_role(heading, StyleRole.HEADING)
    apply_role(section, StyleRole.SECTION_LABEL)

    assert "<accent>" in heading.styleSheet()
    assert "font-weight: bold" in heading.styleSheet()
    assert "<muted>" in section.styleSheet()


def test_body_label_and_heading_read_different_size_tokens(qtbot, fake_theme_bridge):
    """A heading and a body label must be separately sizable by the app.

    Both were first written on `fontSizeMd`, which looked tidy and was
    unusable: the reference app wants 12px body labels and 14px headings,
    and one token cannot be two numbers. Sharing a token is not
    consolidation when the two things were never the same size.

    Each still resolves through a token rather than a literal — that part
    was right and is pinned below.
    """
    from PySide6.QtWidgets import QWidget

    body = QWidget()
    qtbot.addWidget(body)
    heading = QWidget()
    qtbot.addWidget(heading)

    apply_role(body, StyleRole.BODY_LABEL)
    apply_role(heading, StyleRole.HEADING)

    assert "<fontSizeMd>" in body.styleSheet()
    assert "<fontSizeLg>" in heading.styleSheet()


def test_progress_disabled_chunk_uses_the_muted_token(qtbot, fake_theme_bridge):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)

    apply_role(widget, StyleRole.PROGRESS, state=WidgetState.DISABLED)

    assert "<muted>" in widget.styleSheet()
