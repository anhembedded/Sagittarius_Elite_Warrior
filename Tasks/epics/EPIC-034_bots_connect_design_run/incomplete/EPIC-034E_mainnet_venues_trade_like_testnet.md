# EPIC-034E — Mainnet trades exactly like testnet: two mainnet venues from the same code, the keyring, withdrawal keys refused, one real-money confirmation

**Status:** 🟡 In progress (built and proven on the fake Binance server; only the owner's check with their own key remains)
**Source:** the owner, 2026-10-07 — first *"giờ tui đưa key mainnet thì nó phải get được thông tin của tôi"* (when I give a mainnet key it must read my information), then, after the read-only design: *"testnet sinh ra để test logic, rồi mainnet chạy trên đó để kế thừa sự đúng đắn"* and the decision **D11**: *"mainnet giao dịch giống hệt testnet, không chặn lệnh nào … tôi chấp nhận rủi ro"*. This file's scope changed from a read-only source to D11's venues; the earlier read-only build (PR #417) was removed by it.
**Risk:** 🔴 — the first code that sends real-money orders
**Complexity:** L — a new `TradingVenue` pair through the assembly, credentials, Connect and two confirmations
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md), [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md), extended by this task
**Depends on:** [EPIC-034D](../completed/EPIC-034D_connect_step.md)

---

## 1. Context and problem
D4 first made mainnet a read-only `AccountSource`, a second implementation of the account read that no testnet run proved anything about. The owner rejected that: the testnet exists to test the logic and mainnet runs on the same code. D11 supersedes D4 and `EPIC-026` D3 (the lock that kept mainnet out of `TradingVenue`).

## 2. Acceptance criteria
- [x] `TradingVenue` has `SPOT_MAINNET` and `FUTURES_MAINNET`, titled "Spot Mainnet" and "Futures Mainnet", with the right `market_type`, `supports_order_submission` and `has_positions`; the testnets stay first, so the primary venue is never real money.
- [x] Each is built by the same `VenueAssembly` path as its testnet twin; the only difference is `testnet=False`, reaching the client through one function (`new_client`, timeout plus server-time offset) that replaced every copy in the Spot and Futures session factories, unsigned clients included.
- [x] No mainnet-specific reader, trading client or parser (`test_a_mainnet_venue_is_built_from_the_same_classes_as_its_testnet_twin`).
- [x] The Connect step reads each mainnet venue through `ComposedVenueAccountReader` like every other venue, with one step in front: the key gate (D5).
- [x] A key that can withdraw is refused with `WITHDRAWAL_ENABLED` before any account read; a key that can trade is accepted (no advice, D11).
- [x] The secret is in the OS keyring, never in `secrets.local.json` (D10): `MainnetCredentialsProvider` has no file source.
- [x] Credentials: `BINANCE_SPOT_MAINNET_API_KEY` / `_SECRET`, `BINANCE_FUTURES_MAINNET_API_KEY` / `_SECRET`; `scripts/save_mainnet_key.py spot|futures` stores either after the gate accepted it. `BINANCE_MAINNET_READONLY_*` and the read-only source are gone.
- [x] The first Start (or Resume), arm or manual order on a mainnet venue in a session asks one confirmation that names real money; declining sends nothing; a testnet is never asked.
- [ ] The owner trades on their own mainnet key (manual check): **not run**, see Resume.

## 3. Design
`TradingVenue` carries `is_testnet`/`is_mainnet`. `new_client(venue, credentials)` (`adapters/binance/binance_client_builder.py`) is the one place a trading `Client` is built; `FuturesSessionFactory(venue)` and `SpotSessionFactory(venue)` hold the venue, and `VenueAssembly` builds one per venue. `AccountSource` is one member per venue. The key gate is an optional step of the one snapshot assembler. The confirmation is `IRealMoneyConsent` (asked once per mainnet venue per session, answered by a dialog, asked from the Bots screen before Start/Resume/Arm and from the order desk before a manual order's own confirmation). Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md) D11.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/contracts/trading_venue.py`, `account_source.py` | the two members; the source per venue; `venue_alignment.py` says "orders on testnet" only for a testnet venue |
| `src/modules/trading/adapters/binance/binance_client_builder.py` | the one `Client` constructor |
| `futures_session_factory.py`, `spot/spot_session_factory.py`, both account readers and user data streams | the venue's flag and name, no hard-coded testnet |
| `src/support/binance_gateway/adapters/env_first_credentials_provider.py` | the mainnet names and `MainnetCredentialsProvider` (env, then keyring, no file) |
| `adapters/binance/mainnet/` | `ApiRestrictionsKeyGate`, `key_permissions_*`, `mainnet_key_enrolment.py`, `keyring_secret_store.py` |
| `composition/venue_assembly.py`, `venue_accounts.py` | per-venue factories and credentials; every reader is `ComposedVenueAccountReader`, mainnet with the gate |
| `contracts/i_real_money_consent.py`, `application/real_money_consent.py`, `ui/real_money_dialog.py`, the bots dialogs and `command_for`, `with_real_money_consent` | the confirmation |
| Trade menu, desk titles, environment banner | each venue's own name and access key; the banner says REAL MONEY for mainnet |
| removed | `MainnetReadOnlyAccountReader`, `MainnetReadSessionFactory`, `IMainnetReadClient`, `ICredentialsResolver`, `AccountSource.SPOT_MAINNET_READONLY`, the Mainnet account window and query, `test_mainnet_has_no_order_path.py` and its probes |

## 5. Testing
Each mainnet venue runs against the fake server through the Connect path (`tests/integration/modules/bots/test_mainnet_venues_on_the_fake_exchange.py`); `testnet=False` reaching the client of a mainnet venue and `testnet=True` the testnets' is asserted through the real assembly (`test_module_venue_contexts_binding.py`) and in the builder (`test_binance_client_builder.py`); the gate, the enrolment, the credentials and the consent each have their unit tests. Never a call to `*.binance.com`: the sandbox cannot reach it and no test places or simulates a mainnet order.

## Implementation notes (written when done)
Not done: the owner's own-key check remains, so this file stays in `incomplete/` (`ONBOARDING.md` §3).

**Decisions.**
- **`AccountSource` stays**, one member per venue, because the Connect step reads an account and never sends an order; it no longer has a source without a venue.
- **The venue menu entries have their own access keys** (F, S, U, P): two venues per market made `&Futures` and `&Futures` collide, which the action declaration refuses at boot.
- **`save_to_file` keeps its name** on `IExchangeCredentialsProvider`; for a mainnet venue it writes to the keyring. Renaming it touches 39 call sites, none of which are mainnet.
- **The banner always names the mainnet venues** as real money, because every venue is assembled whether or not it has a key; it does not know a key is absent.
- **A venue's account status names its venue**, so the Spot account reader no longer reports `SPOT_TESTNET` for a mainnet account.

## Resume
- **The owner's manual check (the one open criterion).** Run `scripts/save_mainnet_key.py spot` (or `futures`) once, or set the two environment variables of the venue; open the app, choose Trade → Venue → Spot Mainnet or Futures Mainnet, and Connect shows the real balances. A key that can withdraw shows the refusal. The first order asks the real-money question once. The sandbox cannot reach `*.binance.com` (HTTP 451), so none of this ran against the real exchange.
- **Not done and not asked for:** mainnet-specific caps and a typed acknowledgement (`EPIC-026` D5): D11 says no order is blocked.
- **Known gap, flagged not fixed — one market-data venue for every desk:** the Connect snapshot (balance, rules, commission, price) and the Design step's planner numbers are read through the bot's own venue ports, so a mainnet bot sees mainnet numbers there. The Bots chart, its live stream and the grid backtests read the one process-wide `MarketDataVenue` (`EXCHANGE_MARKET_DATA_VENUE`, default `mainnet_public`): right for the mainnet venues, wrong for the testnets, and with `futures_testnet` the other way round. `VenueAlignment` now has `DATA_TESTNET_ORDERS_MAINNET` (DANGER banner, real money on testnet prices) and judges every enabled venue, the mainnet ones first; it is a warning, not a gate on Start. The full fix is a market-data source per trading venue (sync, klines and stream ports keyed by venue; `spot_candle_feed(container, venue)`), which is a `market_data` change, not this PR's.
- **The keyring (D10)**: `requirements.txt` has `keyring` since PR #417 (the owner allowed it on 2026-10-07).
