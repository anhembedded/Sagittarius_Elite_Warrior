# SPEC-003 — Check that the app can reach the exchange

- **Status:** ✅ built and proven
- **Actor:** trader (before turning trading on), operator (diagnosing a setup)
- **Origin:** `EPIC-021D`. Its §2.2 is where the rule "an English string from the exchange is
  not a stable contract" was decided, which is why this use case answers with named failure
  kinds.
- **Surfaces:** Tools → Check connection in every mode, its answer a word in the status bar and,
  on a failure, a message naming what to do (`EPIC-033H`) · the full report on Tools → Options →
  Trading · `exchange-status` on the command line and at the interactive prompt.

## 1. Trigger

*"Before I risk anything, tell me whether this app can actually talk to my account — and if it
cannot, tell me which part is wrong."*

## 2. Preconditions

1. A Futures Testnet API key pair is configured, from the environment or from
   `src/config/secrets.local.json`. **Not** having one is a first-class answer below, not a
   precondition failure.
2. The configured trading venue is Futures Testnet. This app does not talk to mainnet.

## 3. Main flow

1. The actor asks for the check — the control on Tools → Options → Trading, or `exchange-status`.
2. The app resolves credentials. If there are none, it stops here and answers
   `NOT_CONFIGURED` **without any network call**.
3. The app makes a small number of read-only requests: server time, account balance, position
   mode, open positions — and, on Futures since `EPIC-028O`, the account's Multi-Assets mode,
   read at most once every five minutes (it changes only when the actor changes it).
4. The app compares its own clock with the exchange's and keeps the difference in
   milliseconds.
5. The app answers with one immutable status: the venue, whether it is reachable, the named
   failure if it is not, the clock skew, the USDT balance, the position mode, the margin type
   and the number of open positions — and, since `EPIC-028D`, the **account summary** read from
   the same account payload: on Futures the available balance, wallet, margin balance,
   unrealized PnL, position mode and asset mode; on Spot the quote asset's free and locked parts
   and the equity. A Futures account in Single-Asset mode is summarised from its USDT asset; in
   Multi-Assets mode, from the account-wide totals, in USD across every margin asset.
6. Each surface renders that one value: the Options page as a label, the command line as a short
   report.

## 4. What must be true afterwards

- The actor can tell **which** part is wrong from the answer alone, without reading a log: a bad
  secret, a clock out of range, a key that is not valid for this venue, an unreachable network
  and an account in Hedge mode are five different answers, not one "failed".
- Nothing was changed. Every request in step 3 is read-only; running the check twice is
  indistinguishable from running it once.
- Every field beyond the venue, reachability and the failure is `None` **exactly when it was
  never learned** — the check failed before reaching it, or, for the margin type, there is no
  open position to infer it from (margin type is per symbol on Binance Futures, not
  account-wide).
- The command line tells spendable from held: on Futures it prints the wallet balance as
  `Wallet (USDT)` and, beside it, `Available (USDT)` (what a new order can use; the wallet also
  counts margin already committed) and the unrealized PnL. Either figure is `?` when it was not
  learned, never `0`. In Multi-Assets mode the line reads `Available (USD)` and one more line
  names the mode, so a USD total across every margin asset is never labelled USDT.
- The summary is `None` when a figure it needs is missing or not a number — never a summary with
  an invented zero — and a Spot summary's equity is `None` when a holding cannot be priced.
  A Futures summary is also `None` when the asset mode cannot be read: guessing it would label
  one mode's figures as the other's.
- A successful check is not permission to trade. Turning trading on is SPEC-004, and it runs its
  own check.

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| No credentials configured | `NOT_CONFIGURED`, and the report says so plainly | Decided before any request; there is nothing to ask the exchange |
| The API secret does not match the key | `BAD_SIGNATURE` | Binance `-1022`, translated once, at the one place allowed to read an exchange error code |
| The machine's clock is too far from the exchange's | `CLOCK_SKEW`, with the measured skew in milliseconds | Binance `-1021`. The number is shown because the fix is the actor's clock, and they need to see how far off it is |
| The exchange rejected the key (a mainnet or other-venue key, an IP off the allowlist, a missing permission) | `KEY_REJECTED` | Binance `-2015` covers all three and names none; the app is testnet-only, so a mainnet key is unknown there. The words list the causes and never say "expired" |
| DNS, TCP, TLS or a timeout — or any error code without a narrower name | `NETWORK` | The honest bucket. It is named `NETWORK` rather than `UNKNOWN` because that is what it is from the actor's side |
| The account is in Hedge mode | `HEDGE_MODE_UNSUPPORTED` — reachable, but not usable | This app's order model assumes One-way. "Connected fine, but this account cannot trade here" is not one of the other five, so it is its own answer |
| The Futures asset mode cannot be read (no answer, or an answer of another shape) | Reachable, no failure, and no account summary; one WARNING until it is readable again | The connection is fine; only which figures to show is unknown, and a guessed mode would mislabel them (`EPIC-028O`) |

## 6. What this use case does NOT promise

- It does not promise the account **can place an order**. It reads; it does not test order
  permissions. `order-dry-run` (SPEC-005) is the check that does.
- It does not promise a per-symbol margin type. The field is `None` unless an open position
  reveals one, and the app does not invent a default.
- It does not keep watching. The answer is a snapshot taken when asked; the connection can break
  a second later and nothing here will notice.
- It does not read or display a secret. The answer never carries the key or the secret, and
  neither does any log line on this path.

## 7. Ports and modules it exercises

`trading`: `IAccountSnapshot` (`check_connection()` — the sentence the Options page and the
command line both call), `ITradingAccountReader` (the account reads behind it),
`IExchangeSessionFactory` (the session the reads go through). `ExchangeConnectionStatus` and
`ConnectionFailureKind` are the published result. `support/binance_gateway` owns credential
resolution and the error translation.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| Every failure kind, and the fields left `None` for each | `tests/unit/modules/trading/application/queries/test_get_exchange_connection_status.py` | unit |
| Both implementations of the port answer the same way | `tests/unit/modules/trading/contracts/test_account_snapshot_contract.py` | contract |
| The account reads behind it | `tests/unit/modules/trading/contracts/test_trading_account_reader_contract.py` | contract |
| The command line's report for each outcome | `tests/unit/presentation/cli/test_exchange_status_formatter.py` | unit |
| The account summary each reader builds from its payload, and `None` rather than a guess | `tests/unit/modules/trading/adapters/binance/test_futures_account_reader.py`, `tests/unit/modules/trading/adapters/binance/spot/test_spot_account_reader.py` | unit |
| The summary over a real HTTP round trip | `tests/integration/infrastructure/binance/test_futures_account_reader_against_fake_server.py` | integration |
| The Options page renders the right label, and asks the port exactly once | `tests/unit/modules/trading/ui/settings/test_trading_settings_connection_check.py` | unit |
| Tools → Check connection: the status bar's word, the failure named where the user looks, and only the newest check writes | `tests/unit/modules/trading/ui/market/test_market_connection_check.py` | unit |
| A real check against the real Futures Testnet | `tests/testnet/test_connection.py` — **the user runs it**: `SEW_TESTNET_TESTS=1` plus real credentials, via `ci-local.ps1 -TestnetOnly`; the ordinary gate never invokes this tier | human |
