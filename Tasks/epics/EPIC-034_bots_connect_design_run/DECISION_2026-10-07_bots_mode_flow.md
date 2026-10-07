# ADR — A bot reaches Start through Connect, Design and Run; a key is enough to trade, and a mainnet key is read, never traded

**Epic:** [EPIC-034](README.md)
**Date:** 2026-10-07
**Status:** Accepted (D1–D10)
**Decided by:** the owner. D1–D4 are quoted where they are made; D5–D10 were accepted as recommended on 2026-10-07: *"duyệt hết"* (approve them all). That includes D10's new `keyring` dependency, which ONBOARDING §7 reserves to the owner.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context
✅ A new Grid bot on `master-warrior` 2889775 could not start, and nothing told the owner why:
- **The reason is computed but never shown.** `ActionAvailability.reason` (`src/modules/bots/ui/bots_screen/bot_action_rules.py:63-87`) is not displayed; `bots_command_binding.py:7-10` records this as accepted in `EPIC-033D`. Only a refused plan reaches the user (`bot_plan_panel.py:123-127`).
- **Five refusals surface only after the click:** trading off, venue not enabled, the symbol lease, the budget, another active bot (`application/services/grid_start_preconditions.py:68-109`). They appear in a status label (`bots_presenter.py:355`).
- **The bot chart is silent.** It goes live only for a started bot (`bot_chart_host.py:43,108-110`). Its four messages go out on `LiveCandleChart.logged`, which the Bots module never connects (`live_chart_coordinator.py:117-170`); the Desk does (`desk_presenter.py:214`).
- **The venue reads as an identifier** (`bots_table_models.py:71`, `bot_facts.py:82`, `new_bot_dialog.py:94`). The status bar reports the app's primary venue, not the bot's (`connection_words.py:51-57`).
- **The balance is checked only at Start**, when trading registers the owner budget (`grid_start_preconditions.py:100`). The plan's other checks run before the click (`domain/grid/grid_checks.py`).
- **Two switches gate every order.** A venue toggle in Options read once at start-up (`binance_endpoints.py:130-167`), and the Enable trading switch (`application/session/enable_trading/handler.py`). The switch reconciles the whole account and refuses when a position the app did not open exists.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | A bot reaches Start through three steps, each unlocking the next. **Connect**: the venue's account, the key's permissions, the symbol's filters and price are read. **Design**: the chart and the parameters, each constraint an assertion with its numbers. **Run**: saved, reconciled, started. | Accepted | 🟢 the owner: *"bot phải có state là đã kết nối được với account … sau đó người dùng mới xem chart, và set các param, các param đảm bảo được assert đúng với các ràng buộc"* (a bot must first be connected to the account; then the user sees the chart and sets the parameters, asserted against the constraints) | The chart and the plan are locked until Connect succeeds; every reason is visible before the click. Delivered by `EPIC-034D`, `034F` and `034H`. |
| D2 | Every venue with a usable key is on. The Spot and Futures toggles in Tools → Options leave, and with them the restart a venue change needed. | Accepted | 🟢 the owner: *"2 tính năng enable trading và enable spot, future tui thấy thừa và không cần thiết, xóa đi, mặc định là enable hết luôn"* (the enable trading and enable Spot/Futures features are redundant and unnecessary; delete them; everything enabled by default) | A venue without a key is still shown, with "no key" as its Connect result. Delivered by `EPIC-034B`. |
| D3 | The trading ON/OFF switch leaves. Its reconciliation (read the whole account, refuse when a position the app did not open exists) and the opening of the order session and user data stream run inside the action that needs them: Start a bot, arm a strategy, place a manual order. Emergency stop stays. The first Start on a mainnet venue, when one exists (`EPIC-026`), asks a confirmation that names real money. | Accepted | 🟢 the owner chose option A of two: *"A, làm theo đề xuất của bạn"* (A, do as you propose). Option B, always on with no check, was rejected. | One step instead of three; the guard against foreign positions is kept. SPEC-004 changes from a switch to a precondition. Delivered by `EPIC-034C`. |
| D4 | A mainnet key is read, never traded. The read-only mainnet account is an `AccountSource` with a reader port only. It is not a `TradingVenue`: no trading session factory, no trading client, no path through `execute_order`. An architecture guard fails if any path from it reaches order submission. Its credentials have their own names (`BINANCE_MAINNET_READONLY_API_KEY` / `_SECRET`). | Accepted | 🟢 the owner: *"giờ tui đưa key mainnet thì nó phải get được thông tin của tôi, đó là 1 milestone trong epic"* (when I give a mainnet key it must read my information; that is a milestone of this epic) | `EPIC-026` D3 keeps its lock: no mainnet `TradingVenue` member. Its D6 was cancelled by the owner the same day, so reading mainnet before a soak contradicts nothing. Delivered by `EPIC-034E`. |
| D5 | The key's permissions are read (`GET /sapi/v1/account/apiRestrictions`). A key that can withdraw is refused, and the refusal names the permission. A key that can trade is accepted read-only, with advice to create a read-only key. | Accepted | 🟢 the owner: *"duyệt hết"* | The app never holds a credential that can move funds off the exchange. |
| D6 | Connect runs by itself when a bot is selected. One snapshot per venue is shared by every bot on it, re-read on a timer and on Refresh. | Accepted | 🟢 the owner: *"duyệt hết"* | Reading is risk-free; the user never has to ask for what the screen needs. |
| D7 | A constraint either **blocks Start** or **advises**. It blocks for the exchange's rules and for money: balance, minimum notional, per-order cap, open-order limit, price band, break-even after fees, the stop loss and take profit on the right side of the range. It advises for strategy judgement: ATR, slippage room, spacing. | Accepted | 🟢 the owner: *"duyệt hết"* | A blocked Start names the constraint and the field; advice never blocks. |
| D8 | "Save and Start" is the Run step's one primary action; Save stays for drafts. | Accepted | 🟢 the owner: *"duyệt hết"* | The hidden "save first" refusal disappears. |
| D9 | The chart can go live while the bot is a draft. It is a view-only price stream that places nothing and needs no trading. | Accepted | 🟢 the owner: *"duyệt hết"* | The user sets the range against the live price. Delivered by `EPIC-034G`. |
| D10 | The mainnet secret is stored in the operating system's keyring, not in `secrets.local.json`. | Accepted | 🟢 the owner: *"duyệt hết"*, which approves adding the `keyring` package (ONBOARDING §7) | Without it, the mainnet key is read from the environment only and never written to disk. |

## 3. Alternatives considered
- **Option B for D3: always on, no reconciliation.** Rejected by the owner. With a mainnet key it would let a bot or an armed strategy trade real money the moment the app starts, next to positions the app did not open.
- **Mainnet as a `TradingVenue` member in read-only mode.** Rejected: a flag on a trading venue is the "second path" `EPIC-026` D3 forbids. A separate type with no trading port makes the wrong state unrepresentable (`code/errors.md` #8).
- **Keeping the Options toggles but applying them without a restart.** Not taken: the owner judged the toggles unnecessary, and a key already says which venue the user means.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | ~~D5–D10 as recommended?~~ Answered 2026-10-07: accepted. | — | 2026-10-07 |
| O2 | Does the plan already check the base inventory needed by the sell levels above the price? To be read in the code by `EPIC-034F`. | EPIC-034F's design | 2026-10-07 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-034D](incomplete/EPIC-034D_connect_step.md), [EPIC-034F](incomplete/EPIC-034F_design_step_constraints.md), [EPIC-034H](incomplete/EPIC-034H_run_step_readiness.md) | Not started | Not yet verified |
| D2 | [EPIC-034B](incomplete/EPIC-034B_every_venue_with_a_key_is_on.md) | Not started | Not yet verified |
| D3 | [EPIC-034C](incomplete/EPIC-034C_trading_switch_folded_into_actions.md) | Not started | Not yet verified |
| D4, D5, D10 | [EPIC-034E](incomplete/EPIC-034E_mainnet_read_only_account.md) | Not started | Not yet verified |
| D6 | [EPIC-034D](incomplete/EPIC-034D_connect_step.md) | Not started | Not yet verified |
| D7 | [EPIC-034F](incomplete/EPIC-034F_design_step_constraints.md) | Not started | Not yet verified |
| D8 | [EPIC-034H](incomplete/EPIC-034H_run_step_readiness.md) | Not started | Not yet verified |
| D9 | [EPIC-034G](incomplete/EPIC-034G_chart_live_state.md) | Not started | Not yet verified |
