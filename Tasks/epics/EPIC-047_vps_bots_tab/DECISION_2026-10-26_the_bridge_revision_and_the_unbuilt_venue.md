# ADR — The bridge numbers a bot's changes itself, the facts file shows an unbuilt venue's key state, and exchange facts stay as fresh as the last read

**Epic:** [EPIC-047](README.md)
**Date:** 2026-10-26
**Status:** Accepted
**Decided by:** D1 by the author of [EPIC-047C](completed/EPIC-047C_the_bridge_behind_a_forced_command.md), which [EPIC-047A](completed/EPIC-047A_the_wire_codec_and_the_version_handshake.md) handed it; D2 and D3 by the coordinating session under ONBOARDING §7 ("Settle an owner decision that carries a recommendation"), handed to the author in its brief of 2026-10-26. The owner may veto any row; a veto reverts it. The Constitution check is §2a.
**Supersedes / superseded by (optional):** none. Read with [the 2026-10-27 record](DECISION_2026-10-27_a_vps_bot_reaches_binance_only_through_the_vps.md), whose D4 replaces D3 here once the owner accepts it, and with [the remote link record](DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D4 and D5.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree, cited by path and symbol |
| 🤖 Default, owner may veto | an owner question settled on its recommendation under ONBOARDING §7: its Constitution check shows every invariant passes; reverted if the owner vetoes |
| 🤖 Agent decision | decided by the author under ONBOARDING §7: a named pattern, broad precedent |

## 1. Context

- ✅ A receiver applies a bot's record only when its revision is greater (`src/support/wire/revision_gate.py` → `RevisionGate`), and the envelope carries a revision (`src/support/wire/wire_roots.py` → `WireRoots.encode`). 047A left the sender's choice open: a counter in the bot's record, or the bridge's own sequence per bot.
- ✅ The bot's file has no revision (`src/modules/bots/adapters/persistence/bot_record_codec.py` → `encode`, `SCHEMA_VERSION` 1, decoded strictly), and every writer saves through the store the real-money host owns (`src/modules/bots/application/services/lifecycle/notifying_bot_store.py` → `NotifyingBotStore.save`).
- ✅ The host-facts file listed a venue's key state and leases only for a built venue, because `IVenueContexts.get` builds a venue's adapters (047B notes; `src/modules/trading/composition/venue_contexts.py` → `VenueContexts.assembly`).
- ✅ The host reads exchange facts only at a Start, a Resume or a screen load (`src/modules/bots/adapters/recorded_venue_facts.py` → `RecordedVenueFacts`); a scheduled refresh would add REST weight on the account and IP the bots trade on, which G7a exists to avoid.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **The revision is the bridge's own counter per bot, not a field of the record.** It starts at 1 when the bridge first sees a bot file and grows by one each time the file's stamp (modification time, size, inode) changes, a deletion counted as a change. It lives for one bridge process; the desktop makes a new `RevisionGate` for each connection and takes a snapshot first (`src/support/wire/bridge/bridge_session.py` → `BridgeSession._poll`). | Accepted | 🤖 Agent decision | The bot record, its file codec, the store and the real-money host are untouched. The bridge is single-threaded for the bots, so a snapshot and the events that overtake it come from one sequence. The price: a revision means nothing across two bridges, so the desktop must not keep a gate across a reconnect (047D's task says so); a writer other than the host is invisible to a record-borne counter anyway. |
| D2 | **The facts file lists a key state for every enabled venue and a lease for every enabled venue and stored symbol.** A new non-building port, `IVenueKeyStates.key_saved` (`src/modules/trading/contracts/i_venue_key_states.py`), answers from the stored key alone; a lease on a venue nothing has built has the holder `""`, because the lease lives in the venue's session, which does not exist yet. The provider is built for each question and not kept. | Accepted | 🤖 Default, owner may veto | A New bot on an unbuilt venue knows whether a key is saved without the host building the venue. Cost: one read of the secret stores per enabled venue per look (every 2 s), cheap on the VPS (a systemd credential or a permission-checked file); a kept provider was rejected because the mainnet one keeps its first read for the life of the process and would hide a key saved later. |
| D3 | **Exchange facts stay as fresh as the last Start, Resume or screen read.** No scheduled refresh of the exchange for the facts file. | Accepted | 🤖 Default, owner may veto | No request is added on the account and IP the bots trade on. The tab shows `read_at` and says how old a fact is; a bot nobody has read since the host started has none. A bounded refresh stays a later variant behind `RecordedVenueFacts`, and is the owner's call. |

## 2a. Constitution check (D2 and D3, the defaults)

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | D2: `test_a_venue_nothing_has_built_still_shows_its_key_state_and_is_not_built_by_it` fails the test if the reader asks an unbuilt venue's context (`OnlyBuilt.get` asserts); `test_a_key_saved_after_the_first_question_is_seen_at_once` holds the "no kept provider" rule. D3: `test_recording_asks_the_inner_reader_exactly_once_per_read` (047B) holds that the file adds no exchange request. |
| P2 Verify, don't restate | ✅ | The venue and key-state facts above were read at `src/modules/trading/composition/venue_contexts.py` and `venue_assembly.py` in this branch, not recalled from 047B's notes. |
| P3 A copy drifts | ✅ | D2: `stored_credentials_provider` is the one place a venue's key is located, used by the venue assembly and by `StoredVenueKeyStates`. D1: one revision rule, the gate's. |
| P4 Green proves only what was tested | ✅ | D2 is proved at unit level with the real provider over an in-memory secret store, and the composed host's facts file is covered by 047B's integration test; a real mainnet key store is not exercised (named in the task). |
| P5 Apply before you invent | ✅ | D2 mirrors `IVenueContexts`/`IVenueTradingPorts`' shape; D1 is the revision a file-watching protocol takes from the watcher (DERISK R5), the gate being 047A's. |
| P6 Fix the mechanism | ✅ | D2 fixes the 047B gap at its mechanism (a read-only fact must not build a venue) instead of a "not read yet" label in the tab. |
| P7 Seam now, variant later | ✅ | D1: a record counter later changes the sender only, the envelope and gate stay. D3: a refresh is one decorator over `IVenueFacts`. |
| P8 Ratchets only fall | ✅ | No guard loosened, no baseline grown. `boundaries/zones.py` gains one permitted file name (`link.py`) with pinned rows in `test_boundary_rules.py`; the shell's legacy-import baseline is not touched (the probe moved to `support/instance_lock` instead of a new legacy import). |
| P9 Decide alone | ✅ | Both defaults were handed over by the coordinator with the recommendation. |
| P10 Pyramid and units | ✅ | Each row leads with the choice; the costs carry their units (2 s, one read per venue per look). |
| P11 Prompt-grade artifacts | ✅ | Each row names the symbol and the test that holds it. |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ✅ | D2 adds a read-only port and changes what a file lists; it moves no order, limit or key and adds no dependency; a veto reverts `TradingHostHeldFacts` to the built-only listing. D3 changes nothing. |

## 3. Alternatives considered

- **A counter in the bot record (D1).** Lost: it changes the stored file's codec and every writer on the real-money host, for a number only the link reads; and it still could not number a change made by a writer that does not bump it.
- **The bridge's wall-clock or the file's modification time as the revision.** Lost: equal timestamps on two writes in one tick, and a clock that steps back.
- **"Not read yet" for an unbuilt venue (D2).** Lost: it hides a fact the host can answer locally, and the tab's New bot would block on a venue the host knows is fine.
- **Build the venue to read its key (D2).** Lost: `IVenueContexts.get` builds clients and streams on the real-money host for a read.
- **A kept provider with a time-to-live (D2).** Lost: a second cache to keep right for a read the stores answer in microseconds on the VPS.
- **A scheduled exchange refresh for the facts file (D3).** Lost: REST weight on the account and IP the bots use; the owner's call.

## 4. Open questions

None.

## 5. Implementation evidence

| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | [EPIC-047C](completed/EPIC-047C_the_bridge_behind_a_forced_command.md) | Verified in unit and process tests | `tests/unit/support/wire/bridge/test_bridge_reads.py` (revisions, order-independent convergence with `RevisionGate`), `tests/integration/modules/operations/test_the_bridge_process.py` |
| D2 | [EPIC-047C](completed/EPIC-047C_the_bridge_behind_a_forced_command.md) | Verified in unit tests | `tests/unit/modules/trading/test_stored_venue_key_states.py`, `tests/unit/modules/bots/adapters/test_trading_host_held_facts.py` |
| D3 | [EPIC-047C](completed/EPIC-047C_the_bridge_behind_a_forced_command.md) | Nothing built, by decision | 047B's `RecordedVenueFacts` tests |
