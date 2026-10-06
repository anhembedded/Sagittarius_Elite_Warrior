# BUG-153 — The Engine Pin check passes after the engine is replaced by an install that did not go through `engine_pin.py`

- **Reported:** 2026-10-06 (observed by the driving session: after a manual install of a newer engine, `check` still passed)
- **Severity:** 🟡 P2. The gate step `BUG-148` added to stop a machine running an engine CI never built reports success for exactly that machine.
- **Status:** ✅ Fixed (2026-10-06)
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

`scripts/engine_pin.py`, the one place the record lives:

- `record_install` writes the commit and, on a second line, `record-sha256 <hash>`: the hash of the installed distribution's `RECORD` file, read through `importlib.metadata`. `install` calls it after the pip install.
- `installed_engine` reports a recorded commit only while that hash equals the `RECORD` hash of the distribution installed now (`_recorded_commit`). Anything that replaces the distribution (`pip install`, `pip install -U`, `uv pip install`) rewrites `RECORD`, so the record stops matching and `check` reports "an unrecorded commit", the message and exit code it already had. A sidecar from before the fix has no second line and is treated the same way: the next `install` replaces the engine once and records it.
- Why not a file inside `*.dist-info/`: pip removes only the files `RECORD` lists, so an unlisted record could survive a same-version reinstall in the directory the reinstall reuses. The fingerprint needs no cooperation from the installer and is the standard metadata every installer writes.
- `check` and `install` keep their command line and messages. Still stdlib only, no PEP 695.
- A reinstall of the same commit from another temporary directory also rewrites `RECORD` (`direct_url.json` carries the path), so it too reads as unrecorded and `install` runs once more. That is the safe direction.

## Regression test

`tests/unit/scripts/test_engine_pin.py::test_an_engine_replaced_after_install_is_refused`: a real `site-packages` layout under `tmp_path` (package, `*.dist-info` with `METADATA` and `RECORD`), recorded through `record_install`, then the distribution replaced as an installer does. Red before the fix: `pin_problems` returned `[]` (the assertion `problems and "an unrecorded commit" in problems[0]` failed with `assert ([])`); green after. `test_an_installation_whose_record_file_is_unchanged_keeps_its_commit` pins the other direction. No mock stands in for the distribution lookup.

## Verification

- End-to-end in a scratch venv (`install`, then `uv pip install` of engine `bf99528`, then `check`): before the fix `check` exit 0 "is engine.ref's commit"; after, exit 1 "the installed engine is an unrecorded commit; engine.ref pins 07f647f…". A following `install` replaced the engine, recorded it and `check` passed; a second `install` reported it already pinned.
- That run also caught a defect in the first draft (`importlib.metadata.distributions(path=None)` raises on the default search path), which the `tmp_path` tests, which pass explicit directories, could not reach.
- Commit tier: `ci-local.ps1 -SkipTests`, `tests/unit/architecture`, `tests/unit/scripts/test_engine_pin.py` and `test_dependency_pins.py`.
