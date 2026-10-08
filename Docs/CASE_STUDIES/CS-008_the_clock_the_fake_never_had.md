# CS-008 — The clock the fake never had

`BUG-189`: a Spot Grid on Mainnet halted five minutes after Start, `saved 0.0119 against 0 derived`. The owner's machine clock is not Binance's (`BUG-111`), so every history window opened after the bot's own first orders. The gate was green: the fake exchange answered `serverTime: 0` and stamped its orders with the machine's own clock, so two clocks could never disagree.

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| The `EPIC-035B` fake-exchange journeys | Server and machine shared `time.time()`, so a window starting at `run_started_at` always contained the bot's orders. | no: `exchange_clock_skewed_by` skews the fake |
| `BUG-111`'s offset tests | They proved the signature carried the offset, against a fake whose time was the epoch, and nothing read the offset again. | no: they assert a 90 s skew |
| The `IAccountHistoryReader` contract | It states windows and rows, not whose clock they are on. | no: the port states one clock |

## The fix
- `tests/integration/modules/bots/test_a_machine_clock_off_the_exchanges_on_the_fake_exchange.py` runs Start and the reconcile with the exchange 90 s behind and 20 s ahead of the machine; `tests/unit/modules/trading/adapters/binance/test_history_readers_machine_clock.py` pins the translation of both readers.
- `tests/sanity/fake_exchange/history_log.py` gives the fake one exchange clock, default equal to the machine's, that every stamp and `/time` answer use.
- The readers translate by `timestamp_offset`, in both directions.

## Where else this is still open
- Nothing else compares a machine time with an exchange stamp today (`captured_at`, `order_time`, `created_at` searched). A new comparison must go through a reader, or a fake that skews its clock will show it.
