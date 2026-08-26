"""`StateScope`/`Lifetime` — the address type `EPIC-010` keys every slice by."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    Lifetime,
    StateScope,
)


def test_singleton_scope_uses_the_bare_key_on_disk():
    """A singleton's `storage_key` must stay readable in the raw JSON — no
    `#None` suffix — because that file is meant to be `cat`-able."""
    scope = StateScope(key="dashboard")

    assert scope.is_singleton
    assert scope.storage_key == "dashboard"


def test_per_instance_scope_encodes_identity_into_the_key():
    scope = StateScope(key="dashboard", instance_id="7f3a")

    assert not scope.is_singleton
    assert scope.storage_key == "dashboard#7f3a"


def test_as_default_strips_identity_and_forces_persistent():
    """The default template a new instance seeds from is always the singleton,
    always `PERSISTENT` — a `SESSION` template would die with the process that
    was supposed to seed the NEXT one."""
    live_tab = StateScope(
        key="dashboard", instance_id="7f3a", lifetime=Lifetime.SESSION
    )

    default = live_tab.as_default()

    assert default.instance_id is None
    assert default.lifetime is Lifetime.PERSISTENT
    assert default.key == "dashboard"


def test_scope_is_frozen_and_hashable():
    """Frozen per `code-quality-rule.md` §1, and hashable is the point: it is a
    dict key inside `UiStateCoordinator`'s dirty-tracking (`010B`)."""
    a = StateScope(key="dashboard")
    b = StateScope(key="dashboard")

    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_instance_id_accepts_a_composed_path():
    """Identity may nest (window -> tab -> panel); nothing here may assume the
    id is flat or separator-free (`EPIC-010` design §1.1)."""
    scope = StateScope(key="dashboard", instance_id="window-2/tab-3")

    assert scope.storage_key == "dashboard#window-2/tab-3"
