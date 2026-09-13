# EPIC-025C — Phase 2: `modules/strategy` (the Core domain)

- **Status:** 🔴 Backlog
- **Repository:** Elite
- **Blocked by:** B · **Blocks:** D
- **Read first:** HLD §3.4; ADR D1 (`strategy` is the Core domain, separated from `trading` — the
  cost of keeping them merged was `BUG-112`).

## 1. What to do

1. `modules/strategy/`: `domain/strategies`, `services/live_strategy_*`, the
   `use_cases/trading/{arm, disarm}_strategy` handlers (moved out of trading),
   `StrategyArmingCoordinator` (392 lines, from `ui/common`), `signal_feed`.
2. `contracts/`: `IStrategyCatalog`, `IStrategyEngineFactory` (for `backtesting` in Phase 3), the
   DTOs `StrategyDescriptor` and `ArmedStrategySnapshot` (carrying `symbol`), the existing
   `SignalGeneratedEvent` (name unchanged) and the new `StrategyArmedEvent` / `StrategyDisarmedEvent`
   (carrying `symbol`).
3. `strategy` **consumes** `trading.contracts.IOrderSubmission` — never the reverse (Customer /
   Supplier: `trading` is the supplier). The symbol lease **adds to** the existing rules: `strategy`
   calls `ITradingSession.claim_symbol` on arm and `release_symbol` on disarm; `arm_strategy` still
   reads the session's enabled state. **Seam for two strategies on two symbols (ADR §7 item 15):**
   `LiveStrategySession` is keyed by symbol internally even while only one entry exists, so the
   second entry later is a local change. If ADR O4 is decided as option C, `position_sizing_bridge`
   and `MarginRiskPolicy` move here behind `ISizingPolicy`. Signal overlays on
   the chart go through `IChartHost` (HLD §4).
4. Contributed widgets: the strategy card (one implementation shared by Trading and Dev Board), the
   last-signal card, the parameters dialog.

## 2. Done when

- The guard confirms that `modules/trading` imports **nothing** from `modules/strategy`, not even
  its `contracts/`.
- Arm / disarm / tick → automatic order runs on Testnet exactly as before (confirmed by the user).
