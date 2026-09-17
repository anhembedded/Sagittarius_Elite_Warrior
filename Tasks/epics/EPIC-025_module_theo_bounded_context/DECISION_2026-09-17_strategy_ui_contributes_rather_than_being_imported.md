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
| D1 | `strategy` stops being imported by `trading`, `dashboard` and `backtest`: the params dialog arrives as a `Place.MODAL` contribution, and everything else the three screens read (strategy options, the parameter form's schema, parameter validation, the chart overlay's lines and zones) arrives as **data on a published port**, computed inside `modules/strategy` where `BaseStrategy` lives | ✅ | A real redesign, not a file move — blocks PR 4.4. **No new `Place` member and no new contribution shape are needed**: §4 O1–O4 measured every call site and each one lands on an existing mechanism (the port pattern, `Place.MODAL` + `show_modal`, `ICommandDispatcher`) |
| D2 | This redesign is its own piece of work, separate from PR 4.4, planned as `EPIC-025E` §3.2's new **PR 4.3m** | ✅ | PR 4.4 does not start moving `screens/trading`/`dashboard`/`backtest` until 4.3m lands and the boundary guard is clean against the moved trees |

**User's own words, choosing this over widening the rule:** *"P6. Sửa tận gốc rễ cơ chế (Fix the
mechanism, general over local)... Tuyệt đối không chọn giải pháp vá lỗi tạm thời... vậy bạn sẽ chọn
hướng nào? phải là redesign ko?"* — then, given the full size of the redesign (rewriting
Presenter/ViewModel internals across three screens) named explicitly: *"Làm redesign đầy đủ ngay,
tách khỏi PR 4.4."*

## 4. The three open questions, answered (2026-09-17, same day)

Answered by reading the real call sites rather than the plan, and decided against the ten
principles (`ONBOARDING.md` §12.5) rather than by preference. The user, as architect, delegated
the choice with the principles as the standard: *"Dựa vào hiến pháp mà quyết… tui không rành
implement, tui là SA."*

### O1 — the chart overlay. **First answer was wrong; P6 caught it.**

The overlay's three entry points (`compute_strategy_indicator_lines`,
`compute_strategy_trend_zones`, `assign_strategy_line_colors`) are Qt-free pure functions over a
`BaseStrategy` instance plus candles, so the first answer here was "publish the three functions as
contracts and let `trading` keep calling them". That is wrong, and it is wrong in the exact shape
P6 names: to call them, `trading` must first build the throwaway strategy
(`strategy_overlay_coordinator._build_throwaway_strategy`), which needs `type[BaseStrategy]` from
the registry. The computation sitting on the caller's side is *why* the caller needs the other
module's class at all. Publishing the functions would legalise the symptom and leave the cause.

**Answered:** `strategy` publishes the overlay as **already-computed data**. The throwaway
strategy, the registry lookup and the three compute calls all stay inside `modules/strategy`, where
the domain model lives; the port answers with line series and zones. `chart_coordinator` keeps
drawing them through `support/charting` exactly as it does now — that part was never the problem.
No `Place` is involved: an overlay is not a contributed widget, it is data the screen already knows
how to draw (P5 — the existing chart API is the mechanism; nothing new is invented).

### O2 — the params dialog. **`Place.MODAL`, and the runtime hook already ships.**

`WorkbenchSurface.show_modal(title)` exists and is in production use:
`dashboard_view.py:287` opens the manual-order dialog with
`self._surface.show_modal(MANUAL_ORDER_DIALOG).show()`, and `_keep_modal` fills the same
`_modals` dict whether the descriptor came from a screen's own `contribute()` or from another
module's `contribute(registry)` — `build_surface()` walks both through one `_FILL_ORDER`.

**Answered:** `strategy` contributes `Place.MODAL` with a `StrategyParamsDialog` factory onto the
`trading`, `dashboard` and `backtest` surfaces; each screen's "Strategy Parameters…" button calls
`show_modal(...)` instead of importing the dialog. Nothing new is built (P5), and the seam is
already load-bearing for a second case (P7).

### O3 — `StrategyCardViewModel`, and what actually crosses

Measured at the call sites: `TradingView` builds its own plain Qt controls (`_strategy_combo`,
`_sizing_spin`, `_leverage_spin`, `_arm_button`, `_disarm_button`, `_params_button`) — none of them
is strategy's widget. What crosses the boundary is only (a) the data those controls display
(options, armed summary, busy flag, last signal text) and (b) the intents they raise (select, set
sizing, arm, disarm).

**Answered:** each screen keeps its own view model and its own controls. The data comes from the new
port plus the existing `IArmedStrategy`; the intents go out as commands through
`ICommandDispatcher`, which is why the command side needs publishing (O4). `StrategyCardViewModel`
as a shared concrete class disappears rather than being relocated — the duplication it was written
to avoid (`EPIC-023C`) is now data on a port, computed once inside `strategy` (P3: one computation,
no copies).

### O4 — the command side, found while answering O3

`ICommandDispatcher.dispatch(handler_class, dto)` takes the handler class **as the lookup key** —
its own docstring says so — so any caller of a use case must hold that type. `ArmStrategyCommand`,
`ArmStrategyCommandHandler`, `ArmStrategyResult`, `ArmStrategyBlockReason` and the `Disarm`
equivalents live in `modules/strategy/application/use_cases/`, and no module dispatches another
module's command anywhere in the tree today (measured: zero occurrences) — `trading` will be the
first.

**Answered:** those command/result/reason types are published in `modules/strategy/contracts/`.
This is the app-wide dispatch pattern applied, not a new one (P5), and it does **not** contradict
`IArmedStrategy`'s deliberate omission of `arm()`/`disarm()`: the command stays the single way in,
with its validation, symbol lease and events intact. A port method that armed a strategy is still
refused.

### What this does **not** do: reverse PR 2.1c

PR 2.1c deleted `IStrategyCatalog` on two findings — a keys-only port served no consumer, and a
published contract may not carry `BaseStrategy`. The answer above is neither: not a keys-only port,
and not a class-carrying one. It is a port that answers the questions the three consumers actually
ask, in data, with the class-handling kept inside the module that owns the class. 2.1c's second
finding stands untouched, which is why this needed no user decision to reverse it (P2 — checked
what the earlier decision protected before assuming it was in the way).

## 5. O5 answered — the ports, declared, and O2 corrected a second time

Measured every call site of all **three** consumers before naming anything, because that is the
mistake PR 2.1c made in the other direction: `IStrategyCatalog` was declared from the plan, and
deleted once the consumers were read.

### The finding that shrank the redesign: `strategy_params/` is not strategy's UI

Read by imports rather than by location: `param_field.py`, `param_stepper.py` and
`strategy_params_dialog.py` import **only** `support/ui_kit` (`Palette`, `kit`,
`form_field_style`, `kit.widget_value`) plus their own siblings. Not one of them touches
`BaseStrategy`, a strategy contract, or anything else under `modules/strategy`. Only
`bot_params_form.py` does (`strategy_cls().inputs`).

So three of that package's four files are **generic UI-kit furniture** parked in
`modules/strategy/ui/` by PR 2.1e because their *data* comes from a strategy — a different thing
from ownership, and the shape `architecture-rule.md` §5 rules 1–2 forbid (a declared-field editor
and a strategy-schema reader are two abstraction levels sharing one directory).

**This corrects O2 again: no `Place.MODAL` contribution is needed.** The dialog moves to the UI
kit, where both screens may already import it (`_module_may_import`: a module's `ui/` may import
`support/ui_kit` whole). `Place.MODAL` stays available for a real case; this was not one (P7 — do
not build the variant when the case turns out not to exist).

### Every crossing, and where it lands

| Crossing today | Lands | Mechanism | Principle |
| :--- | :--- | :--- | :--- |
| `strategy_params.strategy_params_dialog`, `param_field`, `param_stepper` | `support/ui_kit/param_form/` | already-legal `ui/ → support/ui_kit` | P5, §5 r1 |
| `bot_params_form.build_bot_params_schema` | `IStrategyCatalog.params_form()` | published port | P6 |
| `bot_params_form.parse_bot_params` | `IStrategyCatalog.validate_params()` | published port | P6 |
| `bot_params_form.build_bot_params_rows` | **deleted** — it flattened groups into `rowType: header/field` dicts for QML's `Repeater`, and PR 4.3 deleted the QML; QtWidgets renders groups directly | — | P6 |
| `bot_params_form.step_numeric_param_value` | `support/ui_kit/param_form/` (pure arithmetic over one field; needs no strategy) | with the widget | P3 |
| `strategy_overlay.compute_*`, `assign_strategy_line_colors`, `strategy.chart_line_{colors,widths}()` | `IStrategyChartOverlay.overlay_for()` — computed inside `strategy` | published port | P6 |
| `strategy_registry.available()` → `type[BaseStrategy]` | **stops crossing**: the throwaway instance is built inside `strategy` | — | P6 |
| `strategy_display.humanize_strategy_key` | **stops crossing**: `options()` already returns the label | — | P3 |
| `Arm`/`DisarmStrategyCommand` + handler + result + reason | `modules/strategy/contracts/` | `ICommandDispatcher`'s documented lookup-key pattern | P5 |
| `SignalFeed` | `modules/trading/ui/` (12 lines; its only strategy tie is the published `SignalGeneratedEvent`) | `architecture-rule.md` §6 — a subscriber is owned by what it drives | P6 |
| `StrategyCardViewModel` | **deleted** — each screen keeps its own card state (§4 O3) | — | — |
| `StrategyArmingCoordinator` | each screen's own `coordinators/`, reading the port + dispatching the published commands | `async-ui-action-rule.md` §2 | P6 |

### The two ports (ISP: two consumer roles, two ports)

```python
# modules/strategy/contracts/i_strategy_catalog.py   — the strategy card + backtest config
class IStrategyCatalog(ABC):
    def options(self) -> tuple[StrategyOption, ...]: ...           # key + display label, sorted
    def params_form(self, key: str,
                    values: Mapping[str, object]) -> tuple[ParamGroup, ...]: ...
    def validate_params(self, key: str,
                        raw: Mapping[str, object]) -> ParamValidation: ...

# modules/strategy/contracts/i_strategy_chart_overlay.py — the two chart coordinators
class IStrategyChartOverlay(ABC):
    def overlay_for(self, config: LiveStrategyConfig,
                    candles: Sequence[MarketData]) -> StrategyOverlay: ...
```

`IStrategyCatalog` is HLD §3.4's own planned name, revived deliberately: PR 2.1c deleted it as a
**keys-only** port that served nobody. It comes back with the three methods its consumers were
measured to actually call, and still carries no `BaseStrategy` — so 2.1c's second finding holds
(§4's closing note).

`overlay_for()` runs on a worker thread on the backtest side (`indicator_coordinator` computes
under an `action_id`), so the implementation must be thread-safe — it is pure computation over its
arguments, which is how (SDD "Threading contract").

### The DTOs, and why two of them live in `core/contracts/`

```python
# core/contracts/param_field.py — strategy fills them in, support/ui_kit renders them
class ParamKind(Enum): INT, FLOAT, BOOL, STRING, CHOICE
@dataclass(frozen=True, slots=True)
class ParamField:  name, label, kind, default, value, minval, maxval, options, suffix, step
@dataclass(frozen=True, slots=True)
class ParamGroup:  label: str; fields: tuple[ParamField, ...]

# modules/strategy/contracts/ — strategy → its consumers only
StrategyOption(key, label)
ParamValidation(values: Mapping[str, object], error: str)       # error "" means accepted
StrategyOverlay(lines: tuple[OverlayLine, ...], zones: tuple[TrendZone, ...])
OverlayLine(name, x: tuple[float, ...], y: tuple[float, ...], colour: str, width: float)
TrendZone(start: float, end: float, colour: str, opacity: float)
```

`ParamField`/`ParamGroup`/`ParamKind` must sit in **`core/contracts/`**, not in either side, and the
import table is what decides it: `support/ui_kit` may import `core` but **no** module (not even a
`contracts/` package), and a `modules/*/contracts/` file may not import `support/ui_kit` (the UI-kit
exemption covers a module's `ui/` only). `core/contracts` is where both sides can meet — the same
reason `nav_metadata.py` gives for living there, in this same epic (P5: follow the precedent rather
than invent a third arrangement).

`ParamKind` is a translation of `support/indicators/scripting.InputKind`, not an alias: `core`
imports nothing but `core`, so the mapping happens once, inside `strategy`'s adapter, at the
publishing edge. Both terms go in `Docs/VOCABULARY/README.md` in the same commit.

Loose `list[dict]` does not cross: `code-quality-rule.md` §1 forbids it, and publishing the
QML-era dict shape into the Published Language would outlive the toolkit that asked for it.

## 6. Still open

| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O6 | `LiveStrategyConfigStore` (an `application/` service the arming coordinator calls to persist a successful arming) also stops being reachable once the coordinator is a screen's. Publish it as two port methods, or move the persistence into `ArmStrategyCommandHandler` where the validation and the lease already are? The second is cleaner and is a **behaviour move**, which ADR D12 keeps out of a structural change — so it is a decision, not a detail | PR 4.3m's last commit | 2026-09-17 |
