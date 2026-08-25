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

| # | Failure mode | From | Witnessed by | IN | OUT |
| --: | :--- | :--- | :--- | :---: | :---: |
| 1 | Missing node — something needed was never registered | graph | — | ✅ | ❌ |
| 2 | **Orphan node** — registered, nothing depends on it | graph | **none yet** | ✅ | ❌ |
| 3 | Broken edge — node registered, its dependency is not | graph | — | ✅ | ❌ |
| 4 | Wrong node — right key, wrong type or interface | graph | BUG-020, BUG-026, BUG-027 | ✅ | ❌ |
| 5 | In source, not in graph — added and never registered | graph ↔ source | BUG-039 | ✅ | ❌ |
| 6 | **In graph, not in source** — registration points at deleted code | graph ↔ source | **none yet** | ✅ | ❌ |
| 7 | Cannot enter — boot fails | lifecycle | BUG-043 | 🟡 | ✅ |
| 8 | **Enters degraded** — boot "succeeds" while emitting problems | lifecycle | BUG-028, BUG-031 | 🟡 | ✅ |
| 9 | **Cannot exit** — the process does not die | lifecycle | BUG-007, BUG-023, BUG-041 | ❌ | ✅ |
| 10 | Exits dirty — stop() returns, threads/handles survive | lifecycle | BUG-041 | 🟡 | ✅ |
| 11 | Entry point registered but cannot be constructed | entry points | BUG-019, BUG-035 | ✅ | 🟡 |
| 12 | **Entry point exists but nothing registers it** | entry points | **none yet** | ✅ | ❌ |

`IN` / `OUT` are the two execution layers defined in D2. **Mode 9 is the one
that forces the split**: inside pytest, `teardown()` returning is not the same
as the process dying, because pytest's own process keeps living —
`threading.enumerate()` is a proxy, not the fact. BUG-007's symptom was
literally *"the UI closed but the Python process kept running"*. Only a
subprocess exit code proves that.

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

### D2 — Two execution layers; neither may rebuild the app 🔵 Proposed — **revised 2026-08-25 after review**

> **Superseded:** the first version of D2 read *"Sanity gets no entry point of
> its own"* and concluded that Sanity should call `build()` from pytest. That
> answered the wrong question. It conflated **(A)** *may Sanity use different
> wiring?* — no, correctly — with **(B)** *must Sanity ever run as a real
> process, launched the way production launches?* Answering (A) and stopping
> silently answered (B) with "no", which is wrong.

**Decision.** Sanity runs at **two layers**, which cover disjoint failure modes:

| | **IN-process** | **OUT-of-process** |
| :--- | :--- | :--- |
| Invocation | pytest imports and calls `build()` / `teardown()` | `python -m ...app_bootstrapper --self-check`, spawned by pytest via `subprocess.run` |
| Reality | fake `__main__`, pytest's `sys.argv`, pytest's process lifetime | real `__main__`, real `sys.argv`, real `QApplication`, real `app.exec()`, real `sys.exit()` |
| Can assert | objects — view attached to the stack, properties readable, routes construct, registry scans | the process boundary — exit code, exit within budget, clean stdout/stderr |
| Covers | modes 1–6, 11, 12 | modes 7–10 |

**`--self-check` is not a second composition root.** It runs the real `main()`
and changes exactly one thing: the loop's **termination condition** — "quit when
the user closes the window" becomes "quit after the first idle turn". No branch
in the wiring, no injected double, no step skipped. The diff is a handful of
lines inside `main()`, downstream of everything that composes the app.

It is also a real product capability, not scaffolding: it lets a human verify an
installation actually starts — exactly what BUG-043 (`run-ui.ps1` could not
import the local engine) needed and did not have.

**The entry-point split from the original D2 still stands**, because the
IN-process layer needs it:

```python
def build() -> AppRuntime:            # everything up to, and not including, app.exec()
def teardown(rt: AppRuntime) -> None: # window.shutdown, watchdog.stop, sig_timer.stop, app.stop
def main() -> None:                   # build() -> app.exec() -> teardown() -> sys.exit()
```

**Evidence — the repo has already paid for both halves of this.** ✅ Established

*For the OUT layer being necessary:* three tests already spawn the app as a
subprocess and assert on its exit code —
`tests/integration/presentation/test_shutdown_sync_process.py`,
`test_shutdown_database_sync_process.py`, `test_shutdown_database_scan_process.py`
(`subprocess.run([sys.executable, "-m", ...])`, `returncode == 0`, 30s timeout).
Nobody called it Sanity, but it is exactly "launch the real thing and check it".

*For "must not rebuild the app":* those three probes
(`scripts/shutdown_*_probe.py`, 366 lines) each call `create_app()`, build their
own `QApplication` and `MainWindow`, and inject their own hand-written doubles —
bypassing `app_bootstrapper.main()` entirely. That duplication is the direct
cause of **BUG-026** (`_BlockingExchangeClient` missing
`stream_historical_klines`) and **BUG-027** (`_SeededMarketDataRepository`
missing 7 of 12 port methods): the doubles fell behind the real interfaces and
nothing noticed.

So the rule is not "no subprocess" — it is **launch production's own entry
point, never a bespoke script that re-composes the app.**

**Not "pytest vs command line".** pytest remains the runner for both layers;
the existing shutdown tests already demonstrate pytest driving a real process.
The distinction that matters is **import vs launch**, and the defect was making
import the only mode.

**Rejected alternative.** A `--sanity` flag that builds a *different* app
(skips theme, injects fakes, swaps wiring). Rejected for the original D2's
reason, now with receipts: that is what the three probe scripts do, and it cost
two bugs.

### D2b — The OUT layer is a control channel, not just a boot-and-exit check 🔵 Proposed — **added 2026-08-25 after review**

> **Supersedes the `--self-check` scope in D2.** D2's OUT layer only booted the
> app, idled and exited. Review position: Sanity should *run the app and then
> test it*, driven by a command that starts the app for real and exposes an API
> to publish events or trigger actions. Boot-and-exit is a strict subset of
> that, so `--self-check` becomes the degenerate case of one control session
> that sends `quit` immediately.

**Decision.** The app gains an opt-in control channel. A real process, started
normally, plus a transport that exposes the app's **existing** internal APIs to
a caller outside the process.

**No new API is designed.** ✅ Established — the surface already exists:

| Capability | Already in the repo |
| :--- | :--- |
| Publish an event | `IEventBus.emit()` — `test_sanity_ui_e2e.py` already drives the app this way, in-process |
| Trigger an action | `IDispatcher.dispatch()` — every Command and Query already routes through it |
| A command loop inside the running app | `InteractiveShell` (`IHostedService`, routed from `cli_commands.json`, handlers for `sync` / `stream`) |

What is missing is only a **transport**: a machine-readable channel reaching
those two calls from outside the process.

**Shape.**

```
python -m ...app_bootstrapper --control=stdio
```

The app starts completely normally — real `main()`, real window, real wiring —
plus one hosted service reading newline-delimited JSON:

```json
{"op":"publish",  "event":"MarketTickEvent", "payload":{...}}
{"op":"dispatch", "command":"SyncMarketDataCommand", "payload":{...}}
{"op":"navigate", "route":"backtest"}
{"op":"wait",     "until":{"fsm":"DONE"}, "timeout_ms":30000}
{"op":"quit"}
```

Responses **and every diagnostic** — Qt messages, log records, warnings — stream
back as JSON lines. The harness asserts on that stream plus the exit code.

**Why this is materially better than mocking, not merely different.** Today's
tier patches `AsyncClient` and `BinanceSocketManager`; the review's objection
was precisely that Sanity "creates mock test cases" instead of running the app.
With a control channel the boundary is not faked at all — the app runs offline
and is **fed through its own event bus**. No test double exists to fall behind
its port. That eliminates the BUG-026 / BUG-027 class structurally rather than
by discipline.

**Three constraints that decide whether this works.**

1. **Thread affinity.** Every op must reach the Qt main thread via
   `QMetaObject.invokeMethod(..., QueuedConnection)`. A control channel that
   touches the UI from its own thread manufactures exactly BUG-001 and BUG-031
   — the defect class this tier exists to catch.
2. **Transport only, never a second path.** It calls the same `emit` /
   `dispatch` production calls, and does nothing else. Violating this returns
   the project to the probe-script disease (see D2's evidence).
3. **Security — non-negotiable.** This is a trading application holding Binance
   API credentials, and the channel can dispatch *any* command. It must be off
   by default, enabled only by an explicit flag, bound to stdio or loopback
   only, and must never open a network port by default. This is an approval
   condition, not an implementation detail.

**Blocking prerequisite: the app has no offline mode.** ✅ Established —
`src/config/*.json` contains no flag that disables Binance access. Without one,
a "real" run still reaches the network and the mocks come straight back. An
offline mode is a genuine product feature (developing without keys), and it
must land before this decision can be implemented.

**Scope note.** This transport serves Integration and Desktop E2E as much as
Sanity — the three shutdown probes collapse into it, and driving a real screen
becomes a control session. It should be scoped as a **test automation surface**
for the whole pyramid, not as a Sanity feature.

**Taxonomy conflict to resolve.** Under `ci-rule.md` §6, publishing events and
triggering actions places a test in **Integration**, not Sanity. Adopting this
decision therefore requires amending the tier definitions explicitly. Leaving
the boundary informal is what produced the original problem, so it must not be
left implicit.

**Cost.** Weeks, not days: transport and protocol, JSON payload to typed
event/command construction (Pydantic is already in the stack via
`PydanticValidationMiddleware`), wait/observe primitives, thread discipline,
security gating, and the offline mode. This competes for time with re-verifying
BOT-038, which costs one command and may unlock 36 journey tests immediately.

### D3 — Execution level L2, on both layers 🔵 Proposed

| Level | Runs | Realism | Cost |
| :--- | :--- | :---: | :--- |
| L0 | `create_app()` + `boot()` | low | cheap |
| L1 | `build()` — full production bootstrap, no `exec()` | high | cheap |
| **L2** | **L1 + a bounded run of the real event loop, offscreen** | **highest headless can reach** | **cheap** |
| L3 | real display, real input, real pixels | total | expensive, flaky |

**Decision.** Sanity targets **L2 on the IN layer**, and the OUT layer runs
the real `main()` end to end. It is at **L0, IN only**, today. L3 stays
Desktop E2E.

The OUT layer needs no level choice: it *is* production's own startup, with
one changed stop condition. Its realism is not a dial.

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
| Q9 | What is the `--self-check` termination condition — first idle turn, N loop turns, or a fixed timeout? | D2 OUT layer |
| Q10 | Do the three `scripts/shutdown_*_probe.py` scripts fold into `--self-check`, or stay as scenario probes? Their "sync in flight" setup genuinely needs a blocking double, which `--self-check` must not carry | D2, scope |
| Q11 | If they stay: one shared, type-checked set of test doubles instead of one per script? BUG-026 and BUG-027 were both per-script doubles drifting from their ports | D2 |
| Q12 | Does the OUT layer run on every CI invocation, or only in the full gate? It costs a real process launch per run | C4 |
| Q13 | Offline mode: what is the config key, and what exactly does it disable — the websocket service, the REST client, or both? | D2b, blocking |
| Q14 | Control transport: stdio, loopback socket, or both? Stdio is simplest and safest; a socket allows attaching to an already-running app | D2b |
| Q15 | How are JSON payloads turned into real typed events/commands? Reuse the Pydantic layer already registered as `PydanticValidationMiddleware`, or a separate registry? | D2b |
| Q16 | What can `wait.until` observe — FSM state, a named signal, a log line, all three? This decides whether the harness is deterministic or sleep-based | D2b |
| Q17 | Does adopting D2b mean amending `ci-rule.md` §6's tier definitions, and if so, does "Sanity" keep its name for an event-driven tier? | D2b, taxonomy |
| Q18 | Sequencing: does D2b come before or after re-verifying BOT-038? One is weeks, the other is one command | epic scope |

Q2, Q3, Q4 and Q6 cannot be answered from the authoring environment — it has
neither PySide6 nor `sagittarius_engine` installed, and this project's CI is
Windows/PowerShell-only. They need one session on the real machine.

---

## 8. Consequences if accepted

**Gained.** Coverage for modes 7, 8, 9, 10 and 12 — none of which any tier
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
- The offline mode itself (Q13) — a product feature this ADR depends on but
  does not design.
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
