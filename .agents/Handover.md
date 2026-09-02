# Handover — the most recent session, and what to do next

**Frozen at:** 2026-08-25 · **Elite** `f0e63ca` (`master-warrior`) · **Engine** `2d9154b` (`main`)
Both repos: clean tree, pushed, no pending commits.

> **This file is REPLACED every session, never appended to.** The previous version ran to 585 lines and held 3
> "session handover" sections stacked on top of each other from 19–20/08, and by the end of its life it had to carry a warning block
> at the top saying that most of the content below it was **already wrong** (the native chart had been deleted, and the two repos
> were no longer a submodule). A handover file whose reader has to sort truth from falsehood is worse than
> none. Historical context lives in `git log`, in closed task files and in `Tasks/reports/` —
> that is where it belongs. The old version: `git show f0e63ca:.agents/Handover.md`.
>
> **Division of roles, so there are never 2 sources of truth:** this file holds what **changes every session** (where we are,
> what to do next, what was just decided). [`ONBOARDING.md`](ONBOARDING.md) holds what is **stable** (process,
> gate commands, inherent traps, authority). Don't copy between them.

---

## 1. Next up: `EPIC-007A`, in the **Engine** repo

[`EPIC-007`](../Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/README.md) — standardising shared
cards, 0/7. The ordering table in its README has a **Repo** column; the first three tasks (`007A`–`007C`) are in
`Sagittarius_Engine`, the last four here. Don't skip ahead — the table is ordered by increasing risk.

```bash
cd ../Sagittarius_Engine && git pull
```

`007A` does two things: widen the `find_bare_qt_base_widgets` guard to also catch `QWidget` (the current regex
only matches `QFrame|QDialog`, so 7 of Elite's widgets slip through), and implement `ConfirmOverlay` /
`PickerOverlay` — two classes that `widgets/overlay.py` currently **names in an error message but
has never actually had**. The second one requires opening a `BUG` on the Engine side before fixing it (stating something untrue
about the code = a BUG under that repo's rules); the task file says so explicitly.

**Mandatory reading before the first line:** [`EPIC-007/README.md`](../Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/README.md)
and the 4 PlantUML diagrams in `EPIC-007/design/` (2 as-is, 2 to-be). The ADR records decisions that have already been
argued out — re-deriving them costs a session and usually reaches a different answer.

> ### ⚠️ One sentence in `EPIC-007A` has been invalidated by a newer rule
>
> `007A` §2 says *"both satisfy the ≥2 real instances discipline"*, and `EPIC-007` §3.3 is built on
> the same threshold. **The "≥2 real needs before creating an abstraction" threshold was deleted from
> `architecture-rule.md` by the user on 2026-08-25** (commit `ca45e0f`). The current rule is the opposite:
> abstraction is **always encouraged**; when you write a class you must consider its extensibility and
> its API, because a class is a **contract** with other classes.
>
> That does not mean churning out intermediate layers at random — `EPIC-006`'s ADR §2 has a real lesson: the 4
> `ActionCard`/`FormCard`/`StreamCard`/`TableCard` stubs of the old QML kit dissolved on their own once it turned out
> Qt's `setEnabled()` already did the job. But the reason for dropping them was **"Qt already has it"**, not
> **"there's only 1 consumer"**. While doing `007A`, don't use that ≥2 sentence to justify any
> decision; go ahead and fix the wording in the task file if it gets in the way.

### Other open work, if `EPIC-007` gets blocked

| | |
| :--- | :--- |
| `EPIC-001` 1/2 · `EPIC-002` 4/5 · `EPIC-003` 3/6 (1 cancelled) · `EPIC-004` 3/4 | Elite — all in progress, open each epic's README |
| `BUG-030`, `BUG-034` | 2 open Elite bugs, unclaimed |
| Dismantling the Engine's QML kit | **No task file yet.** Blocked on a decision not yet put to the user: flip the sample app's default to `qfluentwidgets`, or split the kit into an optional extension. Elite has no `.qml` left, so it blocks nothing on this side |
| 66 broken links in `Tasks/` | Pre-existing, deliberately deferred to a separate `docs:` commit |

---

## 2. What the last session did

**`EPIC-008` closed 8/8** (`bf88b51`…`9af4ea5`) — standardising the event flow. Elite now has 3 Feeds
(`SystemErrorFeed`, `HealthFeed`, `SyncProgressFeed`) in `presentation/ui/common/`, 3 ports
(`IEventPublisher`, `IConfigReader`, `ICommandDispatcher`) + their adapters, and 4 guards running
in CI. On the Engine side: `BaseEvent` equality, `EventRegistry` warning on duplicate names, a bus that no longer swallows
errors, and `QtEventBridge`.

**`EPIC-006` closed 6/6** (`0112839`) — Elite is **completely free of `.qml`** (22 files deleted + 2 dependent tests,
4,978 lines). The Engine's QML kit **stays** because the sample app needs it.

**Bookkeeping** (`8b049b5`, `f0e63ca`) — `EPIC-005F` closed (done by `006D/E`), `EPIC-003D` cancelled,
plus a new `cancelled/` convention for the epic layout.

## 3. Expensive decisions — don't re-derive them from scratch

**`EPIC-008G` §2 stopped per its own kill criterion, it was not abandoned.** It intended to remove the presenters'
"bridging" signals so workers could emit straight to the UI. Measured for real: **47 of 48 signals bridge
*threads*, not *bus handlers*** — two entirely different things that the task file conflated
into one. A Qt queued signal is the **correct** mechanism for thread affinity. Removing them means creating
cross-thread bugs with your own hands. The evidence behind the decision is in the contract docstring of
`stream_lifecycle_controller.py` itself. Three presenters now carry a Vietnamese banner right above their signal
declarations — **read it before deleting any signal**.

**The 5th guard was dropped, deliberately.** It would have flagged the very Feed pattern the epic had just built. A
false-positive guard is worse than no guard, because people learn to ignore it.

**4 domain events lost `frozen=True`.** Python forbids a `frozen` dataclass inheriting from a non-`frozen`
one, and `BaseEvent` cannot be `frozen` because it has subclasses that write their own `__init__`. This is a trade-off
recorded explicitly in all 4 docstrings and in the rewritten tests — not an oversight. If you plan to
"fix it properly", read the docstrings first.

**Where an event lives = who owns it, not who finds it convenient.** Belongs to one screen → Qt signal. System-wide
/ ≥2 screens → the bus + exactly **one** Feed. The full rule: `architecture-rule.md` §6, and guard 3
enforces it.

**Shared Kernel: exactly 2 Engine symbols** (`IDomainEvent`, `BaseEvent`) are allowed to appear
in Elite's `domain/`+`application/`. Everything else goes through a port.

**New rule, applying to every task from here on:** anything decided to be done later, or any trade-off accepted, must
**be expressed in the code by an Interface/type/test** — the code speaks for itself, rather than
leaving the rule orphaned in a rule file. (`architecture-rule.md` §7)

## 4. Traps found this session, not yet in any rule file

- **`Mock(spec=...)` constrains method names, not return types.** An unconfigured method
  returns a bare `Mock`, and that goes straight into the real handler. This is the source of the 2 errors that `EPIC-008`
  §4 exposed — §4 **revealed** them, it did not **cause** them (A/B'd with `git stash` to prove it,
  before concluding).
- **`StdLogger.__init__` wipes the handlers** of `logging.getLogger("App")`. Two instances wrapping
  the same stdlib logger — creating the second one kills the first one's logging.
- **`__init_subclass__` registers at class-execution time.** To test a name collision you must
  **define** a second class; calling the registration function by hand does not reproduce it.
- **`\bevent_bus\b` does not match `self._event_bus`** — `_` is a word character. One pass was missed
  to this trap; always verify with a second grep pass after every regex rename.
- **`trigger: always_on` in the frontmatter of `.agents/rules/*.md` is not read by Claude Code** —
  it is a convention of the 7 `.agents/Skills/*.prompt.md` files (moved from `.jules/`,
  `EPIC-012`, 27/08). Claude Code only auto-loads
  [`CLAUDE.md`](../CLAUDE.md) (added 2026-08-25, `0de5403`), and that file is **navigation only**.

## 5. What was removed from this file, and why

The old version had a "Test-writing gotchas" section with ~8 bullets on `Repeater`/`findChild`,
`mapToItem`, `ensurePolished`, `SizeRootObjectToView`, `ScrollBar.qml`, `OverlayHost`. **All of them
are QML traps, and Elite now has 0 `.qml` files** — keeping them would only make a reader think this repo
still runs QML. They may still be valuable for the **Engine's** QML kit; if needed, get them from
`git show f0e63ca:.agents/Handover.md`.

Also removed: the "What this project is" and "Where the actual rules live" sections — duplicates of
[`ONBOARDING.md`](ONBOARDING.md) §1/§2/§9 and [`CLAUDE.md`](../CLAUDE.md), and the duplicate had already
drifted into error (it still described the two repos as superproject/submodule for 4 days after the split). The
"How to verify a change" section was removed because `ci-rule.md` §7 + `ONBOARDING.md` §5 are the owners — the
Handover version used to claim there was a `.github/workflows/ci.yml` "running exactly this command", while the
repo **has no `.github/` directory at all**.
