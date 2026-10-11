# BOT-175 — run.ps1 is the only start point, with -UI or -CLI

**Status:** ✅ Done (2026-10-11)
**Board:** `scripts/run.ps1` is the one launcher (`-UI` default, `-CLI` passes its arguments to `src/main.py`); `run-ui.ps1` deleted because the old `run.ps1` had rotted unused while `run-ui.ps1` was the one the owner ran.
**Source:** Owner, 2026-10-11: "run.ps1 đang quá outdate rùi, từ lâu tui ko dùng nó, giờ sửa run-ui.ps1 -> run.ps1 -UI or -CLI. chỉ 1 điểm start thui" — run.ps1 is badly outdated and unused; make it the single start script with -UI or -CLI.
**Risk:** 🟢 — a launcher script and its guards; no application code.
**Complexity:** S — one script merged, references renamed.
**Depends on:** None

---

## 1. Context and problem
Two launchers existed: `run-ui.ps1` (venv, requirements, engine, GUI; the one in use) and `run.ps1` (a stale copy that started `src/main.py`). Two start points drifted (`BUG-148` was one such drift).

## 2. Acceptance criteria
- [x] `scripts/run.ps1` keeps run-ui.ps1's venv, requirements, engine and `-LocalEngine` logic; `-UI` (default) starts `app_bootstrapper.py`, `-CLI` starts `src/main.py` with every other argument passed through, none opening the REPL.
- [x] `-UI` with `-CLI` prints a message and exits 2 before any setup.
- [x] The Python process's exit code is the script's.
- [x] `scripts/run-ui.ps1` is deleted; every live reference outside `Tasks/` is updated.
- [x] The entry-point guard keeps its strength and gains contract checks.

## 3. Design
Remaining arguments are the automatic `$args`, not `ValueFromRemainingArguments`: that needs a `[Parameter]` attribute, which makes the script advanced and adds the common `-Debug`, a name collision with the `-Debug` switch the owner uses. `-Dev`/`-Debug` with `-CLI` are refused with a message: `src/main.py` has no `--dev`/`--debug` in its parser, and forwarding them would break it. Giving the CLI those flags is part of the later launcher refactor (`EPIC-038`), not this task.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/run.ps1` | run-ui.ps1's logic plus `-UI`/`-CLI`, pass-through, exit code |
| `scripts/run-ui.ps1` | deleted |
| `tests/unit/scripts/test_run_entry_point.py` | renamed from `test_run_ui_entry_point.py`; checks both entry files, the contract, and (with pwsh) `-UI -CLI` |
| `tests/unit/scripts/test_dependency_pins.py` | single launcher in the pinned-engine check |
| `README.md`, `.claude/rules/install-rule.md`, `scripts/ci-local.ps1`, `scripts/engine_pin.py`, `indicator_coordinator.py` | new usage / wording only |

## 5. Testing
Unit tier: `tests/unit/scripts/`. Manual with pwsh 7.4: `-UI -CLI` → exit 2; `-CLI -Dev` → exit 2; stray argument in UI mode → exit 2; with a stub venv python, `-CLI exchange-status --json`, `-CLI`, `-UI -Dev`, `-Debug` and no switch reached the expected entry file and arguments.

## Implementation notes (written when done)
Delivery state: draft PR; `-Full` run on GitHub pending. Not run here: a real `-UI`/`-CLI` start (no display, no engine install).
