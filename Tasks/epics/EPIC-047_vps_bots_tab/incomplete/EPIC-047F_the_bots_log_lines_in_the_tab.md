# EPIC-047F — The selected VPS bot's own log lines appear in the tab, read-only

**Status:** 🟡 In review (2026-11-25) — built and proved on the composed pieces and the real bridge session; the run on the owner's VPS is pending (check 17 of the runbook's §14.6, once PR #760 is merged)
**Source:** the owner's delegation of 2026-10-24, settled as G4: the host's log lines in the tab, read-only, only the selected bot's own events, in a later child. The owner's pain is charter §1.3 (the BUG-268 investigation needed `tar`, `scp` and an upload).
**Risk:** 🟢 — read-only; a bot's lines may contain figures, so the filter must not let another bot's or the host's lines in.
**Complexity:** M — a log source on the host side of the bridge, a stream on the link, and the existing `BotLogFeed` surface on the desktop.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047E](EPIC-047E_the_vps_bots_tab.md)

---

## 1. Context and problem
The Bots tab shows a bot's events through `BotLogFeed`, an in-process log handler on the bus. The host writes its log to its own files, and reading a bot's lines on the VPS today needs SSH, `tar` and `scp`. De-risk R1 listed this stream as a later one ("the log lines later (G4)") beside `BotChangedEvent` and `ArmedStrategyChangedEvent` (DERISK §1.3).

## 2. Acceptance criteria
Evidence is the pull request's head and its runs; "owner step" means not run on a real machine.
- [x] **Selecting a VPS bot shows its own log lines in the Bots tab's own panel, newest last, with the age of the last line.** `RemoteBotLogFeed` feeds the same `BotsViewModel.append_log_line` and `BotLogPanel`; the age is the model's `log_note` ("the host's last line is N min old", by the minute so the panel is not redrawn under the reader). *Evidence:* `test_the_vps_tab_log_follows_the_selected_bot.py`.
- [x] **Only the selected bot's lines cross the link, filtered on the host side by bot id** (the file is per bot; the bridge validates the id; a test with two bots in one host log). *Evidence:* `test_bot_log_files.py::test_two_bots_in_one_host_never_share_a_file_or_a_read`, `test_the_hosts_bot_log_is_written_and_read.py` (real logging, real thread, two bots), `test_the_bot_log_comes_from_the_host_over_the_bridge.py` (real bridge session), `test_an_unsafe_id_never_reaches_a_path_and_reads_as_empty`.
- [x] **Read-only; nothing in the panel sends a command.** The feed's only dependency is `IVpsTab.bot_log`, a read; the bridge call opens a file read-only and writes nothing (`test_the_reader_writes_nothing_and_a_missing_file_is_an_empty_page`).
- [x] **Bounded** per line (`MAX_LINE_CHARS`), per bot (`MAX_LINES_PER_BOT`, `MAX_BYTES_PER_BOT`), across bots (`MAX_BYTES_ALL_BOTS`), per call (`MAX_LINES_PER_READ`, `MAX_BYTES_PER_READ`) and in time (one ask per `POLL_MS`, so at most about 100 lines a second). A slow desktop holds nothing on the bridge: there is no stream, the ring simply overwrites its oldest lines. One test per bound in `test_bot_log_files.py`.
- [x] **Switching bots stops asking for the old one; the bridge holds nothing after the tab closes or the link drops.** There is no stream: each ask is one call; a late answer for another bot is dropped, and `close()` stops the timer (`test_a_late_answer_for_a_bot_no_longer_selected_is_dropped`, `test_a_closed_feed_asks_nothing_more_and_the_timer_stops`, `test_the_call_holds_no_stream_nothing_arrives_after_the_answer`).
- [x] **A line contains no key or secret.** `logging-rule.md` does not forbid a secret in a line, so the host drops a matching line whole (`bot_log_secret_filter.py`): shapes for an assignment to a secret-like name, a bearer token, a webhook URL, a long token and a PEM block, each proved alone by a mutation test (`test_bot_log_secret_filter.py`: remove one shape and its sample gets through).
- [ ] **Owner step:** on the real VPS the panel shows a running bot's lines with the files `0600` and no key in them (runbook §14.6 row 17). Not run.

## 3. Design
**Decided with the coordinator (2026-11-02) because the task assumed a file that does not exist:** the host writes no log file (`LOGGING.md` §1), so the bridge cannot "read the host's log from its files". The host writes a bounded per-bot file for the purpose (`state/bot-logs/<id>.jsonl`, next to `host-facts.json`) from an `App.Bots` handler through a bounded queue and one writer thread, and the bridge gets one read-only call, `bot_log(bot_id, since)`. The conditions the coordinator set, and where each is held:

| Condition | Held by |
| :--- | :--- |
| 1. The handler never blocks or raises into a bot's thread; a full queue drops and counts; a writer error is swallowed with one throttled WARNING | `BotLogHandler.emit` (`put_nowait`, one `try`), `BotLogWriter._fault`; tests in `test_bot_log_recorder.py` (each killed by a mutation) |
| 2. No recursion | the handler ignores records of `App.Operations.BotLog`, the only logger the recorder and writer use; the writer's logs also go to `App.Operations.*`, not `App.Bots` |
| 3. Files `0600`, bounded per bot in bytes and lines and across bots | `BotLogFiles`; one test per bound |
| 4. Secret filter, key shapes, drop the whole line, tested with mutation | `SECRET_SHAPES`; `test_bot_log_secret_filter.py` |
| 5. The call is read-only and bounded | `serve_bot_log`, `BotLogFileReader` |
| 6. The runbook says where the files are | `headless_runbook.md` §8b table row; `LOGGING.md` §1 |
| 7. No setting the owner must set | the recorder is on by default because 1 to 5 hold; `operations.vps_log_enabled` can turn it off, `operations.vps_feed_enabled` (the GUI's) turns it off with the feed |

The cursor is a time in nanoseconds the host stamps on each record, strictly increasing, so a restart or a rewritten file never reuses one. The desktop polls the **selected** bot every `POLL_MS` (2 s) on the app's pool, one read at a time, and shows the lines through the Bots tab's own model and panel; `BotsBackend.log_feed` is the one new seam (the Bots tab's default is the unchanged `BotLogFeed`).

## 3a. Reuse
`BotLogFeed` and the Bots tab's log panel: `used`. The logging namespaces and tags of `logging-rule.md` decide the filter: `used`.

## 4. Changes, per file
The new files are `operations/contracts/bot_log.py` (+ `i_bot_log_sink.py`, `i_bot_log_reader.py`), `operations/application/bot_log_recorder.py`, `bot_log_secret_filter.py`, `operations/adapters/bot_log_files.py`, `bridge_bot_log_view.py`, `operations/composition/bot_log_host.py`, `support/wire/bridge/bridge_bot_log_call.py`, `bridge_ports.py` (`SessionPorts` moved out of `bridge_session.py`, which was at the 400-line ceiling), `support/wire/contracts/i_bridge_bot_log.py`, `modules/bots/contracts/bot_log_chunk.py`, `shell/vps_link/host_bot_log.py`, `bots/ui/bots_screen/remote_bot_log_feed.py`, `i_bot_log_feed.py`; changed: the bridge session and its main, `operations/link.py`, `IVpsTab` and its shell implementation, `BotsBackend`, the Bots presenter (one line each), the view model and log panel (a `log_note`, empty in the Bots tab), `VpsFeedSettings`, `config_keys.py` and `app_config.json` (`operations.vps_log_enabled`).

## 5. Testing
Unit and integration on the real handler, thread, files and bridge session; mutation checks run on 20 mechanisms (each killed, after two redundant guards were reduced to one). The full gate is GitHub Actions' run on the PR head. Not run: the VPS.

## 6. Docs touched
`Docs/MODULES/bots/07-deployment.md` (a section with the sequence), `Docs/OPERATIONS/LOGGING.md`, `Docs/OPERATIONS/headless_runbook.md` (§8b row).

## Implementation notes (written when done)
- **Not changed from the coordinator's design:** every condition held; none had to be weakened.
- **Review round 1 (PR #762) changed four things.** (1) The secret scan covers the **whole** message, then the line is cut (a key straddling the cut had left a prefix); to keep the work on the bot's thread bounded, a message longer than `MAX_MESSAGE_CHARS` (4 × the line bound) is dropped whole and unscanned, and the webhook shape is bounded (`\S{0,200}`), because the first fix made the scan quadratic on a long run of `http://` (200 KB took 103 s on the reviewer's probe). (2) The sequence number is given by the writer thread, not the handler: two bot threads could enqueue 6 before 5 and the cursor then repeated or skipped a line. (3) A file with junk counts against the byte bound by its real size and is compacted, a torn last line is closed before the next record, and a file is read from its last `4 × MAX_BYTES_PER_BOT` bytes only. (4) The filter is ASCII-only (a key written with a zero-width character inside it passes): accepted, noted in its docstring.
- **A secret filter that leans to drop.** It also drops a harmless line with a 32-character run of letters, digits, `-` or `_` or a `token:` label; the lines a bot writes today carry six-character bot ids and `SEW-xxxxxx-` order ids, which pass (a test holds the samples). A false drop costs one line in a view.
- **A gap.** `Bot <id> chart: …` lines of the chart host (`bot_chart_host.py`) do not match `Bot <id>: ` and are not kept; the Bots tab shows them, the VPS tab does not. Not needed on a host (it has no chart).
- **Owner step (pending):** runbook §14.6 row 17 (merged in #760 and #761); and one look at the `sew` account's read of `state/bot-logs/` (it owns them).
