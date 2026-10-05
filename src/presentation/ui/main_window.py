"""
@brief MainWindow — the application's one workbench window (`EPIC-033C`).

@details
The window is the Engine's `WorkbenchShell`: a menu bar in the Windows order,
a vertical mode bar (Ctrl+1…), a stack of modes, a status bar, Window → Reset
layout, Tools → Options, Help → About. This class supplies the policy: which
modes exist (every navigable screen the `IScreenRegistry` knows, in its
order), their icons and access keys, the venue in the title and status bar,
what to ask before closing, and what to remember.

@par Every mode is built at start
The user chose this over a lazily built mode (2026-10-04): a mode is a host
the shell owns from the first frame. Building a screen therefore no longer
means the user opened it, so a presenter that goes live when opened does so
in `IShownAsMode.on_mode_shown()`, which this window calls each time a mode
shows, with why.

@par Commands are actions (`EPIC-033D`)
Each module's contributed commands become one `QAction` apiece, in their menu
and, when asked, on their mode's toolbar. A presenter that performs commands
(`CommandPresenter`) binds them as it is built. A command nothing binds stays
disabled and is reported once at the end of the build.

@par The status bar (`EPIC-033H`)
The venue, then what each screen offers as `IStatusSource` (the connection
state), shown in every mode.

@par One Output pane (`EPIC-033F`)
Every screen that keeps a log offers it as a channel (`IOutputSource`); the
window docks one Output pane at the bottom with all of them, and showing a
mode brings its channel forward.

@par The last mode is remembered (HLD §11.2)
The window opens on the mode the last session ended in, as Windows
applications do; the first run opens on the registry's default. It arrives
as `RESTORE`, never `USER_INTENT`, so a screen whose design is "open means
live" can tell a start from a click (`BUG-104`, `BUG-107`).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from PySide6.QtCore import QObject
from PySide6.QtGui import QCloseEvent, QMoveEvent, QPalette, QResizeEvent
from PySide6.QtWidgets import QApplication, QLabel
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_shown_as_mode import (
    IShownAsMode,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.close_confirmation import (
    ConfirmClose,
    ask_before_closing,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.command_actions import (
    action_descriptor,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.mode_perspectives import (
    ModePerspectives,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.shell_navigation import (
    ShellNavigation,
    from_shell_source,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.icon_loader import (
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_presenter import (
    CommandPresenter,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.mode_host import ModeHost
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source import IOutputSource
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import (
    INavigationService,
    IScreenRegistry,
    ScreenDescriptor,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_source import IStatusSource
from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from sagittarius_engine.extensions.pyside_mvc.workbench.access_key_assignment import (
    assign_access_keys,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_confirmation import (
    MessageBoxConfirmer,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.i_options_page import (
    IOptionsPage,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.navigation_service import (
    NavigationSource as ShellNavigationSource,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputPane
from sagittarius_engine.extensions.pyside_mvc.workbench.workbench_shell import (
    ShellMode,
    WorkbenchShell,
)

logger = logging.getLogger("App.Shell.MainWindow")

APPLICATION_NAME = "Sagittarius Elite Warrior"
#: The Dev Board's right column is wide; a smaller first window clips it
#: before the user has resized anything.
_WINDOW_SIZE = (1440, 860)
#: The View menu's own items keep these access keys: T&oolbars, Stat&us bar.
_VIEW_MENU_KEYS = ("o", "u")
_MODE_ICON_SIZE = 24
#: The key `restore_state()` reads the last mode from (`WorkbenchShell`).
_MODE_KEY = "mode"


class MainWindow(WorkbenchShell):
    """The application window: every navigable screen as a mode."""

    def __init__(
        self,
        app_engine,
        screen_registry: IScreenRegistry,
        *,
        venue_text: str = "",
        version_text: str = "",
        state_coordinator: UiStateCoordinator | None = None,
        close_objections: ICloseObjections | None = None,
        confirm_close: ConfirmClose | None = None,
    ) -> None:
        # The commands' owner exists before the window it then belongs to, so
        # every action dies with the window rather than with the application.
        action_owner = QObject()
        registry = ActionRegistry(action_owner, MessageBoxConfirmer())
        super().__init__(
            registry,
            application_name=APPLICATION_NAME,
            about_text=_about_text(venue_text, version_text),
        )
        action_owner.setParent(self)
        self._container = app_engine.context.container
        self._close_objections = close_objections
        #: `None` asks with a message box. Never a lambda over `self`: a
        #: cycle would keep this wrapper alive after Qt deletes the window.
        self._confirm_close = confirm_close
        # Set before any geometry call: `resizeEvent`/`moveEvent` may fire
        # synchronously from `resize()`, and both read it.
        self._state_coordinator = state_coordinator
        self._command_binder: ICommandBinder = registry
        self._commands = tuple(
            (command, registry.contribute(action_descriptor(command)))
            for command in screen_registry.commands()
        )
        self._presenters: dict[str, BasePresenter] = {}
        self._hosts: dict[str, ModeHost] = {}
        self._output = OutputPane(self)
        #: Mode id -> its channel in the Output pane, for modes that have one.
        self._output_channels: dict[str, str] = {}
        self._perspectives = ModePerspectives()
        self._pending_source: ShellNavigationSource | None = None
        self._last_source: ShellNavigationSource | None = None
        self._restored_mode = False
        self._is_shut_down = False

        self.resize(*_WINDOW_SIZE)
        self._show_venue(venue_text)
        self._add_modes(screen_registry.modes())
        self._place_commands()
        self.set_output_pane(self._output)
        self.navigation.mode_changed.connect(self._on_mode_changed)
        self.finish_setup()
        for host in self._hosts.values():
            self._perspectives.register(host)

        if self._state_coordinator is not None:
            self._state_coordinator.restore_into(self._perspectives)
            self._state_coordinator.restore_into(self)
        if not self._restored_mode:
            self.navigate(
                screen_registry.get_default_route(), ShellNavigationSource.RESTORE
            )
        if self._last_source is None and self.current_mode is not None:
            # The mode showing was already current, so no change fired.
            self._announce(self.current_mode, ShellNavigationSource.RESTORE)

    # -- building ------------------------------------------------------------

    def _show_venue(self, venue_text: str) -> None:
        """The venue in text, never by colour alone (MS `vis-color`)."""
        if not venue_text:
            return
        self.setWindowTitle(f"{APPLICATION_NAME} — {venue_text}")
        label = QLabel(venue_text)
        label.setObjectName("workbench::venue")
        self.add_status_widget(label)

    def _add_modes(self, screens: Sequence[ScreenDescriptor]) -> None:
        titles = [screen.nav.title for screen in screens if screen.nav is not None]
        texts = assign_access_keys(titles, _VIEW_MENU_KEYS)
        icon_colour = QApplication.palette().color(QPalette.ColorRole.WindowText)
        for screen, text in zip(screens, texts, strict=True):
            view = screen.view_factory()
            presenter = screen.presenter_class(view, self._container)
            self._presenters[screen.route] = presenter
            if isinstance(presenter, CommandPresenter):
                presenter.bind_commands(self._command_binder)
            channel = view.output_channel() if isinstance(view, IOutputSource) else None
            if channel is not None:
                self._output.add_channel(channel)
                self._output_channels[screen.route] = channel.channel_id
            if isinstance(view, IStatusSource):
                for widget in view.status_widgets():
                    self.add_status_widget(widget)
            host = ModeHost(screen.route, view)
            self._hosts[screen.route] = host
            icon = (
                get_icon_loader().get_icon(
                    screen.nav.icon, icon_colour.name(), _MODE_ICON_SIZE
                )
                if screen.nav is not None
                else None
            )
            self.add_mode(ShellMode(screen.route, text, host, icon=icon))
            logger.debug("Mode %r built", screen.route)
        logger.info("Workbench built %d mode(s): %s", len(screens), list(self._hosts))

    def _place_commands(self) -> None:
        """Puts each toolbar command on its mode's toolbar, or on every
        mode's when it belongs to all of them."""
        for command, action in self._commands:
            if not command.on_toolbar:
                continue
            modes = (command.mode,) if command.mode is not None else tuple(self._hosts)
            for mode in modes:
                host = self._hosts.get(mode)
                if host is not None:
                    host.add_command(action)

    def add_options_page(self, page: IOptionsPage) -> None:
        """One page of Tools → Options; the log line is what proves, from a
        real process, that the composition root added it."""
        super().add_options_page(page)
        logger.info("[options] Tools > Options page %r added", page.title)

    # -- what tests and the composition root read ----------------------------

    @property
    def navigation_service(self) -> INavigationService:
        """The `INavigationService` governing mode changes in this window.

        A new adapter per call, never one held here: it holds the window, and
        a window holding it back is a cycle that keeps this wrapper alive
        after Qt deletes the window."""
        return ShellNavigation(self)

    @property
    def last_source(self) -> ShellNavigationSource | None:
        """Why the showing mode was last shown."""
        return self._last_source

    @property
    def presenters(self) -> Mapping[str, BasePresenter]:
        return dict(self._presenters)

    @property
    def hosts(self) -> Mapping[str, ModeHost]:
        return dict(self._hosts)

    # -- navigating ------------------------------------------------------------

    def switch_screen(self, route_name: str) -> bool:
        """A user's request to show `route_name`, as a click would make it."""
        return self.navigate(route_name, ShellNavigationSource.USER_INTENT)

    def navigate(self, mode_id: str, source: ShellNavigationSource) -> bool:
        """Every mode change passes here — clicks, shortcuts, View, restore —
        so the mode shown hears why (`_on_mode_changed`)."""
        if mode_id == self.current_mode and source is ShellNavigationSource.USER_INTENT:
            # A click on the showing mode changes nothing on the stack, but it
            # is still the user asking for it: a mode restored at start that
            # waits for a click to go live (`BUG-104`) hears that click here.
            self._announce(mode_id, source)
            return True
        self._pending_source = source
        try:
            return super().navigate(mode_id, source)
        finally:
            self._pending_source = None

    def _on_mode_changed(self, mode_id: str) -> None:
        source = self._pending_source or ShellNavigationSource.USER_INTENT
        self._announce(mode_id, source)

    def _announce(self, mode_id: str, source: ShellNavigationSource) -> None:
        self._last_source = source
        presenter = self._presenters[mode_id]
        logger.info("Mode %r shown (%s)", mode_id, source.name)
        channel_id = self._output_channels.get(mode_id)
        if channel_id is not None:
            self._output.show_channel(channel_id)
        if isinstance(presenter, IShownAsMode):
            presenter.on_mode_shown(from_shell_source(source))
        self._mark_dirty()

    # -- closing ---------------------------------------------------------------

    def shutdown(self) -> None:
        """Saves the window and every mode's layout, then disposes every
        presenter, last built first. Safe to call twice."""
        if self._is_shut_down:
            return
        self._is_shut_down = True
        if self._state_coordinator is not None:
            self._state_coordinator.mark_dirty(self._perspectives)
            self._state_coordinator.mark_dirty(self)
            # A pending debounced write does not fire once the event loop
            # stops turning — this is the real safety net, not the timer.
            self._state_coordinator.flush()
        for route, presenter in reversed(tuple(self._presenters.items())):
            try:
                presenter.dispose()
            except Exception:
                logger.exception("Presenter of mode %r failed to dispose", route)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Asks first when a context objects (`EPIC-029F`, ADR O4): a running
        bot's orders stay on the exchange with nobody watching them. Cancel
        keeps the window, and shuts nothing down."""
        reasons = (
            self._close_objections.reasons()
            if self._close_objections is not None
            else ()
        )
        if reasons and not self._close_confirmed(reasons):
            logger.info(
                "Close cancelled: %d objection(s) kept the app open", len(reasons)
            )
            event.ignore()
            return
        super().closeEvent(event)
        if event.isAccepted():
            self.shutdown()

    def _close_confirmed(self, reasons: Sequence[str]) -> bool:
        if self._confirm_close is not None:
            return self._confirm_close(reasons)
        return ask_before_closing(self, reasons)

    # -- remembered state (`IStateContributor`, structural) ---------------------

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="shell")

    def restore_state(self, data: StateData) -> None:
        mode = data.get(_MODE_KEY)
        self._restored_mode = isinstance(mode, str) and mode in self._hosts
        super().restore_state(data)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._mark_dirty()

    def moveEvent(self, event: QMoveEvent) -> None:
        super().moveEvent(event)
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        if self._state_coordinator is not None and not self._is_shut_down:
            self._state_coordinator.mark_dirty(self)


def _about_text(venue_text: str, version_text: str) -> str:
    """Help → About: the name, the version and the venue."""
    lines = [APPLICATION_NAME, "A desktop workbench for Binance trading bots."]
    if version_text:
        lines.append(version_text)
    if venue_text:
        lines.append(f"Venue: {venue_text}")
    return "\n".join(lines)
