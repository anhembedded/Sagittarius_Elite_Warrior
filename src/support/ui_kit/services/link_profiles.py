"""`EPIC-047D` — the connection profiles the person keeps, and which one the VPS tab uses.

One object holds them and everything that cares follows it (`TickFlashPreference` is the same
shape), remembered across sessions through `ui_state` (`IStateContributor`, structural). It holds
profiles only: no password, no passphrase, no key (`link_profile.py`). Tools → Options → VPS link
edits them; the VPS Bots tab (`EPIC-047E`) reads `selected`.

Capability: Keep the VPS connection profiles (host, port, user, protocol, a key file or the agent) and which one is in use
    Also: connection profile, ssh profile, vps link settings, remote host setting, saved connection, host list
    Use: LinkProfiles
    User: src/shell/options_pages.py
    Status: stable
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProfile,
    problem_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.link_profile_state import (
    profile_from_state,
    profile_to_state,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    JsonValue,
    StateData,
    StateScope,
)

_SCOPE_KEY = "vps_link"


class LinkProfiles:
    """@brief The saved profiles and the selected one; tells its listeners when they change."""

    def __init__(self, on_changed: Callable[[], None] | None = None) -> None:
        self._profiles: tuple[LinkProfile, ...] = ()
        self._selected: str | None = None
        self._on_changed = on_changed
        self._listeners: list[Callable[[], None]] = []

    def set_on_changed(self, on_changed: Callable[[], None]) -> None:
        self._on_changed = on_changed

    @property
    def profiles(self) -> tuple[LinkProfile, ...]:
        return self._profiles

    @property
    def selected_name(self) -> str | None:
        return self._selected

    def selected(self) -> LinkProfile | None:
        return next((p for p in self._profiles if p.name == self._selected), None)

    def replace(self, profiles: tuple[LinkProfile, ...], selected: str | None) -> bool:
        """Keep exactly `profiles`, `selected` among them; `False` (nothing changes) when it is so already.

        @raise ValueError a profile `problem_of` refuses, a name twice, or `selected` not among them."""
        for profile in profiles:
            problem = problem_of(profile)
            if problem is not None:
                raise ValueError(f"{profile.name or 'a profile'}: {problem}")
        names = [p.name for p in profiles]
        if len(set(names)) != len(names):
            raise ValueError("two profiles have the same name")
        if selected is not None and selected not in names:
            raise ValueError(f"the selected profile {selected!r} is not among them")
        if profiles == self._profiles and selected == self._selected:
            return False
        self._profiles, self._selected = profiles, selected
        for listener in tuple(self._listeners):
            listener()
        if self._on_changed is not None:
            self._on_changed()
        return True

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    # -- IStateContributor (structural, no base class) ------------------- #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=_SCOPE_KEY)

    def capture_state(self) -> StateData:
        profiles: list[JsonValue] = [profile_to_state(p) for p in self._profiles]
        return {"profiles": profiles, "selected": self._selected}

    def restore_state(self, data: StateData) -> None:
        """A restore announces nothing (`EPIC-010`). An entry that cannot be read is dropped, with a warning."""
        raw = data.get("profiles")
        read = (
            [profile_from_state(item) for item in raw] if isinstance(raw, list) else []
        )
        kept: list[LinkProfile] = []
        for profile in read:
            if profile is not None and all(profile.name != k.name for k in kept):
                kept.append(profile)
        chosen = data.get("selected")
        self._profiles = tuple(kept)
        self._selected = (
            chosen
            if isinstance(chosen, str) and any(p.name == chosen for p in kept)
            else None
        )
