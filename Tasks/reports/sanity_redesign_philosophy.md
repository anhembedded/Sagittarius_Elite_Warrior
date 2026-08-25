# Rebuilding the Sanity Tier — Principles, Not Patches

> [!NOTE]
> **Companion to [`sanity_tier_audit_and_remediation.md`](sanity_tier_audit_and_remediation.md).**
> That report says what is broken and lists P0/P1/P2 repairs. This one answers
> a different question the audit deliberately did not: *what should the tier
> have been, such that it could not have rotted this way?*
>
> These are two different documents on purpose. The repairs are worth doing
> even if this redesign is rejected. The redesign is worth doing even if every
> repair lands — because repairs restore the tier to a design that already
> failed once.

---

## 1. The design error, in one sentence

**The tier was defined by its mechanism instead of by its question.**

`code-rule.md` §4 defines Sanity as: *"boot the real app, construct real View +
Presenter, assert real DI resolves and `quick_widget.errors() == []`"*. Every
clause is a **how**. There is no **why** anywhere in the contract.

So when the how became obsolete — EPIC-006 migrated the UI off QML entirely,
and `QQuickWidget` stopped existing in this app — the tier had nothing to fall
back on. It kept executing the parts of the mechanism that still ran, silently
stopped proving the part that didn't, and reported green throughout. Nobody
noticed, because "38 sanity passed" looks identical whether the tier is
proving something or nothing.

A tier defined by a question survives a change of mechanism. A tier defined by
a mechanism dies with it — and does not notice it has died. That is the whole
failure, and no amount of patching the current tests addresses it.

---

## 2. The question Sanity uniquely answers

Sanity is the **only** tier that boots the real composition root and then
stops. Unit fakes the root. Integration boots it but immediately starts
driving behaviour through it. Desktop E2E boots it but is expensive, opt-in
and rare.

That leaves exactly one question nothing else asks:

> **Can the thing production assembles come into existence at all — and does
> it assemble in silence?**

Not *is it correct* (Unit). Not *does it do what the user wanted*
(Integration). Not *what does the user see* (Desktop E2E). Only: **does it come
into being, does anything scream while it does, and can it be shut down again.**

Every principle below is derived from that sentence. Nothing below mentions a
UI framework, because the question does not.

---

## 3. Eight principles

### P1 — Define the tier by its question; never name a mechanism in the contract

The rewritten contract states four obligations and no implementation:

1. Everything the composition root registers **resolves**.
2. Everything a user can reach **constructs**.
3. Nothing **complains** on any channel while (1) and (2) happen.
4. The result can be **shut down** within a budget.

Not one word about QML, QtWidgets, `QQuickWidget` or any successor. When the UI
framework changes again — and on this project's history it will — the contract
survives untouched and only the fixtures move.

### P2 — Sanity is a property of the whole; it must not grow with features

This is the structural cause of everything the audit found.

The current rule says *"every new feature/screen ships construction-only sanity
coverage"*. Follow that faithfully and you get precisely today's tier: 9 files,
6 near-copies of one boot fixture, 2 hand-written command allowlists, 4 tests
each pinned to one strategy name — **and still only 2 of 4 screens ever
constructed.** Per-feature sanity is a contradiction in terms. Composition is a
whole-system property; it cannot be proven one feature at a time, and trying
guarantees the gaps land exactly where nobody thought to look.

Invert the rule:

> **Adding a feature must add zero sanity tests.** If a new screen needs a new
> sanity test, the existing sanity tests were written wrong.

This is not a style preference — it is the design's own acceptance criterion,
and it is measurable. The sanity test count should be **flat forever** while
the app grows. The `test-health` skill watches for exactly this and escalates
when the number moves.

### P3 — Prove by scanning, never by listing

Every hand-maintained list is a guard against **deletion only**. It is
structurally blind to the failure that actually happens: *someone adds a thing
and forgets to register it.*

`_BACKTEST_COMMANDS` and `_DATABASE_COMMANDS` catch a handler removed from
`binance_bot_module.py`. Neither can ever catch a handler that was never added
to it. The four strategy-name tests are the same shape, one BOT number each,
growing without bound and proving less every year.

The correct pattern is already in this tier — `test_view_model_thread_affinity_sanity.py`
pins a list *and* proves the list complete against a live `__subclasses__()`
scan. Rule: **a constant that drives `parametrize` in `tests/sanity` must
either be accompanied by a completeness proof, or be replaced by the scan
outright.** Prefer replacing it.

### P4 — Silence is the assertion

Sanity is the only place where every diagnostic channel of the real
application is open simultaneously: Python `logging`, Qt's message handler,
`warnings`, `stderr`, and the exception hook. That is the tier's structural
advantage, and it is currently thrown away entirely.

`BUG-028` shouted `Unable to assign [undefined] to double`.
`BUG-031` (P1) shouted `QBasicTimer::start: Timers cannot be started from
another thread`. Both reached users. Both were audible the whole time.
`Invoke-RunLogScan` listens on one channel out of five — and it is the one Qt
does not use.

So the tier's most valuable assertion is not something it checks, but something
it **refuses to tolerate**: during boot → construct → shutdown, every channel
must stay clean. Corollary: the allowlist of tolerated messages lives in code,
one line per message, each with a written reason. When that allowlist wants to
grow, the tier is telling you something true, and the answer is a bug report,
not another entry.

### P5 — The lifecycle includes dying

Boot → construct → **shut down**. The tier currently stops after the second
step; `app.stop()` sits in fixture teardown carrying no assertion at all.

Three shutdown bugs — `BUG-007`, `BUG-023`, `BUG-041`, two of them P1 — all
found by a human closing the window and watching a process refuse to exit.
Worse than uncovered: because the call is in teardown, a hang shows up as a
**hung test run**, not a failing test, so it degrades the tier's credibility
instead of reporting the defect.

An application that cannot exit has not passed a composition check. Shutdown is
half the lifecycle and belongs inside the contract, with a time budget and a
live-thread assertion.

### P6 — Cheap is a correctness property, not an optimisation

The repository has already run this experiment and written down the result.
`tests/integration/presentation/ui/` became slow and flaky, so it was
`--ignore`d — and 36 user-journey tests have proven nothing at any price ever
since. A tier that is expensive gets switched off, and a tier that is switched
off is worth exactly zero regardless of how well it was written.

Sanity today boots the real app roughly **24 times** to produce 38 assertions,
which is why it must run sequentially in its own job.

Budget for the rebuilt tier: **one boot, under ten seconds, cheap enough that
nobody is ever tempted to skip it.** The session-scoped fixture is not a
nicety — it is what keeps the tier alive long enough to be useful.

### P7 — Sanity must not know a single business fact

It may not assert that `ema_crossover` exists. That is feature knowledge and it
belongs to Unit or Integration. The moment Sanity learns a strategy's name, it
begins rotting per-feature — which is precisely why four separate tests, one
per BOT number, now assert four hard-coded strings.

The scanning form — *"every `IStrategy` implementation on disk is registered in
`StrategyRegistry`"* — proves strictly more, in one test, forever, with zero
maintenance, and keeps working for strategies nobody has written yet.

The test: **if an assertion would need editing when a feature changes, it does
not belong in Sanity.**

### P8 — A contract nobody executes does not exist

`code-rule.md` mandated `quick_widget.errors() == []`. Zero of 38 tests ever
did it. The clause was, in every sense that matters, not a rule — it was a
sentence in a file.

So every clause of the new contract ships **with its own enforcement**:
`.claude/skills/test-health/contract.json` restates each mandatory clause as
something greppable, and the `test-health` audit reports any clause with zero
enforcement in the tier it governs. Rule and enforcement change in the same
commit, or neither changes.

This is the principle that makes the other seven durable. Without it, this
document becomes the next `code-rule.md` §4.

---

## 4. What the tier becomes

From **9 files / 19 test functions / 38 cases / ~24 boots** to roughly
**2 files / 9 tests / 1 boot** — proving strictly more.

**`tests/sanity/conftest.py`** — the entire fixture surface, once:

- `booted_app` — session-scoped, loading exactly what `app_bootstrapper.main()`
  loads (`app_config.json` + `user_config.json`, `writable=True`), patching the
  network boundary identically for every test.
- `diagnostic_guard` — autouse, installs `qInstallMessageHandler`, a logging
  handler, a `warnings` catcher and an excepthook; fails the test on any
  problem-level record from any of them (P4).
- `qapp` — overrides the root fixture so a missing PySide6 is a **failure**,
  not a skip. A composition-health tier must go red on a broken environment.

**`tests/sanity/test_composition_root.py`** — nine tests, none feature-aware:

| # | Test | Principle | Replaces / closes |
| --: | :--- | :--- | :--- |
| 1 | Every binding the container registers resolves | P3 | both hand-written allowlists |
| 2 | Every `*Command`/`*Query` under `src/application/use_cases/` is registered | P3 | catches *add-without-register*, which no current test can |
| 3 | Every route registered in `MainWindow._setup_router()` constructs its real View + Presenter | P2, P3 | 2/4 screens → 4/4, and covers screens not yet written (`BUG-019` class) |
| 4 | Every strategy implementation on disk is registered | P7 | 4 name-pinned tests, permanently |
| 5 | Every indicator script on disk is registered | P7 | 1 name-pinned test, permanently |
| 6 | Boot + construct emit nothing on any diagnostic channel | P4 | `BUG-028`, `BUG-031` class — currently uncovered anywhere |
| 7 | The app shuts down within budget, leaving no live non-daemon thread | P5 | `BUG-007`/`023`/`041` class — currently uncovered anywhere |
| 8 | Every `BaseQmlViewModel` mutator is thread-protected | — | kept **as-is**; already scans, already has a drift guard |
| 9 | `main_window.py` has no top-level bootstrapper import | — | kept as-is; cheap, catches what pytest structurally cannot |

Tests 1–7 are written so that **no future feature can require a tenth test.**
That property, not the count, is what is being bought.

> **One open verification.** Test 1 assumes `StdLibContainer` can enumerate its
> own registrations. That could not be checked while writing this — the engine
> is not installed in the authoring environment. If the container exposes no
> registry, drop test 1 and rely on test 2, which scans the source instead and
> needs no container introspection at all.

---

## 5. What gets deleted

A rebuild that only adds is a patch wearing a rebuild's clothes. These come out
in the same change:

- `tests/integration/test_ui_sanity.py` — a `print()` and no assertion.
- Both `parametrize` allowlists, and the 5 name-pinned registry tests.
- 6 copies of the boot fixture, including the one that loads a different config
  and is the only test in the tier that does not patch the network.
- The `quick_widget.errors() == []` clause in `code-rule.md` §4, and the
  now-vacuous `errors()` / `findChildren(QQuickWidget)` assertions in
  `test_preview_fixtures_exist.py`.
- The 22 unloaded `.qml` files, the 2 test files still guarding them, and the
  session-autouse `_configure_app_qml` fixture that configures a QML stack
  production no longer initialises.

Everything in that list currently reports green while proving nothing. Leaving
it in place is not neutral — it is the exact material the next audit will have
to re-discover.

---

## 6. Migration order — no big bang

Each step is independently revertible and leaves the tier green.

1. **`conftest.py` first.** Pure consolidation, no behavioural change, no new
   assertion. Buys the single boot (P6) and removes the drift surface, which
   makes every later step smaller.
2. **Rewrite `code-rule.md` §4 and seed `contract.json`** (P1, P8). Rule before
   code — otherwise the next feature ships against the dead contract, and the
   audit grades against a rule nobody holds.
3. **Add the scanning tests alongside the allowlist tests.** Both run. Confirm
   each new test fails for the right reason when a registration is deliberately
   removed, per `bug-fix-rule.md`. Only then delete the allowlist version.
4. **Add `diagnostic_guard` last** (P4), because it is the one step expected to
   turn the tier red. Every message it surfaces is triaged as either a real
   defect — which then follows `bug-fix-rule.md` in full — or an explicitly
   justified allowlist entry with a written reason. **Do not start this step
   while the tier is already red for another reason.**
5. **Delete** everything in §5, in its own commit, so the diff is legible.

---

## 7. How we will know it worked

Not by test count, and not by coverage — §5 of the audit shows both saturated
here long ago.

| Signal | Now | Target |
| :--- | :---: | :---: |
| Sanity tests added when a screen is added | 1 or more | **0** (P2) |
| Screens constructed by the tier | 2 / 4 | all registered routes |
| Diagnostic channels observed | 1 of 5 (Python logging only, via CI grep) | 5 of 5 (P4) |
| Full app boots per tier run | ~24 | 1 (P6) |
| Assertions that reference a business name | 5 | 0 (P7) |
| Rule clauses with zero enforcement | 1 known, undetected for months | 0, and detected within 3 days (P8) |

The last row is the one that matters. Every other number can be gamed by
someone writing tests to satisfy a table. That row measures whether the project
can still tell the difference between a rule it holds and a rule it merely
wrote down — which is the failure this entire document exists to prevent
recurring.

---

*Written 2026-08-25 against commit `f27649e`. Static analysis only — the suite
could not be run in the authoring environment (see the audit report §1). The
open verification in §4 must be resolved before implementing test 1.*
