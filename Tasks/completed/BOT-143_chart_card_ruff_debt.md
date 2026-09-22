# BOT-143 — `master-warrior` fails `ci-local.ps1 -Full`'s Ruff Lint/Format steps on every PR

**Status:** ✅ Done (2026-09-22)
**Source:** Surfaced by `PR #248`'s stand-down comment (2026-09-21) and independently reproduced three more times while driving `PR #249` (`BOT-141`) to green — by the author and by two independent reviewer sessions, with reproduced error counts disagreeing (3, 22, 77) depending on the checkout directory's own name (see Design).
**Risk:** 🟢 — two named constants and a `ruff format` pass on 3 files; no behavior change, confirmed by the full charting + architecture unit tiers passing unchanged.
**Complexity:** S — mechanical.
**Epic (optional):** None
**SPEC (optional):** None
**Depends on:** None

---

## 1. Context and problem

`master-warrior` @ `e9330e7` (and its predecessor commits, per `PR #248`'s comment) fails GitHub Actions' `ci-local.ps1 -Full` check on `Ruff Lint` and `Ruff Format`, so **every** code PR built on it inherits a red CI it did not cause. Three `PLR2004` "magic value" lint errors:

- `src/support/charting/chart_card/plot_layout.py:187` — `x_limits[0] > -1e300`
- `src/support/charting/chart_card/plot_layout.py:192` — `x_limits[1] < 1e300`
- `src/support/charting/chart_card/cached_frame_interaction.py:428` — `len(x_range_limits) >= 2`

and 3 files needing `ruff format`: the same two files plus `tests/unit/support/charting/test_chart_view_bounds.py:166`.

## 2. Acceptance criteria

- [x] `ruff check src tests tools scripts` passes clean on the fixed tree.
- [x] `ruff format --check src tests tools scripts` passes clean on the fixed tree.
- [x] No behavior change: the affected charting unit tests (199) and the full architecture tier (425) pass unchanged.
- [x] The two `PLR2004` values get named constants with a comment explaining what they represent, not a bare `# noqa`.

## 3. Design

**Root-cause note on the disagreeing reproduction counts (3 vs 22 vs 77).** Every prior reproduction that reported extra `I001` "unsorted imports" errors (19 or more, across files in `scripts/`) was run from a checkout directory *not* literally named `Sagittarius_Elite_Warrior` (a generic worktree or clone path). This repository has no `[tool.ruff.lint.isort] known-first-party` setting, so ruff's isort falls back to inferring the project's own package name from the checkout directory's name to classify `from Sagittarius_Elite_Warrior.src...` imports as first-party vs. third-party — get that wrong and every such import sorts as third-party, producing spurious `I001` findings that do not reproduce in a correctly-named checkout and that GitHub Actions' own checkout (which always names the directory after the repo) never sees either. Verified directly: an identical worktree at `/tmp/ruff-fix` reported 19 extra `I001` errors; the same content copied to `/tmp/Sagittarius_Elite_Warrior` reported zero. **The real, CI-matching failure is exactly the 3 lint + 3 format issues above** — confirmed as the actual `FAILED_STEPS` cause by fixing precisely those and nothing else, then re-running both commands clean. Scope stayed to that; the `I001` question is noted here rather than "fixed" since it was never a real defect. Worth a `process-drift`/`.claude/rules/install-rule.md` note that ruff reproduction must run from a directory named `Sagittarius_Elite_Warrior`; not added as a separate task since it's a two-line caution, not a mechanism.

**Named constants over bare literals**, per `code/quality.md` §4 ("shared keys live in `config_keys.py` or `constants.py`" — here, module-scoped since each constant is meaningful only within its one file): `_PYQTGRAPH_UNBOUNDED_LIMIT = 1e300` (pyqtgraph's own "no limit set" sentinel for a `ViewBox` axis) and `_RANGE_PAIR_LENGTH = 2` (a `[min, max]` pair has exactly two elements). Both get a one-line docstring comment stating what the value represents, not just satisfying the linter.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/support/charting/chart_card/plot_layout.py` | Add `_PYQTGRAPH_UNBOUNDED_LIMIT = 1e300`; use it at both comparison sites; `ruff format`. |
| `src/support/charting/chart_card/cached_frame_interaction.py` | Add `_RANGE_PAIR_LENGTH = 2`; use it at the one comparison site; `ruff format`. |
| `tests/unit/support/charting/test_chart_view_bounds.py` | `ruff format` only — no logic change. |

## 5. Testing

`ruff check`/`ruff format --check src tests tools scripts` — clean (was `FAILED_STEPS: Ruff Lint,Ruff Format`). `pytest tests/unit/support/charting -q` — 199 passed (no behavior change to the pyqtgraph limit-clamping or pan/zoom math). `pytest tests/unit/architecture -q` — 425 passed. Full `tests/unit -q` run in progress at time of writing; see Implementation notes for the final count.

## Implementation notes (written when done)

Fixed on a fresh branch off `origin/master-warrior` (`e9330e7`), not stacked on `BOT-141`'s branch — this is unrelated pre-existing debt, not part of that task's scope (`ONBOARDING.md` §7, `commit-rule.md` §3 "Atomic Change"). See §3 above for the reproduction-count root cause — this took longer to pin down than the fix itself, and is worth remembering the next time a ruff count doesn't match between two sessions.

Verification: `ruff check`/`ruff format --check src tests tools scripts` clean; `tests/unit/support/charting` (199) and `tests/unit/architecture` (425) passed against the fixed tree; full `tests/unit -q` — 4901 passed, 7 pre-existing unrelated warnings (Qt/`websockets`/`pyqtgraph` deprecations), 0 failures. No production behavior changed — both constants replace a literal with the identical value, and `ruff format` only reflows already-equivalent expressions.
