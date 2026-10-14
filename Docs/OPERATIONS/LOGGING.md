Status: Current

# Logging for an unattended run

The log guide of the headless operation (`EPIC-038`, task `038G`). The runbook ([`headless_runbook.md`](headless_runbook.md), `EPIC-038H`) links here for log placement, rotation and the health line. Design: [`DESIGN_2026-10-09_headless_operation.md` §6, §12](../../Tasks/epics/EPIC-038_headless_operation/DESIGN_2026-10-09_headless_operation.md) · evidence: [`RESEARCH` §9](../../Tasks/epics/EPIC-038_headless_operation/RESEARCH_2026-10-09_headless_operation.md) · decision: O7.

## 1. Where the log goes

The application writes every record to **standard output** (`log.console.enabled`, on in `app_config.json`) and to no file. The supervisor owns the stream:

| Platform | Who captures stdout | Who bounds it |
| :--- | :--- | :--- |
| Linux, systemd | the journal | journald (`SystemMaxUse=`, `journalctl --vacuum-time`) |
| Windows, NSSM | the wrapper's captured output | NSSM rotation (`AppRotateFiles`, `AppRotateBytes`, `AppRotateOnline`) |

A command whose stdout carries a machine-readable report (`--json`, `--format <name>`) writes its log to **standard error** instead, so the report stays one document and the log is still kept (`EPIC-038D`; `src/shell/console_log_stream.py`). `run` takes no such flag: its stdout is the log.

A service unit or wrapper therefore sets **no `log.file`** and passes neither `--dev` nor `--debug`: both write a full session log to `<data root>/logs/` (`logging-rule.md` §7), which is right for a developer reproducing a bug and wrong for a process that runs for months.

## 2. If you set `log.file` anyway

**`log.file` grows without bound**: the Engine's file handler is a plain `logging.FileHandler` with no rotation and no size cap, until the Engine gains rotation (decision O7: a separate Engine proposal, not part of this epic). A full disk stops the database write, not the network call, so its symptoms are strange.

Until then, rotate the file from outside. The handler keeps its file open, so `copytruncate` is required; without it the application keeps writing to the rotated file:

```text
/var/log/sew/sew.log {
    daily
    rotate 14
    maxsize 50M
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

`copytruncate` can lose the few records written between the copy and the truncate. That is the price of not having rotation in the application.

## 3. Record format

Every record is `%(asctime)s - %(name)s - %(levelname)s - %(message)s`. The order and the ` - ` separator are fixed: the CI run-log scan reads `- (WARNING|ERROR|CRITICAL) -`, and so should an operator's filter:

```bash
# The unit name is the one deploy/linux/sew-run.service ships.
journalctl -u sew-run -o cat | grep -E ' - (WARNING|ERROR|CRITICAL) - '
```

JSON logging would be a formatter the Engine owns. It is recorded, not built.

## 4. The health line

The `run` host (`EPIC-038D`) writes one INFO record per health interval (`--health-interval`, default 60 s) and one at each state change it makes (`SERVING`, `DRAINING`), through `log_health_line` in `src/modules/operations/application/health_line.py`, the only writer:

```text
[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0,recovering:0,error:0,starting:0,stopping:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310
```

| Key | Value | Unknown |
| :--- | :--- | :--- |
| `state` | `BOOTING`, `SERVING`, `DRAINING`, `STOPPED` or `FAILED` | n/a |
| `up` | whole seconds since boot, suffixed `s` | n/a |
| `bots` | `running`, `paused`, `halted`, `recovering`, `error`, `starting` and `stopping` counts, zeros included, in that order (the last three were added by `BUG-209`: a bot in ERROR was invisible here); `none` when the bots' section did not answer | n/a |
| `tick_age_s` | whole seconds since the last market tick (the freshest open feed) | `na` |
| `stream_down_s` | whole seconds the worst user-data stream has been out of `connected`; `0` when every stream is connected | `na` when none has reported |
| `skew_ms` | signed milliseconds, local clock minus the exchange's, as the host's probe last measured it (it asks the exchange its time before each snapshot); the venue furthest from zero when several are in use | `na` until the first measurement, and after one that found nothing |
| `rss_mb` | resident memory, whole megabytes | `na` |

Stability: a key is added at the end and never renamed or reordered, and the parser (`parse_health_line`) ignores keys it does not know, so an older monitor survives a newer host. The line holds counts, ages and names only, never free text, so a credential cannot reach it.

**The level is always INFO.** A stale feed is a large `tick_age_s`, not a WARNING, and a bot in ERROR is `error:1` here as well as an ERROR record of its own; the escalation to a person is the alert source's job (`EPIC-036`). A health line that logged WARNING would also trip the CI run-log scan on every quiet-but-healthy run.

Progress, not liveness: the process being alive proves nothing about the bots, so a monitor alerts when the line stops appearing or when `tick_age_s`/`stream_down_s` grow past its threshold.

## 5. Known gaps and sources of volume (`EPIC-038C`)
- **The Engine's dispatcher line is off outside developer mode** (`BOT-178`, 2026-10-14; it replaces the 2026-10-13 decision to accept it). The Engine logs `Executing query: <name>` at INFO for every dispatch (`kernel/dispatcher.py`), on the shared `App` logger, which a dispatcher has no way to change on its own. Polling made it the loudest line of a normal run: the bots status report and list every 10 s in the desktop, two per health interval in `run`. The app now drops that one record unless `dev.mode` is on (`--dev`, `--debug` or the file's switch), through a filter on the `App` logger installed by `create_app` (`src/shell/dispatch_log_filter.py`). Only the INFO query line is matched: the command line (`Executing command: <name>`, INFO), a failed dispatch (`<name> failed`, ERROR) and the dispatcher's payload and completion lines (DEBUG) keep their levels, so a failing run's queries still show. `run` takes no `--dev`; a developer turns the line on for it with `dev.mode` in the configuration file. The Engine-side fix (log the query at DEBUG) is a proposed patch in `BOT-178`; when the Engine ships it the filter is deleted. `test_query_dispatch_is_quiet_outside_dev_mode.py` proves both modes on the real dispatcher.
- **`stream_down_s` replaces `stream_age_s`** (`EPIC-038D`). The user-data stream publishes state *changes*, not each message, so "seconds since the last user-stream message" never existed. The field was renamed before any monitor parsed it, and is fed from the snapshot's `trading.stream_down_s`.
- **`tick_age_s` is the freshest feed.** In the snapshot `market_data.tick_age_s` is the age of the *most recent* candle across every open feed, so one dead symbol hides behind any live one, and a feed closed on purpose is never forgotten. The per-feed ages are published (`market_data.feeds`); a monitor that cares about one symbol reads those.

## 6. What `run` writes, by tag (`EPIC-038D`, `BUG-209`)

Everything on standard output, one record per line, in the format of §3. The tags are stable and greppable.

| Tag | Level | Meaning |
| :--- | :--- | :--- |
| `[run]` | INFO | the options in effect: stop policy, timeouts, pre-flight enforced or skipped, host signal |
| `[preflight]` | INFO / WARNING / ERROR | the checks that ran; each non-passing finding with its remedy; the `--skip-preflight` override (WARNING) |
| `[host]` | INFO | each state change (`BOOTING -> SERVING`, `SERVING -> DRAINING`, `DRAINING -> STOPPED`), each start-up step, the stop policy and how it ended; WARNING when the policy was given up on (timeout or second signal) and the bots it left |
| `[alerts]` | WARNING | no alert channel carries bot events (until `EPIC-036B`); the one WARNING a healthy `run` writes at start |
| `[recovering]` | WARNING | one per bot left RECOVERING after the restart, and whose move it is (decision O2) |
| `[resume-recovering]`, `[start-planned]` | INFO / WARNING | what `--resume-recovering` and `--start-planned` did, venue by venue and bot by bot; `[start-planned]` also says when the applied plan wants no bot running |
| `[plan]` (`App.Bots.Plan`) | INFO | one line per `bot apply`: how many entries were created, edited, deleted, left or blocked (`EPIC-038I`) |
| `[stop-policy]` | INFO / WARNING | `leave-orders`: each bot left and its orders resting; `stop-bots`: each stop requested and confirmed, and each stop refused |
| `[signals]` | INFO | which signals ask the host to stop |
| `[health]` | INFO | the health line (§4); WARNING `probe <name> failed` once per streak when the clock probe cannot ask the exchange |
| `[bot-transition]` (`App.Bots.GridExecutor`) | INFO / WARNING / ERROR | every bot lifecycle transition, with the reason: **WARNING when the bot lands in HALTED, ERROR when it lands in ERROR**, INFO for every other state (`BotRunState.transition`, the one place a transition is applied; `BUG-209`) |
| `[bot-transition-refused]` | WARNING | an event (a halt, a fault) the lifecycle table does not declare in the bot's state: the bot stays where it was, the reason is kept on its record |
| `[missed-fill]`, `[missed-end]` | WARNING | a reconcile applied from history a fill, or an order end, that the stream never delivered; one per order, never per tick |
| `[refresh-failed]`, `[refresh-recovered]` | WARNING / INFO | the positions and holdings reads (and, with their own wording, the account summary): one WARNING at the first failure of a streak, DEBUG for the rest of it, one INFO at the first success after it |
| `[clock-skew]` | WARNING / ERROR / INFO | the clock probe's change of level, with the pre-flight's thresholds: WARNING above 500 ms, ERROR at 1000 ms, INFO `[clock-skew-recovered]` when back within 500 ms; once per venue and level, not per interval |
| `[kline-stream]` (`App.LiveStream`) | ERROR | the market stream failed with an exception, or the library reported `{"e": "error"}`; the stream reconnects after 5 s |
| `[health-snapshot]` | INFO / ERROR | where the snapshot is written and how often; ERROR when a write fails |
| `[log-filter]` (`App.LogFilter`) | INFO | once at start: `dispatcher query lines hidden (dev.mode off)` or `shown (dev.mode on)`, the decision of §5's filter (`BOT-178`) |

## 7. What the levels mean for a bot (`BUG-209`)

An unattended run is judged by the grep of §3 and by the `[health]` line, so the levels are chosen for that reading (`logging-rule.md` §6):

| Level | A bot or a feed, in an unattended run |
| :--- | :--- |
| INFO | a decision or a transition into a state that trades or waits (STARTING, RUNNING, PAUSED, RECOVERING, STOPPING, STOPPED) |
| WARNING | degraded but recovered, or stopped by a rule rather than a fault: a bot in HALTED, a refused transition, a fill the stream lost, the first failure of a read, a clock above 500 ms |
| ERROR | an operation failed: a bot in ERROR, a clock at 1000 ms, a market stream that failed |
| CRITICAL | the process is compromised (none of the above) |

A HALTED bot is **not** an error of the process: the pre-send refusals of our own (the safety gate, the limits, the session lease, the minimum notional) and a reconcile that finds the exchange holding more than the bot bought end there, and the WARNING carries the gate or the reason. The ERROR a failing step writes with its traceback is a second record about the same event, not a duplicate: the transition says where the bot went, the step says why.
