# BUG-146 — `run-ui.ps1` exits without opening a window

- **Reported:** 2026-10-04 (by the user, in chat, right after `EPIC-033C` (#345) merged)
- **Severity:** 🔴 P1 — the app does not start from its documented Windows launcher
- **Status:** ✅ Fixed (2026-10-04)
- **Context:** App start → `scripts/run-ui.ps1` → `src/presentation/ui/` entry point
- **Environment:** Windows, `.\scripts\run-ui.ps1 -Dev`, `master-warrior` after `EPIC-033C`

## Reproduction
1. On `master-warrior` after `EPIC-033C`, run `.\scripts\run-ui.ps1 -Dev`.
2. Expected: the workbench window opens.
3. Actual: the console prints `Starting PySide6 Trading Bot UI (dev mode — log level DEBUG)...` and returns to the prompt. There is no window, no error and no log file. It happens every time.

## Symptom
The last line of the launcher's own output is `Starting PySide6 Trading Bot UI (dev mode — log level DEBUG)...`. Python exits with code 0 and prints nothing.

## Root cause
- **The launcher runs the wrong file.** `scripts/run-ui.ps1:131` ran `src/presentation/ui/main_window.py` as a script. That file started the app only through a legacy `if __name__ == "__main__"` block that forwarded to `app_bootstrapper.main()`.
- **The forwarding block is gone.** `EPIC-033C` rewrote `main_window.py` as `MainWindow(WorkbenchShell)` and dropped that block. Running the file as a script therefore defines classes and exits.
- **The real entry point was never launched directly.** `src/presentation/ui/app_bootstrapper.py` owns `if __name__ == "__main__": main()`. The launcher reached it only by way of the other file.
- **The gate was green while this was live.** The sanity tier's `--self-check` and every boot test start the app with `python -m ...app_bootstrapper`, which is not the launcher's path. No test read the launcher. The net that was missing is the launcher itself. That gap is closed by the regression test below, so no case study is needed.

## Fix
`scripts/run-ui.ps1` now launches `src/presentation/ui/app_bootstrapper.py`, the file that owns `main()`. Nothing forwards from another module, so a rewrite of `main_window.py` cannot silence the launcher again.

## Regression test
- **Test:** `tests/unit/scripts/test_run_ui_entry_point.py::test_the_launcher_runs_a_file_that_starts_the_app`. It reads `$UIEntry` from the launcher, resolves the file, and requires a top-level `if __name__ == "__main__":` block that calls `main()`.
- **Before the fix:** it failed with "run-ui.ps1 launches src/presentation/ui/main_window.py, which has no `if __name__ == "__main__": main()` block".
- **After the fix:** it passes.

## Verification
- **Regression test:** red before the fix, green after.
- **Commit tier:** run before the commit.
- **Reproduced in the launcher's environment** (`PYTHONPATH` set to the checkout's parent, the file run as a script, `--self-check`, offscreen):
  - **Before:** `main_window.py` exits 0 with zero lines of output, the user's symptom exactly.
  - **After:** `app_bootstrapper.py` exits 0. It logs `App.Shell.Contributions - INFO - Contributions collected: 8 screen(s)` and then the engine shutdown, with no traceback. This is positive proof that the real boot ran.
