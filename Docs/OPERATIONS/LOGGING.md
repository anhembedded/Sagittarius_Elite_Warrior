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

## 1b. A command that only reads, or is short-lived, logs to a file of its own (`BOT-185`, `BOT-186`)

A command declared `"read_only": true` in `cli_commands.json` boots the whole application to print one table, and so does a short-lived writer declared `"short_lived": true` (`bot apply`): one result, then it ends. The `bot apply` result table and the mainnet confirmations (`--confirm-venue`) stay on the console; only the log records move. Its console shows that result only. Its records go to `<data root>/logs/cli-<UTC timestamp>-<pid>.log` and `--verbose` (accepted on every command, at any position) puts them on the console as `StdLogger` always did. WARNING, ERROR and CRITICAL records are also written to **standard error** in the same format, whatever the command, so a failure is visible and a `--json` document owns standard output. A command declared `"keeps_console_log": true` keeps the log on stdout as §1 says: `run` (the supervisor's), `sync` (its progress is the log), `stream start` and `stream stop`, and `trade-once` (it can place a real order with `--live` and the application keeps no local order journal, so its console log stays as it always was). Every command that is not a group of verbs must declare one side (`read_only`, `read_only_when`, `short_lived` or `keeps_console_log`), so a new command cannot be quiet or noisy by accident: `test_every_command_declares_where_its_log_goes.py` fails until it chooses.

| Why this shape | |
| :--- | :--- |
| One file per process | Several short commands run at once. Python's `RotatingFileHandler` is not safe across processes: two renames of one file lose records, and on Windows the rename raises `PermissionError` while another process holds the file, which `logging` prints to stderr. A file per process has no writer to race with. |
| Bounded by pruning | At start the command deletes the oldest `cli-*` files beyond the newest 39, then adds its own: 40 files (`FILES_KEPT`; a run that rotates is two files, so a few more while it lasts). Two commands pruning together may both delete one file (the second finds it gone) or leave a few extra until the next start. |
| Bounded per file | Each file is a `RotatingFileHandler` capped at 512 KiB with one backup (`MAX_FILE_BYTES`), single-process so race-free: 20 MiB in all, in practice about 7 KB a run. |
| Rejected: one rotating file | Cross-process rotation above. |
| Rejected: a file per day | Safe to append, but a day's size is the number of runs times 7 KB with no cap, and it needs a pruning rule of its own. |
| Rejected: `logrotate` on the file | Needs `copytruncate` and a root-owned stanza for a file an operator's own account writes. |

If `<data root>/logs` cannot be created, or its file cannot be opened (checked by opening it, since `os.access` ignores Windows ACLs) (a service account's data root seen from another user), the command still runs: it logs one WARNING `[cli-log] no log file (<reason>)` to stderr and shows warnings and errors only. A `log.file` set in the configuration is left alone and written as before, beside this file. Code: `src/shell/cli_log_routing.py`; the entry point decides in `main._quiet_log_for`.

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
[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0,recovering:0,error:0,starting:0,stopping:0,awaiting_recovery:0,awaiting_range:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310
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
| `[resume-recovering]`, `[resume-halted]`, `[start-planned]` | INFO / WARNING | what `--resume-recovering`, `--resume-halted` and `--start-planned` did, venue by venue and bot by bot; `[start-planned]` also says when the applied plan wants no bot running |
| `[plan]` (`App.Bots.Plan`) | INFO | one line per `bot apply`: how many entries were created, edited, deleted, left or blocked (`EPIC-038I`) |
| `[stop-policy]` | INFO / WARNING | `leave-orders`: each bot left and its orders resting (for a Futures bot, why: its stop covers its position, or it holds nothing), and at WARNING each Futures bot it closes before exit with the reason (`closing <id> (<state>) before exit: ...`); `stop-bots`: each stop requested and confirmed, and each stop refused |
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

## 8. Reading the log with the params coloured: `main.py logs` (`BOT-199`, [`PRO-019`](../../Tasks/proposal/PRO-019.md))

The stored record is plain and stays plain (§3). Colour is added at the screen by a viewer that reads plain lines from a pipe or a file and writes them back, and writes them **unchanged** whenever the output is not an interactive terminal, `NO_COLOR` is set (non-empty), `TERM` is `dumb`, or `--no-color`/`--color never` is given.

```bash
M="/opt/sew/.venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"   # as in the runbook
journalctl -u sew-run -o cat -f | $M logs                                       # live
journalctl -u sew-run -o cat --since today | $M logs --level warning
journalctl -u sew-run -o cat | $M logs --bot uie03d --since 2h
$M logs --file /var/lib/sew/logs/cli-<timestamp>-<pid>.log --tag reduce-only-refused
$M logs --file <log.file path> --follow --level error
journalctl -u sew-run -o cat -f | $M logs --color always | less -R              # keep colour through a pager
```

Use `-o cat`: the viewer reads the format of §3, not journald's own prefix. A `-o short` line is not a record head, so it is shown unchanged without a filter and **dropped by any filter** (`--level`, `--bot`, `--tag`, `--since` print nothing for it, and say nothing). The command builds no application and takes no lock, so it works while `run` is up and when the app cannot boot.

| Part of the line | Style (one table, `src/support/log_view/log_meaning_table.py`) |
| :--- | :--- |
| timestamp, the ` - ` separators | dim |
| logger (`App.Bots.GridExit`) | cyan |
| level | CRITICAL bold red, ERROR red, WARNING yellow, INFO default, DEBUG/TRACE dim; WARNING and above also colour the fixed text of the message |
| bracket tag (`[boot-recovery]`, `BACKTEST_TRACE`) | magenta |
| **param**: a value the log call substituted (`Bot %s: exit slice %d of %s` → the id, the number) | bold green |
| a **guess**: a word that looks like a value, on a line no template fits | green, not bold |
| traceback lines | dim red |

Every word is still printed; colour is never the only signal. On the plain path the bytes are the input's own: line endings (`\r\n`, no final newline) and bytes that are not UTF-8 pass through unchanged. **How a param is known.** The plain line cannot say which words were substituted, so `scripts/render_log_templates.py` reads every log call's message template out of `src/` with `ast` into `src/support/log_view/template_catalogue.json`, and the viewer matches a line against it: exact for a `%`-call, an f-string and a call with no params. A line no template fits (or two fit and disagree), and the few calls whose message is a variable, are guessed (`key=value` values, bot ids, numbers) and drawn in the guess style. `test_the_log_template_catalogue_is_current.py` fails when a log call is added or changed without `python3 scripts/render_log_templates.py --write`, so the viewer cannot silently fall behind; it also fails if the number of variable-message calls grows.

Filters keep whole records: a traceback or other continuation line is shown or hidden with the record above it, and a line before the first record appears only when no filter is set. `--level` is "this level and above"; `--bot` matches the 6-character id as a whole word; `--tag` takes `health` or `[health]`; `--since` takes `2h`, `30m`, `1d12h`, `today`, `yesterday` or `2026-10-20T14:30` (a local time). `--follow` needs `--file` (a pipe already streams) and survives a truncation or a rotation of the file.

**Limits.** A record is matched on its first line; a param that itself holds a newline is guessed. A viewer on a different version of the code than the writer may mis-match (the VPS runs one checkout, so the catalogue is the same).
