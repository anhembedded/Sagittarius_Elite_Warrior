# BUG-193 — The bot's Plan still says "no Spot credentials configured" after the key is accepted again

- **Reported:** 2026-10-09 (the owner, in chat, with a screenshot and the app log)
- **Severity:** 🟡 P2 — Start stays blocked for a valid key, and the text sends the owner to check permissions that are fine
- **Status:** Open
- **Board:** The Bots Plan keeps a "no Spot credentials configured" verdict from a moment the mainnet key was refused, while the header already says Connected; the text also misnames an exchange refusal as a missing key.
- **Context:** SPEC-014 (run a grid bot) → `src/modules/bots/` (Plan readiness, Bots screen) and `src/modules/trading/` (mainnet key gate, Spot commission reader)
- **Environment:** Linux (Wayland), the owner's desktop, master-warrior around `ed9bf34`, Spot Mainnet key in the OS keyring, IP whitelist `103.199.56.160`.

## Reproduction
1. Bot `Test_Real_Cash` (`vce9z8`) on Spot Mainnet; the key works (10:05:08 open orders and prices read).
2. On Binance, edit the key's IP restriction; for a short time the exchange refuses the key (`-2015`).
3. During that window, press Save bot (10:07:09).
4. Fix or wait out the refusal; the header turns to "Spot Mainnet: Connected · 35.77 USDT available · key can trade".

Expected: the Plan is judged again and Start is allowed. Actual: the Plan keeps "Start is still blocked: 1 thing left: The plan cannot be judged: ETHUSDT on Spot Mainnet: ETHUSDT: no Spot credentials configured". Frequency: seen once; not yet reproduced by a session.

## Symptom
Log:
```
10:07:09,125 App.Bots.Screen - Bots screen: Save Test_Real_Cash
10:07:09,475 App.TradingAdapter - Spot Mainnet connection check rejected: Binance code -2015 -> KEY_REJECTED [connection-failure]
10:07:09,483 App.Shell.Notifier - Background failure, shown in the 'bots' message bar: bots.connect.spot_mainnet
```
Screenshot (owner, after the IP was confirmed `103.199.56.160` with `curl -4 https://api.ipify.org`): the header reads Connected / key can trade; the Plan pane and the left Bots note read "no Spot credentials configured". The key's API restrictions show Enable Reading and Enable Spot & Margin & Stock Trading ticked, Withdrawals off.

## Root cause
Not yet established. Observations from reading the code (not verified at runtime):
- `src/modules/trading/composition/venue_assembly.py:254` — every mainnet adapter resolves `order_credentials`, which is `KeyGatedCredentials`; `key_gated_credentials.py` returns "no credentials" whenever `ApiRestrictionsKeyGate.check()` refuses, and a refusal is not remembered (`api_restrictions_key_gate`: "a refusal is never remembered").
- `src/modules/trading/adapters/binance/spot/spot_commission_rate_reader.py:70` then raises `"{symbol}: no Spot credentials configured"` — the same text for "no key stored" and "the exchange refused the key", which is wrong for the second case (truthful-UI rule).
- Suspected: the Plan readiness verdict computed during the refusal is not re-judged when the venue connection recovers (the header updates, the Plan does not). Which event the Plan listens to, and whether a key-gate recovery publishes one, is not yet traced.

## Fix
None yet (owner: file only, do not fix now).

## Regression test
Not written. Candidates: a refusal then an acceptance of the key gate re-judges the Plan without a user action; the commission reader names a refused key differently from a missing one.

## Verification
Not run.

## Suggested next steps
1. Trace what the Plan readiness subscribes to and whether the Connected header and the Plan read the same source; make a recovered connection re-judge the Plan.
2. Let the key gate's refusal reach the reader as a named reason (refused by the exchange, with the `-2015` guidance on IP whitelist), not as "no credentials configured"; check the other mainnet readers that share `order_credentials` for the same wording.
3. Workaround for the owner meanwhile: select another bot and back, or press Save bot again, once the header says Connected.
