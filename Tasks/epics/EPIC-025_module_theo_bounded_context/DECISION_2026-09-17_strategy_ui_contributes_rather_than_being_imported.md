# ADR — `strategy` contributes its UI to other surfaces; they stop importing its concrete classes

**Epic:** [EPIC-025](README.md) · **Date:** 2026-09-17 · **Status:** 🟢 Approved (the user, quoted below)

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |

## 1. Context

PR 4.4 (`EPIC-025E` §3.2) starts by moving `screens/trading` into `modules/trading/ui/` — the
smallest of the four screens the pull request folds together. Running the real boundary guard
(`tests/unit/architecture/test_module_boundaries.py`) against the moved tree, before writing
anything else, found six import lines that are legal today (`screens/trading` is legacy, and a
legacy file may import any module's code) and become **illegal the moment `trading` is a real
module** — `boundaries/rules.py::_module_may_import` allows a module to import another module only
through its `contracts/`, with no exception for `ui/`:

```
modules.trading.ui.coordinators.strategy_overlay_coordinator -> modules.strategy.ui.strategy_overlay
modules.trading.ui.trading_presenter -> modules.strategy.application.services.strategy_registry
modules.trading.ui.trading_presenter -> modules.strategy.ui.signal_feed
modules.trading.ui.trading_presenter -> modules.strategy.ui.strategy_arming_coordinator
modules.trading.ui.trading_view -> modules.strategy.ui.strategy_params.strategy_params_dialog
modules.trading.ui.trading_view_model -> modules.strategy.ui.strategy_card_view_model
```

`screens/dashboard` and `screens/backtest` — the other two screens PR 4.4 folds in — carry the
identical shape: eleven files across the three screens import `modules.strategy.ui.*` or
`modules.strategy.application.services.strategy_registry` directly. All of it dates to PR 2.1e,
which moved `strategy`'s UI into `modules/strategy/ui/` while `trading`/`dashboard`/`backtest`
were still legacy, so none of it was ever checked against the module-to-module rule.

**Root cause, not just the symptom.** The imports are not a mistake at each call site; they are one
design decision, repeated: "the armed strategy" is a concept `strategy` owns, and the three screens
each need to show it, so each reaches for `strategy`'s concrete widget/coordinator/view-model
classes directly. The rule catching it now is doing its job — the coupling was always
module-to-module in shape, only unchecked because the importing side had not yet become a module.

## 2. Alternatives considered

| Alternative | Why it lost |
| :--- | :--- |
| Widen `_module_may_import` for `ui/ → ui/`, matching `_UI_SUPPORT_ZONES` and `_is_computation_library`'s precedent | Legalises the coupling without asking why it exists; `SignalFeed` and `StrategyArmingCoordinator` are behavioural coordinators `TradingPresenter` constructs directly (`self._arming_coordinator = StrategyArmingCoordinator(...)`), and `StrategyCardViewModel` is composed straight into `TradingViewModel`'s own data (`self._strategy = StrategyCardViewModel(self)`) — not a widget dropped into a `Place`. Widening the rule would keep three screens permanently reaching into another module's internals, the exact shape `architecture-rule.md` §3 exists to prevent |
| Publish these as `strategy/contracts/` | Contracts are data/behaviour interfaces, not concrete Qt classes — the same reasoning that deleted `IStrategyCatalog` for trying to carry `BaseStrategy` |

## 3. Decisions

| # | Decision | Status | Consequence |
| :-- | :--- | :-- | :--- |
| D1 | `strategy` contributes its UI onto `trading`, `dashboard` and `backtest`'s surfaces through the existing `contribute()` + `IContributionRegistry` + `Place` mechanism (built in Phase 0, used today by `TradingModule`'s own `DEV_PROBE`), instead of those three screens importing `SignalFeed`, `StrategyArmingCoordinator`, `StrategyCardViewModel`, `strategy_overlay.*`, `strategy_params.strategy_params_dialog` or `strategy_registry` directly | ✅ | A real redesign of how the armed-strategy card, chart overlay and params dialog reach each screen — not a file move. Blocks PR 4.4 until done. New `Place` members or a new contribution shape may be needed for a chart overlay and an inline view-model composite, neither of which is a panel-shaped `ContributionDescriptor` today |
| D2 | This redesign is its own piece of work, separate from PR 4.4, planned as `EPIC-025E` §3.2's new **PR 4.3m** | ✅ | PR 4.4 does not start moving `screens/trading`/`dashboard`/`backtest` until 4.3m lands and the boundary guard is clean against the moved trees |

**User's own words, choosing this over widening the rule:** *"P6. Sửa tận gốc rễ cơ chế (Fix the
mechanism, general over local)... Tuyệt đối không chọn giải pháp vá lỗi tạm thời... vậy bạn sẽ chọn
hướng nào? phải là redesign ko?"* — then, given the full size of the redesign (rewriting
Presenter/ViewModel internals across three screens) named explicitly: *"Làm redesign đầy đủ ngay,
tách khỏi PR 4.4."*

## 4. Open questions

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | What `Place` (or new kind) does a chart overlay (`strategy_overlay`) contribute as — it draws directly onto another screen's chart surface, not a dockable panel | PR 4.3m | 2026-09-17 |
| O2 | Does `strategy_params_dialog` become a `Place.MODAL` contribution `trading`/`dashboard`/`backtest` request by id, or does `strategy` publish a port the screen calls to open it | PR 4.3m | 2026-09-17 |
| O3 | `StrategyCardViewModel`'s data (composed into `TradingViewModel` today) needs a shape that crosses through a contribution or a contract rather than direct composition — measure what each screen's view actually reads from it before designing the replacement | PR 4.3m | 2026-09-17 |
