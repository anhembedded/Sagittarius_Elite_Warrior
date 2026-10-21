# BOT-224 — Options > Trading shows this machine's public IP, so the key's IP whitelist can be set

**Status:** ✅ Done (2026-10-21)
**Board:** A Show public IP button on Options > Trading asks an IP-echo service only on the click, shows the public IPv4 as selectable text with Copy and the whitelist advice, and names it in the `-2015` row.
**Source:** Owner, 2026-10-21, via the delivery coordinator: adding a mainnet key answered -2015 for every venue because the key's IP whitelist held the LAN address 192.168.1.20 and two stale public IPs; the owner had to run `Invoke-RestMethod https://api.ipify.org` by hand and asked for "a get IP button on that page" (approved).
**Risk:** 🟢 — a read-only call to a third party, made only on a click; no order, key or setting is touched.
**Complexity:** S — one query behind a port, one adapter, one button and its read-out.
**SPEC (optional):** [SPEC-003](../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md)
**Depends on:** None

---

## 1. Context and problem
Binance matches a key's IP whitelist against the public address it sees and never reports that address on the paths this app uses (`outbound_address_check.py` says so). The page could not tell the owner which address to whitelist.

## 2. Acceptance criteria
- [x] Show public IP next to Check connections fetches the public IPv4 on the click and shows it as selectable text with a Copy button and one line saying to put it in the key's IP whitelist and that a LAN address never matches (`test_trading_settings_public_ip.py`).
- [x] Once known, the `-2015` row names the address; a failed lookup leaves its words as they were (same file).
- [x] The IP service is never called at startup, by Check connections or in the background: asked 0 times until the click (same file).
- [x] `api.ipify.org` with one fallback, `checkip.amazonaws.com`, 5 s timeout each; a failure is one plain sentence, never a crash or message box (`test_urllib_public_address_reader.py`, same file).
- [x] Off the UI thread under the action tracker; a lookup out when the dialog closes is dropped, a key action is not (same file).
- [x] The address is not logged at INFO or above (same file).
- [x] Fits at the dialog's minimum size, light and dark: frames in `BOT-224_assets/`.

## 3. Design
`IPublicAddressReader` (port, `trading/contracts`) answers a `PublicAddressLookup`, an address or a failure kind, never a `None` and never an exception. `UrllibPublicAddressReader` is the adapter, the standard library as `alerting`'s webhook transport does: no dependency. `GetPublicAddressQuery` carries it through the dispatcher. The presenter keeps the last connection status and the looked-up address, so the row's words are built again when the address arrives (`key_rows.py`). Cancellation: the view tells `dialogClosed` when its window hides but not when another Options page is chosen; the presenter fences a lookup still out. A pending `urllib` request cannot be interrupted, so the 5 s timeouts bound the worker.

## 3a. Reuse
`INotifier`: not used, a failure here is a sentence on the page, not a command failure. `StateBadge`, `plain_label`, `EnumLabels`, `ActionOwnershipTracker`, `ICommandDispatcher`: used. HTTP client: `urllib`, as `alerting` (no new dependency).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `trading/contracts/i_public_address_reader.py`, `public_address_lookup.py` | port and result |
| `trading/adapters/network/urllib_public_address_reader.py` | the adapter |
| `trading/application/queries/get_public_address/` | the query and its handler |
| `trading/composition/adapter_bindings.py`, `query_bindings.py` | the bindings |
| `trading/ui/settings/` | button, read-out, words; `key_rows.py` and `trading_settings_actions.py` split out of the presenter to keep it under 400 lines |
| `Docs/SPEC/SPEC-003_check_the_exchange_connection.md` | the new row and its evidence |

## 5. Testing
Unit: the new tests named above, and the existing Trading page tests. Architecture guards run. The GitHub Actions `-Full` run is recorded on the PR.

## 6. Docs touched
`Docs/SPEC/SPEC-003`, §5 and §8. No `Docs/MODULES/trading/` folder exists.

## Implementation notes
- Review round 1 found that `dialogClosed` never fired under the Engine's `OptionsDialog`: `done()` takes each page out (`setParent(None)`) before it hides the dialog, so a hide event saw a visible window. The view now emits on `QEvent.ParentChange` with no parent, and the tests close a real `OptionsDialog` by `accept()` and `reject()` (red when the emit is removed) and check that choosing another page keeps the lookup.
- Local: the Trading and architecture unit tests pass; the GitHub Actions `-Full` run on the PR's head is the full gate.
- Not fixed here: at the dialog's minimum size the State column's long `-2015` sentence is clipped by the grid, the same before this change (frames in `BOT-224_assets/`); filed as [BOT-225](../backlog/BOT-225_the_trading_options_state_column_clips_a_long_failure_sentence.md). The address is also in the read-out below the buttons.
