# EPIC-027G — Spot Testnet exists as a trading venue, with its own keys and honest alignment states

**Status:** ✅ Done (2026-09-27)
**Source:** the user, 2026-09-26: *"tui muốn giao dịch spot"* ("I want to trade spot").
**Risk:** 🟡 — the venue enum gates order submission; a wrong gate could route a Spot order to Futures, or the reverse.
**Complexity:** M — enum member, credentials, alignment states, Settings, gate checks.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027F](EPIC-027F_venue_selected_trading_client_factory.md). ADR D8 accepted.

---

## 1. Context and problem
- `TradingVenue` has exactly `DISABLED` and `FUTURES_TESTNET`
  (`src/support/binance_gateway/contracts/trading_venue.py:14-15`).
- Three gates compare `is not TradingVenue.FUTURES_TESTNET` literally:
  `execute_order/handler.py:192`, `cancel_order/handler.py:93`, `enable_trading/handler.py:100`.
  A new member would be refused everywhere.
- Credentials are venue-scoped: `BINANCE_FUTURES_TESTNET_API_KEY/_SECRET`
  (`env_first_credentials_provider.py:23-24`). Spot Testnet keys are a separate key set issued at
  `testnet.binance.vision`.
- `compute_venue_alignment` knows testnet versus mainnet only (`venue_alignment.py:74-89`). A Futures
  chart with Spot orders would be reported as aligned.
- The account reader hard-codes `venue=TradingVenue.FUTURES_TESTNET` (`futures_account_reader.py:194`).

## 2. Acceptance criteria
- [x] `TradingVenue.SPOT_TESTNET` exists with a `market_type` of `SPOT`. `FUTURES_TESTNET` reports
      `FUTURES_USD_M`. (`trading_venue.py`; `test_trading_venue.py`)
- [x] Spot Testnet keys are read from `BINANCE_SPOT_TESTNET_API_KEY/_SECRET` only. A Futures key can
      never be read as a Spot key, and a test proves it. (`env_first_credentials_provider.py`;
      `test_env_first_credentials_provider.py::test_a_futures_testnet_env_var_never_resolves_for_spot_testnet`)
- [x] The three gates ask "is this a supported trading venue", not "is this Futures Testnet".
      Superseded by a constitutional decision after independent review (see Implementation notes):
      the gates now ask `TradingVenue.supports_order_submission` — a named, single-source capability
      that is `False` for both `DISABLED` and `SPOT_TESTNET` today, `True` only for `FUTURES_TESTNET`,
      until `EPIC-027K` flips it. (`execute_order`/`cancel_order`/`enable_trading` handlers;
      `TradingModule._bind_trading_client_if_enabled`; a `SPOT_TESTNET`-still-refused test in each
      handler's suite and in `test_module_trading_client_binding.py`)
- [x] Venue alignment reports a market mismatch (chart market ≠ trading market) as its own state. The
      environment banner shows it. (`VenueAlignment.MARKET_MISMATCH`; `compute_venue_alignment` takes
      a `chart_market_type` parameter; `environment_banner_content.py`'s new `DANGER`-tier entry)
- [x] Settings offers Spot Testnet with a label that says what it is. The restart requirement is
      unchanged (`BOT-125`). (`trading_settings_view.py`'s `_TRADING_VENUE_LABELS`; existing
      `test_every_trading_venue_has_a_combo_label` covers it generically)

## 3. Design
- A closed enum member, not a flag (`EPIC-021` ADR §3; ADR D8 here). Mainnet Spot is **not** added.
  It enters later as its own reviewed member through `EPIC-026`'s gates (ADR O5).
- `market_type` is a property of the venue, so every downstream consumer (factory, metadata,
  strategy gate, UI) derives the market from one place.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/binance_gateway/contracts/trading_venue.py` | `SPOT_TESTNET`, `market_type` property |
| `src/support/binance_gateway/.../env_first_credentials_provider.py` | Spot Testnet key names |
| `.../venue_alignment.py`, environment banner | market-mismatch state |
| the three handlers above | capability check instead of equality |
| `src/modules/trading/ui/settings/trading_settings_view.py` | the new option and its label |

## 5. Testing
- Unit: enum → market; credential isolation; gates for every member; alignment matrix.
- Sanity: boot with each venue value.
- Ran: `.venv/bin/ruff check`/`format --check` (clean), `mypy` (diffed byte-for-byte against a
  clean-cache baseline run on the pre-change tree — identical 631 pre-existing errors, only line
  numbers shifted; zero new errors), `pytest tests/unit/architecture -q` (451 passed, including the
  god-file ratchet after trimming `app_bootstrapper.py`'s comment to stay at 548/550 lines),
  `pytest tests/unit/modules/trading -q` (797 passed), the touched
  `tests/unit/support/binance_gateway/`, `tests/unit/support/ui_kit/environment_banner/`,
  `tests/unit/modules/trading/ui/settings/`, `test_environment_banner_all_screens.py`,
  `test_credentials_never_reach_a_git_tracked_file.py`, `test_module_trading_client_binding.py`
  (120 passed). Full `tests/unit`: 5638 passed, 0 failed (9m20s) — no regression anywhere in the
  tree from the `IExchangeCredentialsProvider` composition-root change. `tests/sanity` and
  `tests/integration` not run for this change (author's fast-tier scope, `ci-rule.md` §1); GitHub
  Actions' `-Full` run is the authority for those.

## Implementation notes (written when done)
- `IExchangeCredentialsProvider`'s composition-root binding
  (`adapter_bindings.py`) had to become a lazy factory (`c.resolve(TradingVenue)`), since it now
  needs the resolved venue and `register()` may not `resolve()` — the same constraint `EPIC-027F`
  hit for `ITradingClient`. Its three former consumers (`ITradingClientFactory`, `ITradingAccountReader`,
  `IUserDataStream`) were converted from closing over a plain `credentials_provider` local to
  resolving the port themselves; not listed in this task's own file table but a direct, necessary
  consequence of making the provider itself lazy.
- `compute_venue_alignment` gained a third parameter, `chart_market_type: MarketType`, rather than a
  hidden module constant — `app_bootstrapper.py`'s one call site passes `MarketType.SPOT`, naming the
  same fact the live Trading/Dashboard screens already hard-code for their own charts/streams
  (`chart_coordinator.py`, `stream_lifecycle_controller.py`, `presenter_factory_core.py`). Priority
  when both the mainnet-data trap and a market mismatch hold: the mainnet trap wins (already the
  named worst case).
- **Interaction with `EPIC-026P`** (not yet started): that task's own context section says
  `compute_venue_alignment()` is "where the fourth state goes" for its own `ALIGNED_MAINNET` member.
  This task took that slot for `MARKET_MISMATCH` instead, since it was the state this task's own
  acceptance criteria required now. When `EPIC-026P` is picked up, its state becomes the *fifth*
  state, not the fourth — its own task file's line references and phrasing will need a small update
  at that time.
- `DISABLED.market_type` returns `None` (no fabricated default) — a market comparison for a venue
  with no market is meaningless, so `EnvFirstCredentialsProvider` also has no env-var pair for
  `DISABLED` and degrades to the (venue-agnostic) file fallback rather than crashing.

### Post-review correction (2026-09-27) — the gate/`ITradingClient` bind design changed

The independent reviewer (`ONBOARDING.md` §7) found a BLOCKING defect in the first version of this
PR: the literal `is TradingVenue.DISABLED` gate let `SPOT_TESTNET` clear the three order-path gates,
but `ITradingAccountReader`/`ITradingClientFactory`/`IUserDataStream` (`adapter_bindings.py`) and the
`ITradingClient` conditional bind (`TradingModule._bind_trading_client_if_enabled`) all still resolve
Futures-only adapters unconditionally — so `EnableTradingCommandHandler.execute()` would call
`FuturesAccountReader.check_connection()`, signing a **Futures Testnet** request with **Spot
Testnet** credentials, instead of failing loudly and correctly.

Put to the user, who deferred to `.claude/CONSTITUTION.md`'s invariants (P1 Poka-yoke — mechanical
barriers, never human vigilance; P6 — fix the mechanism generally, not a local patch scattered across
adapters; P7 — build the seam now, defer the variant). Decision: add
`TradingVenue.supports_order_submission`, a named capability property (`True` only for
`FUTURES_TESTNET` today) that the three gates and the `ITradingClient` bind now consult instead of a
literal venue comparison. This closes the defect with one mechanical barrier — `SPOT_TESTNET` is
refused at the same gate `DISABLED` already goes through, and `test_module_trading_client_binding.py`
proves `ITradingClient` stays unbound for it — while keeping the "one place" property this task's
original acceptance criterion #3 was written to achieve: `EPIC-027K` flips one `return` in
`supports_order_submission` when Spot's real order path lands, not three handler files again.
Superseding acceptance criterion #3's literal wording ("DISABLED is still refused everywhere") is a
deliberate, recorded deviation, not an oversight — `SPOT_TESTNET`'s own credentials/market_type/
alignment work from the rest of this task is unaffected and unchanged.

Also fixed from the same review: two "should fix" findings — the three new gate tests now assert the
strong `blocked_by is TRADING_VENUE_DISABLED` (matching every sibling test in those files) instead of
a weaker `is not`; `app_bootstrapper.py`'s trimmed banner comment was restored to keep its dropped
"goes back to one registration when the last `PageShell` is gone in Phase 4" retirement condition
(`architecture-rule.md` §7.3), re-tightened to fit the same 548/550-line budget. The reviewer's
[Question] (GitHub Actions' `ci-local.ps1 -Full` conclusion, which their environment could not check)
is answered: green on the PR's post-review head (`cb542973`).

Final verification on `cb542973`: `ruff` clean; `mypy` diffed byte-for-byte against the clean-cache
baseline — still 631 pre-existing errors, zero new; `tests/unit/architecture` 451 passed;
`tests/unit/modules/trading` 798 passed; full `tests/unit` 5640 passed, 0 failed (9m55s — +2 over the
pre-fix run's 5638 from the two new tests, `supports_order_submission`'s own unit test and
`test_module_trading_client_binding.py`'s `SPOT_TESTNET`-stays-unbound case). GitHub Actions'
`ci-local.ps1 -Full` check run: success. PR #281 moved out of draft; merge awaits the user's own
action per `ONBOARDING.md` §7 (author never merges own code).
