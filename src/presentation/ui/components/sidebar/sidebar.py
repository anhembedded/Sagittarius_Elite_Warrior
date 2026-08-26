from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .sidebar_view_model import SidebarViewModel
from .tab_interface import ITab
from .tabs import SidebarSection

_MAX_WIDTH = 250
_EXPANDED_WIDTH = 220
_COLLAPSED_WIDTH = 48

#: Section header text color — deliberately not Palette.MUTED: the QML
#: original used a distinctly dimmer grey for section titles specifically,
#: separate from the general "muted" semantic token. One-off, not promoted
#: to Palette — nothing else in this screen needs it.
#: EPIC-007D kept it rather than folding it into MUTED: that epic merges
#: near-duplicate *card grounds*, and this is a deliberate one-off with a
#: recorded reason, not drift.
_SECTION_TITLE_COLOR = (
    "#5b6270"  # token-exempt: dimmer than MUTED on purpose, see above
)


class _NavButton(QPushButton):
    """
    @brief One sidebar entry — icon + label, tri-state look (idle/hover/
    active), tooltip, and a left accent bar when active+collapsed.

    @details Not part of `pyside_mvc.widgets`: a nav-item button (route
    identity, active-state left bar, dual expanded/collapsed layouts) is
    specific to this app's navigation chrome, not a generic reusable
    control — reads `Palette` directly, the same escape hatch every other
    Elite-specific widget (`_StatusRowWidget`, `MetricCard`, ...) already
    uses for content the engine's generic `StyleRole` vocabulary has no
    reason to know about.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self._icon_label = QLabel()
        layout.addWidget(self._icon_label)

        self._text_label = QLabel()
        self._text_label.setStyleSheet(
            f"color: {Palette.TEXT_PRIMARY}; font-size: 13px;"
        )
        layout.addWidget(self._text_label, 1)

        self._active_bar = QFrame(self)
        self._active_bar.setFixedSize(3, 22)
        self._active_bar.setStyleSheet(
            f"background-color: {Palette.ACCENT}; border-radius: 1px;"
        )
        self._active_bar.hide()

        self._collapsed = False
        self._is_active = False
        self._navigable = True
        self._apply_style()

    def set_content(self, icon: str, label: str, collapsed: bool) -> None:
        self._collapsed = collapsed
        size = 19 if collapsed else 18
        self._icon_label.setPixmap(
            get_icon_loader()
            .get_icon(icon, Palette.TEXT_PRIMARY, size)
            .pixmap(size, size)
        )
        self._text_label.setText("" if collapsed else label)
        self._text_label.setVisible(not collapsed)
        self._layout_active_bar()

    def set_tooltip_text(self, text: str) -> None:
        self.setToolTip(text)

    def set_navigable(self, navigable: bool) -> None:
        self._navigable = navigable
        self.setEnabled(navigable)
        self._apply_style()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._active_bar.setVisible(active and self._collapsed)
        self._apply_style()

    @property
    def display_text(self) -> str:
        """The rendered label — real `QPushButton.text()` stays empty since
        this button lays out its own icon+label `QLabel`s instead of using
        Qt's native single-line button text."""
        return self._text_label.text()

    @property
    def is_active(self) -> bool:
        return self._is_active

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_active_bar()

    def _layout_active_bar(self) -> None:
        self._active_bar.move(-3, (self.height() - self._active_bar.height()) // 2)

    def _apply_style(self) -> None:
        border = "transparent" if self._collapsed else Palette.STATE_NAV_BORDER
        border_style = (
            f"1px solid {border}"
            if self._is_active and not self._collapsed
            else "1px solid transparent"
        )
        self.setStyleSheet(
            f"QPushButton {{ background-color: transparent; text-align: left; "
            f"border: {border_style}; border-radius: 4px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }} "
            f"QPushButton:disabled {{ color: {Palette.MUTED}; }}"
        )


class Sidebar(BaseView):
    """
    @brief Self-contained navigation sidebar — QtWidgets (EPIC-006C).

    @details Migrated off `QmlHostView`/`Sidebar.qml` (kept on disk,
    unloaded, per EPIC-006's rollback convention) the same way EPIC-005's
    screens were: `SidebarViewModel` is a plain `QObject` (never
    `BaseQmlViewModel` — it has no `uiMode` FSM to bind), unchanged.

    Python-facing contract (`sig_navigate`, `set_active`, constructor
    signature) is unchanged, so `MainWindow`'s wiring needed no changes.
    """

    sig_navigate = Signal(str)

    def __init__(
        self,
        sections: Sequence[SidebarSection],
        bottom_actions: Sequence[ITab] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumWidth(_COLLAPSED_WIDTH)
        self.setMaximumWidth(_MAX_WIDTH)
        self.setStyleSheet(
            f"background-color: {Palette.BG_SIDEBAR}; "
            f"border-right: 1px solid {Palette.BORDER};"
        )

        self._sections = tuple(sections)
        self._bottom_actions = tuple(bottom_actions)
        self._nav_buttons: dict[str, _NavButton] = {}
        self._section_title_labels: list[QLabel] = []
        self._section_dividers: list[QFrame] = []

        self._view_model = SidebarViewModel(sections, bottom_actions)
        self._view_model.navigationRequested.connect(self.sig_navigate)
        self._view_model.isCollapsedChanged.connect(self._on_collapsed_changed)

        self._build_ui()
        self._sync_collapsed_state()
        self._on_collapsed_changed()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(10, 16, 10, 10)
        self._outer_layout.setSpacing(8)

        self._outer_layout.addLayout(self._build_header())
        self._outer_layout.addSpacerItem(
            QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )

        for section in self._sections:
            self._outer_layout.addLayout(self._build_section(section))

        self._outer_layout.addStretch(1)

        self._bottom_divider = QFrame()
        self._bottom_divider.setFixedHeight(1)
        self._bottom_divider.setStyleSheet(f"background-color: {Palette.BORDER};")
        self._bottom_divider.setVisible(bool(self._bottom_actions))
        self._outer_layout.addWidget(self._bottom_divider)

        for item in self._bottom_actions:
            self._outer_layout.addWidget(
                self._build_nav_row(item, object_prefix="bottomNavButton_")
            )

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        self._brand_label = QLabel("SAGITTARIUS")
        self._brand_label.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 15px; font-weight: bold;"
        )
        row.addWidget(self._brand_label)

        self._brand_tag = QLabel("ELITE")
        self._brand_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._brand_tag.setStyleSheet(
            f"background-color: {Palette.ACCENT}; color: {Palette.BG}; "
            f"border-radius: 3px; font-size: 9px; font-weight: bold; padding: 1px 4px;"
        )
        row.addWidget(self._brand_tag)

        row.addStretch(1)

        self._btn_collapse = QPushButton()
        self._btn_collapse.setObjectName("btnCollapseSidebar")
        self._btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_collapse.setIcon(
            get_icon_loader().get_icon("panel-left", Palette.TEXT_PRIMARY, 16)
        )
        self._btn_collapse.setFixedSize(28, 28)
        self._btn_collapse.setStyleSheet(
            f"QPushButton {{ background-color: transparent; border: none; "
            f"border-radius: 4px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }}"
        )
        self._btn_collapse.clicked.connect(self._view_model.toggleCollapsed)
        row.addWidget(self._btn_collapse)

        return row

    def _build_section(self, section: SidebarSection) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(8)

        title_label = QLabel(section.title)
        title_label.setStyleSheet(
            f"color: {_SECTION_TITLE_COLOR}; font-size: 10px; font-weight: bold; "
            f"letter-spacing: 1px;"
        )
        column.addWidget(title_label)
        self._section_title_labels.append(title_label)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {Palette.BORDER};")
        divider.setVisible(False)
        column.addWidget(divider, 0, Qt.AlignmentFlag.AlignHCenter)
        self._section_dividers.append(divider)

        for item in section.items:
            column.addWidget(self._build_nav_row(item, object_prefix="navButton_"))

        return column

    def _build_nav_row(self, item: ITab, *, object_prefix: str) -> _NavButton:
        data = item.to_dict()
        button = _NavButton()
        button.setObjectName(f"{object_prefix}{data['route'] or data['label']}")
        button.set_navigable(bool(data["navigable"]))
        button.set_tooltip_text(str(data["tooltip"]))
        button.clicked.connect(
            lambda _checked=False, r=data["route"]: self._view_model.navigate(r)
        )
        self._nav_buttons[data["route"] or data["label"]] = button
        return button

    # ------------------------------------------------------------------ #
    # State sync
    # ------------------------------------------------------------------ #

    def _on_collapsed_changed(self) -> None:
        if self._view_model.isCollapsed:
            self.setFixedWidth(_COLLAPSED_WIDTH)
        else:
            self.setMinimumWidth(_COLLAPSED_WIDTH)
            self.setMaximumWidth(_MAX_WIDTH)
            self.resize(_EXPANDED_WIDTH, self.height())
        self._sync_collapsed_state()

    def _sync_collapsed_state(self) -> None:
        collapsed = self._view_model.isCollapsed
        self._outer_layout.setContentsMargins(
            4 if collapsed else 10, 10 if collapsed else 16, 4 if collapsed else 10, 10
        )
        self._brand_label.setVisible(not collapsed)
        self._brand_tag.setVisible(not collapsed)
        self._btn_collapse.setToolTip(
            "Mở rộng thanh bên" if collapsed else "Thu gọn thanh bên"
        )

        for label in self._section_title_labels:
            label.setVisible(not collapsed)
        for divider in self._section_dividers:
            divider.setVisible(collapsed)

        for section in self._sections:
            for item in section.items:
                data = item.to_dict()
                key = data["route"] or data["label"]
                self._nav_buttons[key].set_content(
                    data["icon"], data["label"], collapsed
                )
                self._nav_buttons[key].setFixedHeight(36 if collapsed else 40)
        for item in self._bottom_actions:
            data = item.to_dict()
            key = data["route"] or data["label"]
            self._nav_buttons[key].set_content(data["icon"], data["label"], collapsed)
            self._nav_buttons[key].setFixedHeight(36 if collapsed else 40)

        self._sync_active_state()

    def _sync_active_state(self) -> None:
        active_route = self._view_model.activeRoute
        for key, button in self._nav_buttons.items():
            button.set_active(bool(active_route) and key == active_route)

    def set_active(self, route_name: str) -> None:
        """
        @brief Marks a route as the active/highlighted entry.
        @param route_name The currently active route.
        """
        self._view_model.set_active_route(route_name)
        self._sync_active_state()

    # ------------------------------------------------------------------ #
    # Collapsed state — public surface for EPIC-010 (remembered UI state)
    # ------------------------------------------------------------------ #

    @property
    def is_collapsed(self) -> bool:
        """@brief Whether the sidebar is currently in its collapsed (icon-only) mode."""
        return bool(self._view_model.isCollapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """@brief Sets the collapsed state directly, bypassing the toggle button.

        @details Exists for restoring a remembered value at boot — calling the
        button's own `toggleCollapsed()` would require knowing the *current*
        state first, which is exactly what a restore does not have yet.
        """
        self._view_model.set_collapsed(collapsed)

    @property
    def collapsed_changed(self) -> SignalInstance:
        """@brief The view model's `isCollapsedChanged` signal, re-exposed.

        @details `_view_model` stays private; this is the one signal a caller
        outside this component legitimately needs — to know when to persist
        the new state, not to react to sidebar layout internals.
        """
        return self._view_model.isCollapsedChanged
