# BUG-153 — The Engine Pin check passes after the engine is replaced by an install that did not go through `engine_pin.py`

- **Reported:** 2026-10-06 (observed by the driving session: after a manual install of a newer engine, `check` still passed)
- **Severity:** 🟡 P2. The gate step `BUG-148` added to stop a machine running an engine CI never built reports success for exactly that machine.
- **Status:** Open
- **Context:** `scripts/engine_pin.py` (`check`, `install`) → the "Engine Pin" step of `scripts/ci-local.ps1`, `run.ps1`, `run-ui.ps1`
- **Environment:** Linux container, Python 3.12 venv, uv 0.x; engine pin `07f647f`, replacement engine `bf99528`.

## Reproduction

1. `uv venv /tmp/scratchvenv --python 3.12`, then `python scripts/engine_pin.py install` with that interpreter: installs `07f647f`, `check` passes.
2. Replace the engine without the installer: fetch another engine commit (`bf99528`) and `uv pip install <checkout>` (`pip install`, `pip install -U` do the same).
3. `python scripts/engine_pin.py check`.

Expected: exit 1, "the installed engine is an unrecorded commit; engine.ref pins 07f647f…".

Actual: exit 0, "sagittarius_engine is engine.ref's commit". Frequency: every time.

## Symptom

```
== install pinned
[engine-pin] installing sagittarius_engine at 07f647f6fc3c55f1b8ef5bbe6334f704fef5e807
[engine-pin] sagittarius_engine is engine.ref's commit
== manual install of another engine commit
installed distribution's direct_url.json: {"url":"file:///tmp/tmp.edkcZEg4Kk","dir_info":{}}
== check
[engine-pin] sagittarius_engine is engine.ref's commit
exit=0
```

## Root cause

`scripts/engine_pin.py` `_record_path()` keeps the installed commit in `<sys.prefix>/sagittarius_engine.ref`, a file beside the environment and owned by nothing. `installed_engine()` reads it and `pin_problems` compares it with `engine.ref`. Nothing ties that file to the distribution it describes, so any install that replaces the distribution leaves the file saying the old commit. The check answered "what did `install` last write", not "which engine is installed".

The Engine Pin step was green on a net it was written to close (`BUG-148`); its tests only fed `pin_problems` a hand-built `EngineInstall`, so the binding between record and distribution was never exercised.

## Fix

Not yet applied.

## Regression test

Not yet written.

## Verification

Not run.

## Suggested next steps

Bind the record to the installed distribution (fingerprint of its `RECORD` file via `importlib.metadata`, compared at `check`).
