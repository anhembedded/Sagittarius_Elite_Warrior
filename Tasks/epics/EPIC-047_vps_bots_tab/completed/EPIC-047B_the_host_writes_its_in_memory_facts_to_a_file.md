# EPIC-047B — The running host writes the facts only it holds to a file when they change

**Status:** ✅ Done (2026-10-27) — merged as #738 on 2026-10-27; the one criterion it narrowed (the bridge's assembly) was closed by [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md)
**Source:** the owner's delegation of 2026-10-24, settled as G7a; [the remote link record](../DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) D4; De-risk R2 §2.5.
**Risk:** 🔴 — it changes the real-money host, even though it only writes a file; a write that blocks, tears or leaks a key would be a defect on the trading host.
**Complexity:** M — one writer beside `health_snapshot.py`, four fact groups, owner-only atomic writes.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-048A](../../EPIC-048_ui_reaches_the_application_through_its_doors/completed/EPIC-048A_the_doors_rule_and_its_guard.md) and the first pull request of [EPIC-048B](../../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) (#731). 047B reads the facts that pull request already exposes (`BotRunFactsReader`, `GetBotRunFactsQuery`); its second pull request (the reads off the UI thread, the screen's remaining doors) changes nothing this file holds.

---

## 1. Context and problem
A bridge is a second process: it reads the store's files and sends commands through `DirectoryHostControl`, and it can reach nothing the running host holds in memory (DERISK §2.5). The Bots screen needs four groups of those facts: the **trading leases** (which symbol is held by which bot or by the Trade tab, the occupancy of `GetBotRunFactsQuery`), the **enabled venues**, the **budget caps** and the **exchange facts** the host already reads. Without a socket there is one honest path: the host writes them to a file, as it writes `state/health.json` every 10 s (`health_snapshot.py`, `HEALTH_INTERVAL_SECONDS`). The bridge must not call the exchange itself: it would add REST weight on the account and IP the bots use, and it would hold the host's keys.

## 2. Acceptance criteria
Evidence is the pull request's head and its runs, named on the pull request. "Not run" means not run.
- [x] The host writes one facts file when a fact changes (and at a bounded interval as a heartbeat), under `state/`, owner-only (0600) and atomically (temp file and rename), as `state/health.json` is. — `FACTS_POLL_SECONDS` = 2 and `FACTS_HEARTBEAT_SECONDS` = 15. Unit: `test_host_facts_publisher.py` (a change is written at the next look; a quiet host is rewritten only past the heartbeat; no rewrite at every look), `test_owner_only_atomic_file.py` (0600 even with an open umask and before the rename; a refused rename leaves the previous file whole). Integration on the composed app over the fake exchange: `test_host_facts_file_on_the_fake_exchange.py`.
- [x] The file carries the four fact groups, a `schema` name and a monotonic revision, and the host's clock time; a reader that finds a torn or older revision keeps the last good one. — `schema` = `sew.host-facts/1`, `revision`, `written_at`, `heartbeat_s`, `pid`; `test_json_host_facts_codec.py` (the closed list of fields), `test_host_facts_watch.py` (a torn, missing or older file keeps the last good header), `first_revision_after` (a restart, or a deleted file, never goes back).
- [x] It carries **no key, no secret and no credential**; a test reads the file for a venue that has a stored key and finds only the connection state ("a key is saved"). — Integration: the running host with a stored key (`fake-key`, `fake-secret`) and the file's bytes never hold either, and the venue says `key_saved`; unit: a planted key-like value in an exchange reason and in `earlier_runs.unavailable` never reaches the bytes, no field the file can reach is named like a secret, and every text field it can reach is on a reviewed list.
- [x] The write never blocks the trading path: a slow or full disk delays the file, not an order or a stop (a test with a blocked writer; a log line names the failure). — `test_host_facts_publishing.py`: 200 ticks return while a write, and while a read of the facts, are blocked, with one write in flight; a failed write is logged at ERROR once per cause and never raised.
- [x] The bridge's `GetBotRunFactsQuery` and `GetVenueChoicesQuery` answers (EPIC-048B) can be built from this file and the store's files alone. — **The data is there; the assembly is 047C's.** `BotRunFacts` needs the enabled venues, the lease holder of the bot's symbol and the caps: all three are in the file, with the store's files for the occupancy. `GetVenueChoicesQuery` needs each enabled venue's key state: the file has it **for a venue something has built**, and a venue nothing has used is absent (reading it would build it), so for such a venue the tab can say only "not read yet". *Closed by 047C (2026-10-26):* `IVenueKeyStates` gives an unbuilt venue its key state and a lease with no holder, and `IHostFactsCodec.decode` reads the body ([the decision record](../DECISION_2026-10-26_the_bridge_revision_and_the_unbuilt_venue.md) D2). The desktop assembles the answers from the file and the bots.
- [x] No trading behaviour changes: the host's existing tests are unchanged and green, and a run on the fake exchange places the same orders. — No existing test was edited; the bots, operations and trading unit suites and the bots and operations integration journeys (the grid and Futures journeys over the fake exchange) ran green. The tap (`RecordedVenueFacts`) asks its inner reader exactly as often as before (`test_recording_asks_the_inner_reader_exactly_once_per_read`).
- [x] The file is written on the Linux VPS profile and on the desktop host; deleting it is harmless (the host rewrites it). — Every writable copy runs `OperationsModule.boot`, as for `health.json`; the integration test deletes the file under a running host and finds it again with a higher revision. The Windows ACL case is a stated limit of the mode bits (`owner_only_atomic_file.py`) and not run here.

## 3. Design
The mechanism is the repository's own `health_snapshot.py` and its writer (P5, mirror a vetted shape): the facts are a read model of host state, written on change. Two halves, because `operations` may not depend on `trading` and `bots` already composes what is needed:

| Half | Where | What |
| :--- | :--- | :--- |
| The facts | `bots` (`contracts/host_held_facts.py` → `HostHeldFacts`; `adapters/trading_host_held_facts.py` → `TradingHostHeldFacts`) | enabled venues, key state of built venues, leases, caps and the latest exchange read per bot, from the ports the Bots screen's own reads use |
| The file | `operations` (`application/host_facts_publisher.py`, `application/host_facts_publishing.py`, `adapters/file_host_facts_sink.py`, `adapters/owner_only_atomic_file.py`) | decide when, write owner-only and atomically, off the scheduler's thread, never raise |

**The encoding is behind one seam.** The file's content is the contract types themselves (`HostHeldFacts`, with `OwnerBudgetCaps`, `TradingVenue`, `ExchangeFacts` and `FuturesFacts` as they are), and `IHostFactsCodec` is the only thing that turns them into bytes. `JsonHostFactsCodec` writes the top level by name and follows the dataclasses' own fields below an exchange snapshot; `EPIC-047A`'s reflective codec replaces it by implementing the same port, and nothing else (the file's shape, the publisher, the sink) changes. `decode_header` is all the writer's side needs; decoding the facts body is added to the port by 047C. The stored-file rule (hand-written, version-tolerant) holds: a reader that knows a header field reads it whatever else the file adds.

**Exchange facts are remembered, not fetched.** G7a says the host writes "the exchange facts it already reads". The host reads them only at a Start, a Resume or a screen load, so `RecordedVenueFacts` (a decorator on `IVenueFacts`) remembers each answer and `read_at` says how old it is. A scheduled refresh would add REST weight on the account the bots trade on, which G7a exists to avoid; it is a decision for the owner, recorded below.

**Two choices the file's reader must know.** (1) A venue nothing has built (`IVenueContexts.built`) has no key state and no lease in the file: `IVenueContexts.get` builds a venue's adapters, and a read-only fact must not build one on the real-money host. (2) A lease is listed for each symbol a stored bot is on, because `ITradingSession` cannot enumerate its leases. Both are in `Docs/MODULES/bots/07-deployment.md`.

## 3a. Reuse
Checked in `.claude/rules/capabilities.md` (it lists `src/support`, `src/core` and `src/shell` only): no atomic-write row. `used`: `FileHealthSnapshotSink`'s replace retry (`REPLACE_ATTEMPTS`, `REPLACE_STEP_S`); `HealthPublishing`'s shape (begin, tick, end, a failure logged and never raised) and its scheduler job; `IOperationsClock`; `IBotStore.load_all` and `list_bots/handler.py` → `listed` order; the ports `BotRunFactsReader` reads (`IVenueTradingPorts`, `OwnerBudgetCaps`); the credentials provider's `resolve()` as `venue_choice.py` reads it; the fakes `FakeVenueTradingPorts`, `FakeVenueContexts`, `FakeCredentialsProvider`, `FakeTradingSession`, `FakeBotStore`. `not used, with the reason`: `atomic_json_file.py` (trading's) writes `0666 & ~umask` and a `.json.tmp` name; the owner-only write needs the file created `0600`. `FileHealthSnapshotSink` and `DirectoryHostControl` each inline a write; `owner_only_atomic_file.py` is the place they converge when a second consumer adopts it (it moves to `src/support` then).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/host_held_facts.py`, `i_host_held_facts.py`, `i_latest_venue_reads.py` | the facts value, the port the file is written from, the port the remembered reads sit behind |
| `src/modules/bots/adapters/trading_host_held_facts.py`, `recorded_venue_facts.py`, `latest_venue_reads.py` | the reader of the host's facts; the decorator on `IVenueFacts`; the thread-safe memory |
| `src/modules/bots/composition/host_facts_bindings.py`, `executor_bindings.py`, `module.py` | the bindings; `_build_venue_facts` wraps its reader in the decorator |
| `src/modules/operations/contracts/host_facts_document.py`, `i_host_facts_codec.py`, `i_host_facts_sink.py`, `i_host_facts_source.py` | the file as a value, the header, the cadence constants, the three ports |
| `src/modules/operations/adapters/owner_only_atomic_file.py`, `json_host_facts_codec.py`, `file_host_facts_sink.py`, `file_host_facts_source.py` | the owner-only atomic write; the hand encoding; the file sink and header source |
| `src/modules/operations/application/host_facts_publisher.py`, `host_facts_publishing.py`, `host_facts_watch.py` | when to write; the worker thread and the once-per-cause log; the reader's last-good view |
| `src/modules/operations/module.py` | bindings, `_begin_host_facts` in `boot()`, the job cancelled in `shutdown()` |
| `src/support/log_view/template_catalogue.json` | the new log templates (`scripts/render_log_templates.py --write`) |
| `Docs/MODULES/bots/03-context.md`, `07-deployment.md`; `Docs/OPERATIONS/headless_runbook.md` | the design and the file list |

## 5. Testing
Tier: unit (45+ tests in `tests/unit/modules/operations/adapters/` and `host_facts/`, `tests/unit/modules/bots/adapters/`), integration on the composed app over the fake exchange (`tests/integration/modules/bots/test_host_facts_file_on_the_fake_exchange.py`), then the full gate on GitHub Actions. Each criterion maps to tests in section 2.

**Mutation checks, run and recorded (each reverted):**
| Mutation | Result |
| :--- | :--- |
| the file is written non-atomically (straight into the target, no temporary file, no rename) | `test_owner_only_atomic_file.py`: 7 of 7 fail, among them the refused-rename test (the previous file was already overwritten) |
| the temporary file is created `0666` instead of `0600` | 3 fail: the umask test, the mode-before-rename test and the loose-file test |
| a field named `api_key` added to a type the file reaches | `test_no_field_the_file_can_reach_is_named_like_a_secret` and `test_every_text_field_the_file_can_reach_is_known` fail |
| the change test is removed (rewrite on every look) | 3 fail: no rewrite at every look, the look just before the heartbeat, an equal fact is no change |
| `tick()` writes on the caller's thread | `test_a_blocked_write_does_not_block_the_caller_of_the_tick` fails (the write never returns) |
| the venue-facts tap is not wired | the integration test fails: "the file did not show: the exchange read" |
| `OperationsModule.boot` does not begin the facts | all four integration tests that read the file fail |
| a venue nothing built is read (`built = enabled`) | 12 of 14 reader tests fail (`IVenueContexts.get` on an unbuilt venue is a fault in the double) |
| a deleted bot's read is carried | `test_a_deleted_bots_snapshot_is_not_carried` fails |
| the decorator reads the inner reader twice | 3 fail, among them "asks the inner reader exactly once per read" |

**Not run:** the Windows ACL case; a real exchange; the bridge reading the file (047C).

## 6. Docs touched
`Docs/MODULES/bots/07-deployment.md` (the facts, the thread, the cadence, the limits) and `03-context.md` (`operations` reads `IHostHeldFacts`); `operations` has no folder under `Docs/MODULES/`, so its part is written in the bots page that already describes "a second process" and the headless host, and says so there. `Docs/OPERATIONS/headless_runbook.md` lists `state/host-facts.json` with the other state files; the bridge's setup stays in [EPIC-047G](../incomplete/EPIC-047G_the_runbook_for_the_vps_link.md).

## Implementation notes
- **Cadence.** Looked at every 2 s, written on a change or at least every 15 s. A change reaches the file within one look plus one write (the integration test allows three looks); a lease or a venue is no fill, so AC2's 5 s is not at stake. The reader calls the host dead after 3 heartbeats (45 s).
- **Revisions** grow by one a write and a start continues above the previous file's and above the clock's seconds (`first_revision_after`), so deleting the file between two runs cannot make a reader that kept the last good revision call the new host older.
- **Free text.** `ExchangeUnavailable.reason` and `EarlierRunsInventory.unavailable` are filled from exception text in the readers; the encoder never writes them (a fixed sentence stands in; the reason stays in the host's `[exchange-facts]` log). The same rule keeps exception text out of the host-facts log lines: a failure is logged by type and errno at ERROR and by text at DEBUG only.
- **Balances.** Unlike `health.json`, this file holds account balances (`ExchangeFacts`), because the Checks need them. It is `0600` and the bridge runs as the same account; it holds no credential.
- **Decisions put to the coordinator, settled in [the 2026-10-26 record](../DECISION_2026-10-26_the_bridge_revision_and_the_unbuilt_venue.md) (D2, D3):** (1) whether the tab needs the exchange facts fresher than the last Start, Resume or load: a refresh adds REST weight, so the owner's call; (2) whether New bot on a venue nothing has built needs its key state: a small port in `trading` that answers without building (recommended, in 047C's scope) or "not read yet" in the tab.
- **Not in this task:** decoding the facts body (047A's codec and 047C's reader), the bridge, and moving `owner_only_atomic_file.py` to `src/support`.
