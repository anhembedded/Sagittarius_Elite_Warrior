# EPIC-048C — A presenter receives a narrow application gateway, not the whole container

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24, settled as G9 of the EPIC-047 charter; the [decision record](../DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) D6 and O1.
**Risk:** 🟡 — it touches ten presenters and twenty factories; a missed dependency shows as a screen that fails to build, which the offscreen tests catch.
**Complexity:** L — 30 functions and the `ScreenDescriptor.presenter_class` signature.
**Epic:** [EPIC-048](../README.md)
**Depends on:** [EPIC-048A](../completed/EPIC-048A_the_doors_rule_and_its_guard.md)

---

## 1. Context and problem
30 functions under `ui/` take the whole `IContainer` (DERISK §7.3, `5ddbd68`): the presenters `AlertsPresenter`, `AlertsSettingsPresenter`, `BackTestPresenter`, `BotsPresenter`, `DataManagementPresenter`, `MarketDataSettingsPresenter`, `DeskPresenter`, `MarketPresenter`, `TradingSettingsPresenter` and `TradePresenter`, and twenty factories and resolvers (`bots_dependencies_for`, `desk_dependencies_for`, `build_coordinators` and the others in DERISK §7.3). The signature is fixed by `screen_descriptor.py` → `ScreenDescriptor.presenter_class`, `(BaseView, IContainer)`. A presenter that holds the container can resolve anything, so the doors are open by construction. EPIC-047's remote backend is one more gateway only if a gateway exists.

## 2. Acceptance criteria
- [ ] ADR O1 is answered first, in this task's Design: one gateway per screen or one per module, and why.
- [ ] A presenter is built from its screen's gateway (a narrow interface in the application layer or in the module's contracts, whichever `architecture-rule.md` §3 allows) and receives no `IContainer`.
- [ ] The `ScreenDescriptor.presenter_class` signature no longer carries `IContainer`; the composition root builds each gateway from the container once.
- [ ] The guard of EPIC-048A reads **0** functions under `ui/` that take `IContainer`, and its baseline line is lowered in this pull request.
- [ ] Every screen builds and renders as before (offscreen), and the existing presenter tests are unchanged and green; where a test built a presenter from a container, it builds it from a fake gateway instead (`testing-rule.md`: doubles from the interface).
- [ ] No gateway exposes a method that returns a service, a port or the container itself.

## 3. Design
The hexagonal shape: the screen's use of the application is one interface, whose local implementation wraps the dispatcher and the bus, and whose remote implementation (EPIC-047) is another adapter (P7: the seam now, the variant later). The gateway carries the doors of ADR D1 and nothing else. Split per screen if the pull request grows past review size; the criteria apply to each part.

## 3a. Reuse
Search `.claude/rules/capabilities.md` for an existing dependencies object (`BotsDependencies` in `bots_dependencies.py` is one shape; R1 lists its fields): `used` as the model for the gateway where a field maps to a query; `not used because …` where it is a UI concern that stays local.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/*/ui/…` | the 30 functions take a gateway |
| `src/…/screen_descriptor.py` | the presenter factory signature |
| composition root | builds each gateway once |
| `tests/unit/architecture/baseline_ui_doors.json` | the container line lowered to 0 |
| `tests/…` | presenter tests on fake gateways |

## 5. Testing
Tier: unit and architecture, then the full gate. Each criterion maps to the guard, an offscreen build per screen, or the presenter tests. Not run.

## 6. Docs touched
`Docs/MODULES/<module>/` files for each module whose presenter wiring changes (`bots` today; `alerting` has a folder too), and `Docs/HLD/11_desktop_workbench.md` if it describes the presenter construction.

## Implementation notes (written when done)
Not written: not started.
