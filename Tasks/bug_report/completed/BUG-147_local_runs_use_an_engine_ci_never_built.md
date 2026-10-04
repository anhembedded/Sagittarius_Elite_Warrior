# BUG-147 — Launching the app or running the local gate can use an engine CI never built

- **Reported:** 2026-10-04 (found while verifying `BUG-143`'s engine bump; the user asked for the fix)
- **Severity:** 🟢 P3. Nothing failed this time, but a machine could run, and type-check against, a different engine from CI's without a word.
- **Status:** ✅ Fixed (2026-10-04)
- **Context:** `scripts/run-ui.ps1`, `scripts/run.ps1`, `scripts/ci-local.ps1`, `.github/workflows/ci.yml`, `src/infrastructure/engine_adapters/engine_capabilities.py`
- **Environment:** the user's Windows machine (`run-ui.ps1`) and this repository's Linux container (`ci-local.ps1`).

## Reproduction

1. `engine.ref` pins `934b830`. Run `.\scripts\run-ui.ps1`: it installs `git+https://github.com/anhembedded/Sagittarius_Engine.git`, the engine's moving `main`, whatever commit that is today.
2. With an engine checkout beside the app at another commit, run `ci-local.ps1 -SkipTests`: mypy reads that checkout, not the installed engine. In the container it read a checkout at `72e4042` while `engine.ref` pinned another commit.

Expected: every environment uses `engine.ref`'s commit, and the gate fails when it does not.

Actual: only CI followed `engine.ref`; nothing checked anywhere else.

## Root cause

- `EPIC-031B` pinned the engine for CI only: `ci.yml` fetched `engine.ref`'s commit, and `test_dependency_pins.py` checked that file alone.
- The other install sites were never moved to the pin:
  - `run-ui.ps1` installed `main`.
  - `run.ps1` installed no engine.
  - `README.md` taught `main`.
  - `engine_capabilities.REINSTALL_COMMAND`, the app's own hint when an engine API is missing, named `main`.
- `ci-local.ps1`'s mypy step set `MYPYPATH` to the sibling engine checkout and the workspace root. mypy searches `MYPYPATH` before the installed packages, so a checkout's `sagittarius_engine/` won. Probed: with the checkout on `MYPYPATH` mypy parses `<checkout>/sagittarius_engine/domain/base_event.py`; without it, the installed copy in `site-packages`.
- No step compared the engine in use with `engine.ref`.

## Fix

- `scripts/engine_pin.py` is the one installer and the one place naming the engine's repository.
  - `install` fetches `engine.ref`'s commit without submodules, replaces the engine in the running interpreter's environment, and records the commit in `<prefix>/sagittarius_engine.ref`. It does nothing when `check` already passes, so a launcher calls it on every start.
  - `check` fails when the engine the interpreter imports is not under its own `site-packages` (a checkout on `PYTHONPATH`, an editable install), or when the recorded commit is not `engine.ref`'s.
- CI, `run-ui.ps1` and `run.ps1` call `install`. `-LocalEngine` (Option 2) is unchanged.
- `ci-local.ps1` runs `check` as its first step, "Engine Pin", with the tests' `PYTHONPATH`, and puts no engine checkout on `MYPYPATH`.
- `REINSTALL_COMMAND`, `README.md` and `install-rule.md` §1/§2b name the installer.

## Regression test

- `tests/unit/scripts/test_dependency_pins.py`, red before the fix (5 failures):
  - only `scripts/engine_pin.py` names the engine's repository among scripts, `src/`, workflows and `README.md`;
  - `run-ui.ps1`, `run.ps1` and CI install through it;
  - `ci-local.ps1` runs its `check` and names no engine checkout.
- `tests/unit/scripts/test_engine_pin.py`: the pinned installed engine passes; another commit, an unrecorded install, a checkout on the path and a missing engine are each refused with their cause.

## Verification

- In the container, `check` refused the engine installed earlier from a checkout ("an unrecorded commit"). `install` fetched `934b830`, reinstalled it and recorded it, and a second `install` reported it already pinned. With the checkout on `PYTHONPATH`, `check` named the checkout.
- `ci-local.ps1 -SkipTests` passes, with "Engine Pin passed" in its log.
- **Not yet run:** `run-ui.ps1` on the user's Windows machine. The first launch reinstalls the engine once.
