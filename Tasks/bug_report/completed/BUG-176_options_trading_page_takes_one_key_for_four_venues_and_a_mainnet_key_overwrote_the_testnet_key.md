# BUG-176 — Tools → Options → Trading has one key field for four venues; a mainnet key pasted there overwrote the Futures Testnet key

- **Reported:** 2026-10-07 (the owner, in chat, with a screenshot of Tools → Options → Trading on master `6aa3586`: "cái ô này thì phân biệt testnet hay mainnet làm gì?")
- **Severity:** 🟡 P2 — a working key is destroyed by a normal action, and a full API key was exposed in a screenshot; no order is affected
- **Status:** ✅ Fixed (2026-10-07)
- **Board:** The page took one key pair for four venues and wrote it to the one `secrets.local.json` entry both testnets read, so a mainnet key replaced the working testnet key, and nothing probed or told which environment a key was for. The page is now one row per venue with one Add key…: an enrolment use case asks mainnet, Spot Testnet and Futures Testnet which one knows the key, refuses a key that can withdraw, and keeps it per venue (mainnet in the keyring, testnet in its own file entry), never touching another venue's key. Held by `test_a_key_added_in_options_keeps_the_other_venues_key.py` and `test_adding_a_key_against_fake_server.py`.
- **Context:** Tools → Options → Trading ([SPEC-003](../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md)) → `modules/trading/` `ui/settings/` (page), `application/credentials/` (enrolment), `adapters/binance/key_environment_probe.py`; `support/binance_gateway/adapters/` (where keys are kept)
- **Environment:** the owner's desktop, master `6aa3586`; reproduced here by a unit test (Binance egress is blocked in this sandbox)

## Reproduction
1. Futures Testnet has a working key in `secrets.local.json`.
2. Open Tools → Options → Trading, paste a mainnet key and secret, press OK.
3. **Expected:** the app works out which environment the key belongs to and keeps every other venue's key.
4. **Actual:** the pair replaces the file's only entry; Futures Testnet (and Spot Testnet, which reads the same entry) now hold the mainnet key and fail with `-2015`/`-2008`.

## Symptom
The page showed "Binance API Key (Public)" / "API Secret (Private)", "Check Connection" (Futures Testnet only), and said the app talks to the testnet only. Since EPIC-034 D11 the app has four venues; mainnet keys could only be stored with `scripts/save_mainnet_key.py` (OS keyring). The owner's screenshot showed a full key.

## Root cause
- `trading_settings_presenter.py` (master) bound the page to `IVenueContexts.primary().credentials_provider`, the Futures Testnet provider, so every key typed went to that venue whatever it was a key of; nothing probed the key.
- `secrets_file_source.py` (master) held one `API_KEY`/`API_SECRET` pair and `EnvFirstCredentialsProvider` for Futures Testnet and Spot Testnet both read it: there was not even one slot per testnet venue.
- Enrolment (probe the environment, the D5 withdrawal check, store in the right place) existed only in `scripts/save_mainnet_key.py`, outside the app.
- Family scan: the same "one pair, venue-agnostic" shape existed nowhere else (`MainnetCredentialsProvider` already keeps two names per venue); the CLI formatter, the market connection words and two code comments still claimed "this app talks to the testnet only" and were corrected.
- The gate was green while this was live: no net covered "one venue's key survives another's save". The regression tests are that net; no case study (the blind spot is closed here, not open elsewhere).

## Fix
- **One enrolment path, in the application layer.** `EnrolKeyCommandHandler` (`application/credentials/enrol_key/`) asks each `KeyEnvironment` through the `IKeyEnvironmentProbe` port (adapter `BinanceKeyEnvironmentProbe`: mainnet `apiRestrictions`, Spot Testnet account, Futures Testnet account), stops at the first that accepts, refuses a mainnet key that can withdraw (D5), keeps a mainnet key for Spot Mainnet and/or Futures Mainnet by its permissions, a testnet key for its testnet venue, and stores nothing when no environment accepts it. `RemoveKeyCommand` and `ListVenueKeysQuery` serve Remove and the rows.
- **Per-venue storage.** `SecretsFileSource` keeps one entry per venue; a pair written by the old format is read for both testnets and migrated into one entry each on the next change. `ISecretStore.delete` and `IExchangeCredentialsProvider.remove_stored` added (every implementer changed in the same commit).
- **The page** (`ui/settings/`) is one row per venue (venue, key fingerprint with its source, connection state in words, Replace/Remove) and Add key… in a dialog with two masked fields; actions run off the UI thread under `ActionOwnershipTracker`; failures go through `INotifier`.
- **`scripts/save_mainnet_key.py` and `enrol_key()` removed.** Reason: the page does the same job for every venue and the CLI could not share the use case without building a container; keeping a second front door is a second code path to keep in step. Headless machines use the venues' environment variables.
- `-2008`/`-2014` (unknown here) and `-2015` (known but refused here) are told apart by `UNKNOWN_KEY_CODES`, which lives in `connection_failure.py` beside the table (after #422 merged it there); everything else is the shared classifier's. Each environment's line on the page is `describe_failure`'s wording (the exchange's code and message, then the reason and the fixes), the same text the key gate and the Connect step use.

## Regression test
- `tests/unit/modules/trading/ui/settings/test_a_key_added_in_options_keeps_the_other_venues_key.py` and `tests/integration/infrastructure/binance/test_adding_a_key_against_fake_server.py::test_a_mainnet_key_pasted_while_a_testnet_key_exists_keeps_the_testnet_key`.
- Red on master `6aa3586` before the fix, for this reason (the same journey through the page master had: set the page's key and secret, Apply):
  ```
  presenter._settings_view_model.apiKey = <mainnet key>; presenter.apply()
  >       assert futures.resolve().credentials.api_key == "testnet-key"
  E       AssertionError: assert 'mmmmmmmmmmmm...mmmmmmmmmmmmm' == 'testnet-key'
  ```
  The test cannot keep that form (the page no longer has those fields), so it was rewritten for the page that replaced it, with a stronger assertion: every venue's key is read back after the add.

## Verification
- Commit tier `ci-local.ps1 -SkipTests`: PASS (log grepped for `FAILED|ERROR|Traceback|ResourceWarning| error:`: no hits).
- Detection over three fake Binance exchanges (mainnet, Spot Testnet, Futures Testnet): unknown everywhere (all three say unknown, nothing stored), `-2015` on mainnet (told apart from unknown), a withdrawal key refused, a Spot-only mainnet key kept for Spot Mainnet alone, both-market key kept for both, a read-only key refused, a testnet key kept for its venue alone, Replace touching one venue, an environment-variable venue not written, a locked keyring, maintenance not read as an unknown key.
- Positive proof the new mechanism ran: the probe's log line `Binance mainnet: the key A1b2…Z9y8 was accepted [key-probe]` and `<venue>: the key … was kept [key-enrolment]`, asserted on the fingerprint only (never the secret) in `test_key_environment_probe.py`.
- Not proven, and not provable from this sandbox (HTTP 451 to `*.binance.*`): the real `-2008`/`-2014`/`-2015` answers of the three real environments. The codes are written from Binance's documentation and the owner's logs (BUG-175); the owner's manual check is to add each kind of key on the real page.
