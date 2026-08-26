"""`EPIC-010` D1 probe — can a SECOND `ConfigManager` instance be the ui_state store?

Exists so D1's decision is re-verifiable in one command instead of trusted as
prose. `EPIC-010`'s design picks option **B2**: keep `state/ui_state.json` a
separate file (credentials and git-tracking make sharing `user_config.json`
untenable) while keeping exactly **one persistence paradigm** in the project —
the `ConfigManager` the app already uses everywhere else.

That choice only holds if four properties are true of the engine's
`ConfigManager`. They are asserted nowhere and are not documented upstream, so
they are measured here rather than assumed:

    H1  a nested dict slice survives set() + save()
    H2  writing ONE slice leaves the other slices on disk untouched
        -> this is design decision D2 (slice-merge) available for free, and it
           is what makes lazy-loaded presenters safe: a session that only opens
           the Dev Board must not erase the Backtest slice
    H3  a truncated JSON file degrades to {} WITHOUT raising
        -> failure mode #9; also locks the accepted cost in design §4.1.3
           (save() is not atomic, so a crash mid-write must fail safe)
    H4  two ConfigManager instances stay isolated — the state store must never
        be able to read API_KEY, and writing state must never touch
        user_config.json

Run:
    PYTHONPATH=. .venv/bin/python scripts/ui_state_store_feasibility_probe.py

Exit code 0 = every hypothesis holds, B2 is viable. Non-zero = D1 must be
revisited, because the reasoning it rests on no longer matches the engine.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_SECRET = "secret-must-not-move"  # noqa: S105 - probe fixture, not a credential


class ProbeError(RuntimeError):
    """Raised when a hypothesis D1 depends on no longer holds."""


def _check(condition: bool, message: str) -> None:
    """Explicit raise rather than `assert` — probes must not lose their checks
    when Python runs with `-O`, and the repo's lint gate rejects bare asserts
    outside `tests/`.
    """
    if not condition:
        raise ProbeError(message)


def _read_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def _store_for(path: str) -> ConfigManager:
    manager = ConfigManager()
    manager.load_json(path, writable=True)
    return manager


def probe_h1_nested_slice_round_trips(state_path: str) -> None:
    print("H1 — a nested dict slice survives set() + save()")
    store = _store_for(state_path)
    store.set("schema_version", 1)
    store.set("dashboard", {"symbol": "BTCUSDT", "interval": "5m"})
    store.set("backtest", {"strategy_key": "ema_pullback", "initial_capital": "5000"})
    store.save()

    on_disk = _read_json(state_path)
    print(json.dumps(on_disk, indent=2, ensure_ascii=False))
    _check(on_disk["dashboard"]["symbol"] == "BTCUSDT", "H1: dashboard slice lost")
    _check(on_disk["backtest"]["strategy_key"] == "ema_pullback", "H1: backtest lost")
    print("H1 PASS — nested dicts persist and read back intact\n")


def probe_h2_writing_one_slice_preserves_others(state_path: str) -> None:
    print("H2 — a session that only opens the Dev Board must not erase Backtest")
    store = _store_for(state_path)
    # This session touched ONLY the Dev Board, so only its slice is set().
    store.set("dashboard", {"symbol": "SOLUSDT", "interval": "1h"})
    store.save()

    after = _read_json(state_path)
    print(json.dumps(after, indent=2, ensure_ascii=False))
    _check(after["dashboard"]["symbol"] == "SOLUSDT", "H2: new slice not written")
    _check("backtest" in after, "H2: UNVISITED backtest slice was ERASED — D2 broken")
    _check(after["backtest"]["initial_capital"] == "5000", "H2: backtest slice mangled")
    print("H2 PASS — slice-merge (D2) works for free, no custom I/O needed\n")


def probe_h3_truncated_file_fails_safe(state_path: str) -> None:
    print("H3 — a truncated file (crash mid-write) must degrade, not raise")
    with open(state_path, "w", encoding="utf-8") as handle:
        handle.write('{"dashboard": {"symbol": "BTC')

    store = _store_for(state_path)
    value = store.get("dashboard", "FALLBACK")
    print(f"  get() returned {value!r} without raising")
    _check(value == "FALLBACK", "H3: corrupt file did not fall back to the default")
    print("H3 PASS — corrupt state cannot block boot; the accepted cost is safe\n")


def probe_h4_stores_stay_isolated(state_path: str, user_path: str) -> None:
    print("H4 — the state store must never see or touch credentials")
    user_store = _store_for(user_path)
    state_store = _store_for(state_path)
    state_store.set("dashboard", {"symbol": "ETHUSDT"})
    state_store.save()

    user_after = _read_json(user_path)
    print(f"  user_config.json after a state write: {user_after}")
    _check(user_after.get("API_KEY") == _SECRET, "H4: user_config.json was mutated")
    _check("dashboard" not in user_after, "H4: state leaked into user_config.json")
    _check(user_store.get("API_KEY") == _SECRET, "H4: real config stopped resolving")
    _check(state_store.get("API_KEY") is None, "H4: state store can READ credentials")
    print("H4 PASS — the two stores are fully isolated\n")


def main() -> None:
    root = tempfile.mkdtemp()
    state_path = os.path.join(root, "state", "ui_state.json")
    user_path = os.path.join(root, "config", "user_config.json")
    _write_json(user_path, {"API_KEY": _SECRET, "DEFAULT_INTERVAL": "1m"})

    for probe in (
        lambda: probe_h1_nested_slice_round_trips(state_path),
        lambda: probe_h2_writing_one_slice_preserves_others(state_path),
        lambda: probe_h3_truncated_file_fails_safe(state_path),
        lambda: probe_h4_stores_stay_isolated(state_path, user_path),
    ):
        print("=" * 70)
        probe()

    print("=" * 70)
    print("ALL FOUR HOLD — EPIC-010 D1 option B2 is viable.")
    print("Free from ConfigManager: slice-merge (D2) and fail-safe corruption (#9).")
    print("Still owed by us: save() is NOT atomic — see design doc section 4.1.3.")


if __name__ == "__main__":
    main()
