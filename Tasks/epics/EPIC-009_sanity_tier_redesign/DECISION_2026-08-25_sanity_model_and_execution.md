# ADR — Sanity Tier: Model, Execution Level and Assertion Boundary

**Belongs to:** [`EPIC-009`](README.md)
**Date:** 2026-08-25
**Status:** 🔵 **Proposed — under discussion. Nothing approved, nothing implemented.**

> [!IMPORTANT]
> **Read the status column, not the prose.** Every claim in this document is
> tagged. The failure this ADR exists to prevent is the one that produced the
> problem in the first place: a written rule that reads like a decision but was
> never ratified, never enforced, and outlived the thing it described.
>
> | Tag | Meaning |
> | :--- | :--- |
> | ✅ **Established** | Verified against the tree; cite `file:line`; not a matter of opinion |
> | 🔵 **Proposed** | Converged on in discussion; **not** approved; may change |
> | 🟠 **Draft** | Written down to be argued with; expected to change |
> | ❓ **Open** | Blocks implementation until answered |

---

## 1. Context

Two reports established the problem; this ADR does not restate them:

- [`sanity_tier_audit_and_remediation.md`](../../reports/sanity_tier_audit_and_remediation.md)
  — what is broken, with evidence.
- [`sanity_redesign_philosophy.md`](../../reports/sanity_redesign_philosophy.md)
  — the first attempt at a redesign, **superseded in method** by §2 below.

The three findings that make this an epic rather than a fix: ✅ **Established**

1. The Sanity contract in `code-rule.md` §4 mandates `quick_widget.errors() == []`,
   which no test performs and none now can — EPIC-006 removed QML from the app
   entirely. The tier has been guarding an architecture the app abandoned.
2. Of 43 filed bugs, only 3 fall inside Sanity's remit; the tier missed all 3.
   A further 19 fall in classes Sanity is contractually forbidden to touch.
3. Today's tier boots `create_app()` directly and therefore **skips the entire
   production UI bootstrap** — `_apply_font`, `_apply_theme`, `get_theme_bridge`,
   `_install_exception_handler`, `setup_qt_signal_handling`, `UIWatchdog`, and
   `QTimer.singleShot(0, _log_ui_ready)` (`app_bootstrapper.py:62-140`). It
   claims to boot "the exact same factory production uses"; that is half true.

---

## 2. Method rejected — and why it is recorded here

**The first redesign attempt derived eight "principles" backwards from the 43
bug records.** Each principle mapped to one defect class that had already
happened. On review it was rejected as *"rules and best practice from mistakes,
not a sanity design"*, and that rejection was correct.

The generic failure: **a design derived from history can only remember; it
cannot predict.** Deriving from structure produces coverage for failures nobody
has hit yet. Validating against history is the right use of the bug record;
generating from it is not.

Concrete proof that the distinction is not academic — deriving from structure
(§4) produced three failure modes that the eight principles missed entirely,
because no bug had ever exercised them: **modes 2, 6 and 12**.

The eight principles are not discarded, but they were four different kinds of
statement in one list, which is why they read as a best-practice checklist:

| Original | Actually is |
| :--- | :--- |
| P1 define by question, P2 must not grow with features | Design principle — retained, §3 |
| P3 scan not list, P6 cheap is correctness, P7 no business facts | Implementation constraint — §6 |
| P4 silence is the assertion, P5 lifecycle includes dying | **Failure modes 8, 9, 10** — mislabelled as principles |
| P8 a contract nobody executes does not exist | Governance — outside this ADR |

---

## 3. D1 — The model 🔵 Proposed

Sanity's subject is not "the app". It is what `create_app()` plus the UI
bootstrap actually produce:

```
Composition root  =  Graph(nodes, edges)  +  Lifecycle(enter, exit)  +  EntryPoints
```

From which the tier's question follows, with no framework named:

> **Can the thing production assembles come into existence at all — and does it
> assemble in silence?**

Not *is it correct* (Unit). Not *does the user get what they wanted*
(Integration). Not *what is on screen* (Desktop E2E).

**Why this and not a prose definition:** a model generates a finite, arguable
failure list (§4). A prose definition generates opinions. The current contract
is a prose definition, and it is how the tier came to guard nothing.

---

## 4. Draft failure-mode catalogue 🟠 Draft — **not ratified**

Derived from §3 alone. No bug consulted while writing this table; the bug
column was filled in afterwards, as validation.

| # | Failure mode | From | Witnessed by |
| --: | :--- | :--- | :--- |
| 1 | Missing node — something needed was never registered | graph | — |
| 2 | **Orphan node** — registered, nothing depends on it | graph | **none yet** |
| 3 | Broken edge — node registered, its dependency is not | graph | — |
| 4 | Wrong node — right key, wrong type or interface | graph | BUG-020, BUG-026, BUG-027 |
| 5 | In source, not in graph — added and never registered | graph ↔ source | BUG-039 |
| 6 | **In graph, not in source** — registration points at deleted code | graph ↔ source | **none yet** |
| 7 | Cannot enter — boot fails | lifecycle | — |
| 8 | **Enters degraded** — boot "succeeds" while emitting problems | lifecycle | BUG-028, BUG-031 |
| 9 | Cannot exit — shutdown hangs | lifecycle | BUG-007, BUG-023, BUG-041 |
| 10 | Exits dirty — stop() returns, threads/handles survive | lifecycle | BUG-041 |
| 11 | Entry point registered but cannot be constructed | entry points | BUG-019, BUG-035 |
| 12 | **Entry point exists but nothing registers it** | entry points | **none yet** |

**Modes 2, 6 and 12 have no bug behind them.** That is not a reason to drop
them — it is the entire argument for §2's method. Mode 12 in particular is
cheap to cover and currently invisible: a screen package under
`src/presentation/ui/screens/` that was never added to
`MainWindow._setup_router()` is unreachable to every existing test, and the
scanning technique needed already exists in
`tests/unit/presentation/ui/test_preview_fixtures_exist.py`.

❓ **This table is the first thing to ratify.** Every later decision is derived
from it, so an error here propagates to everything.

---

## 5. Decisions proposed

### D2 — Sanity gets **no** entry point of its own 🔵 Proposed

**Decision.** Do not add a CLI, headless or "test mode" path for Sanity. Split
the existing production entry point at the event loop instead:

```python
def build() -> AppRuntime:            # everything up to, and not including, app.exec()
def teardown(rt: AppRuntime) -> None: # window.shutdown, watchdog.stop, sig_timer.stop, app.stop
def main() -> None:                   # build() -> app.exec() -> teardown() -> sys.exit()
```

Sanity calls `build()` and `teardown()` — **the same two functions production
calls**, with no duplicated logic and no `if testing:` branch.

**Rationale.** A path built for Sanity is a path only Sanity proves. It would
be a third composition root alongside `app_bootstrapper.main()` and
`main.main()`, and it would drift — the same disease as the six copied fixtures
(audit F7), one level up and harder to see. The repo already carries a mild
form of this: today's tier boots `create_app()` directly and proves a path
production never runs (§1.3).

**Bonus, not incidental.** The split hands Sanity production's *real* teardown,
which no tier currently touches — modes 9 and 10, three bugs, two of them P1.

**Rejected alternative.** *"Add a `--sanity` headless mode."* Rejected: it makes
the realism gap larger, not smaller, and it is exactly the kind of convenience
that reads as pragmatic and quietly invalidates the tier.

---

### D3 — Execution level L2 🔵 Proposed

| Level | Runs | Realism | Cost |
| :--- | :--- | :---: | :--- |
| L0 | `create_app()` + `boot()` | low | cheap |
| L1 | `build()` — full production bootstrap, no `exec()` | high | cheap |
| **L2** | **L1 + a bounded run of the real event loop, offscreen** | **highest headless can reach** | **cheap** |
| L3 | real display, real input, real pixels | total | expensive, flaky |

**Decision.** Sanity targets **L2**. It is at **L0** today. L3 stays Desktop E2E.

**Why the event loop is mandatory, i.e. why not stop at L1.** An entire defect
class only exists once the loop turns: `QTimer`, `QueuedConnection`,
`deleteLater()`, and the bootstrap's own `QTimer.singleShot(0, _log_ui_ready)`.
BUG-031 is precisely this class. Shape:

```
QTimer.singleShot(0, ...)          # let production's own _log_ui_ready actually run
QTimer.singleShot(BUDGET_MS, app.quit)
app.exec()                          # the real loop, time-boxed, self-terminating
```

This is Qt's real loop, not a `processEvents()` imitation, so it catches what
`processEvents()` does not.

**The L2/L3 boundary is the Sanity/E2E boundary:** L2 has no user input and no
pixels; L3 has both. That sentence is the whole tier split, and it is
framework-independent.

---

### D4 — Substitution boundary: the network, and nothing else 🔵 Proposed

| Permitted | Forbidden |
| :--- | :--- |
| Network boundary — `AsyncClient`, `BinanceSocketManager` (current practice, correct) | Anything inside the app |
| Database **path**, redirected **via config override** | Patching a repository, session or handler |
| `QT_QPA_PLATFORM=offscreen` | Skipping `_apply_theme` / `_apply_font` "to go faster" |

**The load-bearing distinction:** changing *configuration* leaves the
composition root intact; changing a *code path* means the tier is testing a
different application. Redirecting the DB path is configuration. Mocking
`IMarketDataRepository` is a code path — and the moment it happens, Sanity is
no longer answering §3's question.

Every substitution beyond the network boundary requires a written reason in
code. A growing substitution list is the tier losing value, not becoming more
stable.

> ⚠️ **Known trap.** `app_bootstrapper.py:104` sets
> `QT_LOGGING_RULES=qt.qpa.fonts.warning=false;qt.qpa.window=false` — production
> suppresses some Qt warnings. Calling `build()` inherits that suppression and
> partially blinds mode 8 at source. Proposal: Sanity re-enables full output and
> records those two rules as two explicit allowlist lines with reasons, so they
> become visible rather than absent.

---

### D5 — UI assertions are structural only 🔵 Proposed

**Forbidden:** asserting content — labels, column counts, heights, `symbol ==
"BTCUSDT"`. That is feature knowledge; it rots per feature and it is what the
current tier does (`test_backtest_screen_ui_sanity.py`).

**Permitted:** properties true of *every* screen, derived from §4:

| # | Assertion | Mode |
| --: | :--- | :---: |
| 1 | `View()` + `Presenter(view, container)` does not raise | 11 |
| 2 | Every route in the router registry constructs | 11 |
| 3 | Every screen package on disk has a route (**reverse scan**) | **12** |
| 4 | The constructed view is actually attached to the router's `QStackedWidget` | 11 |
| 5 | Every `@Property` on the ViewModel is readable without raising (via metaobject) | 8 |
| 6 | Survives N event-loop turns with no diagnostic on any channel | **8** |
| 7 | `deleteLater()` + pump leaves no pending-timer / orphan-child warning | **10** |

Assertion 5 is the strong form of today's `presenter._view_model is not None`:
generic, requires no knowledge of which properties exist, and catches the
"getter explodes before data arrives" class that nothing currently guards.

**Deliberately absent: any assertion about what is displayed.** That is
Integration's contract.

---

## 6. Implementation constraints (demoted from §2's principle list) 🔵 Proposed

Not decisions about *what* Sanity is — conditions any implementation must meet:

- **C1 — Scan, never list.** A constant driving `parametrize` must be
  accompanied by a proof of completeness against a live scan, or replaced by
  the scan. Existing correct example:
  `tests/sanity/test_view_model_thread_affinity_sanity.py:62`.
- **C2 — Adding a feature adds zero Sanity tests.** If a new screen requires a
  new Sanity test, the existing tests were written wrong. This is the design's
  own acceptance criterion and is machine-checkable — the `test-health` skill
  already escalates on `tests/sanity` growth.
- **C3 — No business facts.** If an assertion would need editing when a feature
  changes, it does not belong in this tier.
- **C4 — Cheap is correctness.** One boot, one bounded loop, target under 10s
  total. Exceeding the budget is treated as a red test. BOT-038 is the recorded
  cost of ignoring this: an expensive tier gets `--ignore`d and then proves
  nothing at any price.

---

## 7. Open questions — blocking ❓

| # | Question | Blocks |
| --: | :--- | :--- |
| Q1 | Ratify, amend or reject the 12-mode catalogue (§4) | everything |
| Q2 | Can `StdLibContainer` enumerate its own registrations? | modes 2 and 6; if not, only the source→graph direction is testable |
| Q3 | Does `MainWindow` construct under `offscreen` *with* the full bootstrap? Unverified — today's tier constructs it *without* theme/font/theme-bridge | D3 |
| Q4 | Can `@Property` be enumerated via metaobject on `BaseQmlViewModel`? | D5 assertion 5 |
| Q5 | Inherit or override production's `QT_LOGGING_RULES` suppression? | D4, mode 8 |
| Q6 | Does config expose the DB path, so it can be redirected without a code path change? | D4 |
| Q7 | What is `BUDGET_MS`, and what happens on overrun? | D3, C4 |
| Q8 | Is re-verifying BOT-038 inside this epic or a prerequisite to it? | epic scope |

Q2, Q3, Q4 and Q6 cannot be answered from the authoring environment — it has
neither PySide6 nor `sagittarius_engine` installed, and this project's CI is
Windows/PowerShell-only. They need one session on the real machine.

---

## 8. Consequences if accepted

**Gained.** Coverage for modes 8, 9, 10 and 12 — none of which any tier
currently holds, and which account for 6 filed bugs, 3 of them P1. Tier cost
drops from ~24 app boots to 1. Test count stops tracking feature count.

**Paid.** `app_bootstrapper.main()` must be refactored — production code
changed to serve testability, which needs its own verification. Adding the
diagnostic guard is expected to turn the tier **red**, and every message it
surfaces must be triaged per `bug-fix-rule.md` rather than allowlisted for
convenience. `code-rule.md` §4 and `ci-rule.md` §6 both have to be rewritten
before any code lands.

**Unchanged.** `offscreen` remains a real gap from production rendering. That
gap is accepted and is precisely why Desktop E2E exists. What is not
acceptable is pretending it is not there.

---

## 9. Explicitly out of scope

- The Integration tier and BOT-038. Related, separately decided.
- Deleting the 22 dead `.qml` files — already recorded as EPIC-006 debt in
  [its README](../EPIC-006_drop_qml/README.md); this ADR does not claim it.
- The `test-health` skill, already shipped. It enforces this ADR once ratified;
  it does not depend on it.
- Any implementation. Nothing is built until §7 is closed.

---

## 10. References

- [`sanity_tier_audit_and_remediation.md`](../../reports/sanity_tier_audit_and_remediation.md)
- [`sanity_redesign_philosophy.md`](../../reports/sanity_redesign_philosophy.md) — superseded in method (§2)
- [`EPIC-006` ADR](../EPIC-006_drop_qml/DECISION_2026-08-24_widget_architecture.md) — the migration whose fallout §1.1 describes
- `.agents/rules/ci-rule.md` §6, `.agents/rules/code-rule.md` §4 — the contracts this ADR replaces
- `.claude/skills/test-health/` — the enforcement mechanism
