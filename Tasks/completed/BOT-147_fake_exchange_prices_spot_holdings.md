# BOT-147 — The fake exchange prices Spot holdings, so a Spot account read reports its equity

**Status:** ✅ Done (2026-10-04)
**Source:** The user, 2026-10-04: *"bạn tạo 1 PR kiểm tra xem, 2 bạn có làm việc liên tục đến khi merge được kho"* ("open a PR to check whether the two of you keep working until it can be merged"). This is the small real change that PR carries; the gap was seen in the fake-exchange journeys' logs.
**Risk:** 🟢 — test fixture only; the one consumer change is the Spot equity becoming a number instead of unavailable in fake-exchange tests.
**Complexity:** S — one route and two tests.
**Depends on:** None

---

## 1. Context and problem
`SpotAccountReader._compute_equity` prices every non-dust holding through `client.get_symbol_ticker`, which `python-binance` sends to `GET /api/v3/ticker/price` (`src/modules/trading/adapters/binance/spot/spot_account_reader.py:215`). The fake exchange served only `ticker/bookTicker` (`tests/sanity/fake_exchange/spot_routes.py`). Every journey that read the Spot account therefore logged the WARNING "SpotAccountReader equity: could not price BTC via BTCUSDT ticker", and the equity was `None`. No test could observe a priced Spot equity against the fake.

## 2. Acceptance criteria
- [x] Against the fake exchange, a real `SpotAccountReader` reports the equity as the quote balance plus each holding at its last price, with no WARNING logged.
- [x] `GET /api/v3/ticker/price` answers Binance's shape, follows the last price, and answers `-1121` for a symbol the fake does not list.

## 3. Design
Both ticker routes quote one fact, the symbol's last price. `SpotAccountState` exposes it as `last_price(symbol)`, and `spot_routes.py` owns both wire shapes in one `_ticker` function. Before, the state built the `bookTicker` dict itself, so a second ticker would have put a second wire shape in the state, and the state file sits at 397 of the 400-line limit.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/sanity/fake_exchange/spot_account_state.py` | `book_ticker` becomes `last_price`; the book's half-spread constant moves to the routes |
| `tests/sanity/fake_exchange/spot_routes.py` | `GET /api/v3/ticker/price`; both tickers through `_ticker` |
| `tests/integration/infrastructure/binance/test_spot_account_reader_against_fake_server.py` (new) | the two criteria |

## 5. Testing
- Integration: `test_the_spot_equity_prices_every_holding_at_its_last_price` (criterion 1) and `test_the_price_follows_the_last_price_and_a_bad_symbol_is_1121` (criterion 2).
- Regression: the existing `bookTicker` tests (`test_order_entry_reads_against_fake_server.py`) are unchanged and pass.

## Implementation notes (written when done)
- Red first: with the fixture change stashed, both new tests failed for the right reason (`assert None == Decimal('900000')`; "no route for '/api/v3/ticker/price'"). With it, they pass.
- `tests/integration` and `tests/unit/architecture`: 859 passed, 4 skipped. The commit tier (`ci-local.ps1 -SkipTests`) is green.
- The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR.
