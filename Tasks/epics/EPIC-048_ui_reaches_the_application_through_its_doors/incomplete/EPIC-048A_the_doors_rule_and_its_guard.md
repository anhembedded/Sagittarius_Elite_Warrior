# EPIC-048A — The rule for the UI's doors is written, and a guard that only shrinks holds it

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24 (*"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"*, "decide them for me, consistent with the whole Constitution"), settled as G9 of the EPIC-047 charter; the [decision record](../DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) D1–D4.
**Risk:** 🟡 — a guard that scans 441 files and imports modules can be slow or flaky, and a wrong classification either blocks work or lets bypasses in.
**Complexity:** M — one rule section and one test with a baseline file; the method exists as a spike.
**Epic:** [EPIC-048](../README.md)
**Depends on:** None

---

## 1. Context and problem
`architecture-rule.md` §3 says a module imports another only through its `contracts/`, and says nothing about how the UI reaches the application. De-risk R7 (DERISK §7.3, at `5ddbd68`) found **215 imports in 82 files over 18 screen areas** that reach application services, application internals, adapters or behavioural ports outside the doors, and **30 functions under `ui/` that take the whole `IContainer`**. Nothing stops a 216th. EPIC-047 cannot put a remote backend behind a screen that bypasses the doors.

## 2. Acceptance criteria
- [ ] `.claude/rules/architecture-rule.md` states the rule of ADR D1: the UI reaches the application through `ICommandDispatcher`, `IEventPublisher` and `IEventBus`, plus the UI-only allowlist (`INotifier`, `IRealMoneyConsent`, `IThreadManager`, `IInstanceAccess`, `IDisplayTimezonePreference`, `IDisplayPreferences`) and the pure-code ports `IBotKind`, `IBotKindCatalog` and `ICandleFeed`; the section carries its `[guard: …]` tag, and `python3 scripts/check_skill_prompt_references.py` passes.
- [ ] A test in `tests/unit/architecture/` reads the UI tree with DERISK §7.2's method and compares each area's counts (`APP_SERVICE`, `APP_OTHER`, `ADAPTER`, `PORT`, split `fn` and `data`) and the count of functions that take `IContainer` with a committed baseline file.
- [ ] The first baseline is **measured by this task**, not copied: it starts from R7's 215 imports, 82 files and 30 container-taking functions less the 18 imports the allowlist now admits (197 expected). The task records the measured numbers and any difference from R7 in its Implementation notes.
- [ ] The guard fails when a count rises, and fails with a message that names the file, the imported name and its class. A count that falls fails until the baseline is lowered in the same pull request (a ratchet, `P8`).
- [ ] Mutation check (`testing-rule.md`): a planted new application-service import in a UI file turns the guard red; removing an existing one without lowering the baseline turns it red; both revert green.
- [ ] The guard runs in the full gate in a time the task records, and creates no stray file or `ResourceWarning`.
- [ ] `data` imports are a second baseline line (ADR D4); a new `fn`, port or adapter import fails at once.

## 3. Design
The guard mirrors the repository's own baseline guards (`tests/unit/architecture/baseline_*.txt`, `test_module_boundaries.py`) and the spike `scan_ui_doors.py` of DERISK §7.2 (`ast` plus `importlib`): the classification, the `USE_CASE_MESSAGE` pattern and the `IContainer` parameter check come from there. The allowlist lives in one place the guard and the rule both name (`P3`); the rule cites the file and does not repeat the names where a copy would drift. The baseline file holds counts per area, not file lists, so an unrelated import rename does not churn it. Pure-code ports are allowed because they are code or public data, not host facts (ADR D2).

## 3a. Reuse
Checked `.claude/rules/capabilities.md` and `tests/unit/architecture/`: `scanned_roots_registry.py`, `screen_files.py` and `guard_scan_resolver.py` may already list the UI roots; `used` if they do, with the file named in the notes; `not used because …` otherwise. The spike is the starting point, not a dependency.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/architecture-rule.md` | the rule text (new subsection under §3) with its guard tag |
| `tests/unit/architecture/test_ui_reaches_the_application_through_its_doors.py` | the guard (name proposed) |
| `tests/unit/architecture/baseline_ui_doors.json` | the counts per area, the container count (name proposed) |
| `.claude/README.md` | the manifest row if the rule file's description changes |

## 5. Testing
Tier: architecture guard, in the unit tier (`ci-rule.md` §2). Each acceptance item maps to the guard itself and to the mutation check above, run by hand and recorded with the red and green output. The full gate's job log is read for `FAILED|ERROR|Traceback|ResourceWarning`. Not run.

## 6. Docs touched
`.claude/rules/architecture-rule.md` (§3). `Docs/VOCABULARY/README.md`: an entry for "the UI's doors" if the rule coins the word.

## Implementation notes (written when done)
Not written: not started.
