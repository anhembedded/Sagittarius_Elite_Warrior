"""`EPIC-010H` — forgetting single remembered values, not whole slices.

@details The precedence rule this exists for:

    ui_state  >  user_config DEFAULT_*  >  module constants

A remembered value outranks the Settings default, so changing that default has
to drop the remembered one — otherwise the user edits Settings, presses Save,
and nothing appears to happen.

`discard()` could not do that job: it drops the whole slice, so invalidating
one symbol would also throw away leverage, commission, the timezone and the
script checklist. Hence a second, narrower verb.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.config_manager_state_store import (
    ConfigManagerStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.null_state_store import (
    NullStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.repo_state_store_locator import (
    RepoStateStoreLocator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope

_SCOPE = StateScope(key="backtest")
_FULL = {"symbol": "BTCUSDT", "timeframe": "1m", "long_leverage": 3.0}


@pytest.fixture(params=["in_memory", "config_manager"])
def store(request, tmp_path):
    """Both real stores, so the verb cannot be implemented for one and
    silently forgotten in the other."""
    if request.param == "in_memory":
        return InMemoryStateStore()
    return ConfigManagerStateStore(RepoStateStoreLocator(repo_root=tmp_path))


def test_only_the_named_keys_are_forgotten(store):
    store.write(_SCOPE, _FULL)

    store.discard_keys(_SCOPE, ["symbol", "timeframe"])

    assert store.read(_SCOPE) == {"long_leverage": 3.0}


def test_a_key_the_slice_never_held_is_ignored(store):
    store.write(_SCOPE, _FULL)

    store.discard_keys(_SCOPE, ["never_stored"])

    assert store.read(_SCOPE) == _FULL


def test_discarding_from_a_slice_that_does_not_exist_does_not_raise(store):
    store.discard_keys(StateScope(key="never_written"), ["symbol"])

    assert store.read(StateScope(key="never_written")) == {}


def test_other_slices_are_untouched(store):
    store.write(_SCOPE, _FULL)
    store.write(StateScope(key="dashboard"), {"symbol": "ETHUSDT"})

    store.discard_keys(_SCOPE, ["symbol"])

    assert store.read(StateScope(key="dashboard")) == {"symbol": "ETHUSDT"}


def test_discarding_everything_is_not_the_same_as_discarding_the_slice(store):
    """A slice emptied key-by-key must still read back as an empty slice, not
    blow up — the two verbs converge here rather than conflicting."""
    store.write(_SCOPE, _FULL)

    store.discard_keys(_SCOPE, list(_FULL))

    assert store.read(_SCOPE) == {}


def test_a_caller_that_kept_the_mapping_it_wrote_does_not_see_it_change(store):
    """The stores hand back `StateData`, a read-only Mapping. Mutating a
    stored slice in place would change a mapping the caller still holds."""
    written = dict(_FULL)
    store.write(_SCOPE, written)

    store.discard_keys(_SCOPE, ["symbol"])

    assert written == _FULL


def test_the_null_store_is_a_harmless_no_op():
    NullStateStore().discard_keys(_SCOPE, ["symbol"])
