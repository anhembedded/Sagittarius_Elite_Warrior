# §10 — The test philosophy for the module architecture: what each layer proves, and how

- **Status:** 🟢 Approved 2026-09-13 (ADR D19), in answer to the user: *"xem lại triết lý test
  case, test layer, module hay như nào… các layer nào"* ("revisit the test philosophy — test cases,
  test layers, how modules are tested, which layers"). §9 says what happens to the *existing* tests
  during the migration; this section says what the suite **is** once the architecture exists.
- **Builds on, does not replace:** [`.agents/rules/testing-rule.md`](../../.agents/rules/testing-rule.md)
  (how to write a test; BVA; mutation-verify; no sleeps) and
  [`.agents/rules/ci-rule.md`](../../.agents/rules/ci-rule.md) (the four levels — Unit,
  Integration, Sanity, Desktop E2E — and the gate). Those stay the authority. This section adds the
  **map from architecture layer to proof**, because the old map ("test the presenter, test the
  handler") stops describing a system made of modules, contracts, cards and surfaces.

## 10.1 The three ideas, each with a name

| Idea | Origin | What it means for this app |
| :--- | :--- | :--- |
| **Test the hexagon through its ports** | Cockburn's Hexagonal Architecture; Freeman & Pryce, *Growing Object-Oriented Software, Guided by Tests* | A module's `application/` is tested by calling its **ports** with its **adapters replaced by fakes**; adapters are tested against the real thing (or the fake server); `domain/` is tested pure. Nobody tests a use case by mocking the classes next to it |
| **Verified fakes and contract suites** | Freeman & Pryce ("the same tests run against the fake and the real"); consumer-driven contracts (Pact), done in-process | Every public port ships **one fake** inside `contracts/testing/`, and **one contract suite** that both the fake and the real implementation must pass. Consumers test against the verified fake. This is the general cure for `BUG-026`/`BUG-027` (hand-written substitutes that drifted from the real port) |
| **A test proves one layer** | the test pyramid (Cohn) and Google's small/medium/large sizes, mapped onto this repository's four levels | Each layer of HLD §3.2 has exactly one kind of proof (table 10.2); a test that reaches two layers is either an integration test by design or a mistake |

Two supporting practices already in the rules stay as they are: **fitness functions** (the guards,
HLD §6.1) prove structure, and the **sanity tier** proves the real composition root boots in
silence with zero per-feature tests.

## 10.2 The proof map — one row per layer of the architecture

| Layer (HLD §3.2) | What must be proven | How | Tier | Doubles allowed |
| :--- | :--- | :--- | :--- | :--- |
| `domain/` | the rule is right at its boundaries | pure tests, Boundary Value Analysis, mutation-verify (`testing-rule.md` §2); property-based tests for pure arithmetic (sizing, rounding, PnL) — see 10.6 | unit | none — domain has no dependencies |
| `contracts/` (ports, DTOs, events, errors) | the contract means what it says, for every implementation | the **contract suite**: one test module per port, parametrised over `[fake, real]`; DTOs are frozen and constructible without Qt; each event's payload is asserted once | unit (fake) + integration (real, when the real needs I/O) | the port's own verified fake only |
| `application/` (use cases, services, port implementations) | the use case does the right thing through its ports, from any thread | drive the port or the handler with **verified fakes of other modules' ports** and in-memory adapters; one thread-safety test per port implementation that mutates state (the `threading.Barrier` pattern already used in `test_execute_order.py::TestConcurrentDispatch`) | unit | verified fakes of foreign ports; in-memory fakes of own adapters |
| `adapters/` | the real thing is spoken to correctly | persistence against a temporary SQLite file; exchange REST and websocket against `tests/sanity/fake_exchange` (the existing fake server) — never a mocked `requests` | integration | the fake server; a temp database |
| `ui/` — a **card** (View + Presenter) | the presenter reacts correctly and the view renders the state | presenter tests **without Qt** through the view model (the View/ViewModel/Presenter split exists for this — `Docs/Diagrams/ui_architecture.md`); one `qtbot` smoke test per view that constructs it, feeds a state and reads the widget; the card's `ActionOwnershipTracker` semantics per `async-ui-action-rule.md` | unit | verified fakes of ports; a spy dispatcher |
| `module.py` (`register` / `boot` / `contribute` / `subscribe`) | the module obeys the SDD's rules | the declaration guard (`register` never resolves; `contribute` calls no factory and imports no widget module; `dependencies` equal real imports) — written **once**, runs over every module | unit (architecture) | container spy, registry spy |
| a **surface** | the layout is what the UI map says | assert places, contributions and their order per surface against the registry; **no behaviour** — a surface has none | unit | the real registry, fake factories |
| cross-module **events** | each cross-module event is published with its documented payload and normalised by exactly one Feed (`architecture-rule.md` §6) | one test per row of HLD §2.5: publisher emits, the Feed receives, no second subscriber | unit | the Engine's `MemoryEventBus` (real) |
| a **journey across modules** | a tick becomes an order (SDD-04) and the lease refuses the second owner | the real modules wired by the real shell, exchange replaced by the fake server, one journey per row of HLD §2.3's pairs | integration | the fake server only |
| **structure** | the boundaries hold and shrink | the three guards of HLD §6.1, the UI-map guard, the retargeted existing guards, the allowlist ratchet | unit (architecture) | — |
| the **composition root** | the real app boots, in silence, and every registered thing is reachable | the sanity tier as it is today — zero new tests; its scans now iterate modules and surfaces instead of screen packages | sanity | the fake server at the network boundary, drawn at configuration |
| the **Engine** | the API the app depends on exists in the installed build | `engine_capabilities.py` checked at boot; the Engine's own suite lives in its own repository | sanity | — |
| **real behaviour** | orders fill, PnL moves, the user sees what the exchange sees | `tests/testnet/` (opt-in) and the user running Testnet after Phases 1 and 2 — the evidence tier `EPIC-024B` §6 established | testnet / human | none |

## 10.3 Contract suites and verified fakes — the mechanism, concretely

```
modules/market_data/contracts/
├── i_historical_klines.py            # the port (ABC)
└── testing/
    ├── fake_historical_klines.py     # FakeHistoricalKlines(IHistoricalKlines): in-memory, seeded by the test
    └── contract_historical_klines.py # class HistoricalKlinesContract: the suite, parametrised by a fixture `impl`
tests/unit/modules/market_data/contracts/test_historical_klines_contract.py      # runs the suite against the fake
tests/integration/modules/market_data/contracts/test_historical_klines_real.py   # runs the same suite against the real service + temp DB
tests/unit/modules/backtesting/…                                                  # consumers use FakeHistoricalKlines, never a Mock
```

Rules:

1. **A fake ships with the contract**, in the provider module, under `contracts/testing/`. It is
   public API: consumers import it. It is small, deterministic, in-memory, and has no Qt.
2. **The contract suite is written by the provider and extended by consumers.** A consumer that
   needs a guarantee the suite does not state adds a test to the suite — that is the
   consumer-driven half. A guarantee no consumer needs is not in the suite.
3. **Both implementations run the suite.** The fake runs it in unit; the real implementation runs
   it in integration. A fake that diverges from the real fails the same test the real passes, which
   is exactly the failure `BUG-026`/`BUG-027` had no way to produce.
4. **No `Mock(spec=IPort)` for a foreign port** in application or ui tests. A module may mock
   *its own* internals when a unit test needs it; it never mocks another module's port — it uses
   that module's verified fake. A guard greps for `Mock(spec=I` against foreign ports.
5. The sanity rule stays: sanity never substitutes a port at all; it substitutes the network at
   configuration.

## 10.4 Cards and surfaces — where the old "presenter tests" go

The old suite tested a screen's Presenter as one object with dozens of methods (2,008 lines for
Dev Board). In the new architecture a screen has no behaviour, and a card has little: it shows a
feed and dispatches actions. So:

- A **card's presenter test** is short and there is one per card. It uses the module's verified
  fakes for ports and a spy for the dispatcher, asserts the view model after each event and the
  dispatched command after each action, and asserts the `ActionOwnershipTracker` outcome for an
  in-flight action. No Qt.
- A **card's view test** is one `qtbot` smoke test: construct, apply a view-model state, read the
  widget. It proves the binding, not the behaviour.
- A **surface test** asserts the UI map row for that surface — places, contributors, order — and
  that a gated-off surface receives nothing. It never asserts a business fact.
- The **Qt-click journey tests** (today's `test_dev_board_*` under integration) survive as the only
  tests that press real buttons on a real surface with real cards and the fake server; there is
  one per user journey the epic promises to keep (manual order, cancel, enable/disable, arm/disarm).

## 10.5 The module's definition of done, as tests

A module is done when all of these exist and are green — this list is the review checklist:

- [ ] every public port has a fake under `contracts/testing/` and a contract suite; the fake and
      the real both pass it;
- [ ] every cross-module event has its publisher/Feed test;
- [ ] every port implementation that mutates state has a concurrency test;
- [ ] every card has one presenter test module and one view smoke test;
- [ ] the module's row in the UI-map guard is non-empty and matches HLD §4.6.4;
- [ ] the declaration guard passes for the module with no allowlist entry;
- [ ] the module's tests live under `tests/{unit,integration}/modules/<id>/` mirroring its layers;
- [ ] the sanity tier still has zero per-module tests and is green.

## 10.6 Candidates that follow "apply before you invent" — proposed, not adopted

| Candidate | What it would replace | Verdict asked of the user |
| :--- | :--- | :--- |
| **Hypothesis** (property-based testing, MIT) for `domain/` arithmetic: sizing, lot rounding, PnL, fee, margin | hand-enumerated boundary cases that miss the one that matters | 🟢 **adopted for domain math only** (user, 2026-09-13; the dependency lands with the Phase 0 code PR); it is a test dependency, not a mechanism the design builds, so ADR §5 ("no library substitutes a planned mechanism") does not apply. The existing BVA rule stays; Hypothesis generates the values BVA names |
| **pytest-benchmark** for the chart and backtest hot paths | ad-hoc timing scripts under `scripts/benchmarking/` | ❌ not now; `Bolt`'s scripts exist and the epic is not about performance |
| **approvaltests** for the golden master | a hand-rolled file compare | ❌ not needed; a stored trade log and `filecmp` is enough |

## 10.7 Anti-patterns this section forbids (each has a precedent in this repository's bug board)

- Mocking a foreign module's port with `Mock` — use its verified fake (`BUG-026`, `BUG-027`).
- Asserting through log text instead of through the port or the view model.
- A test that imports a module's `application/` or `adapters/` from another module's test —
  that is a boundary violation and the guard catches it.
- A `sleep` in an async test (`testing-rule.md` §2).
- A surface test that asserts a business fact, or a sanity test that names a feature.
- A card presenter test that constructs the real widget tree "to be safe" — the view smoke test
  exists for that; the presenter test stays Qt-free so it runs in milliseconds.
