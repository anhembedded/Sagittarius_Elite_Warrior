# Logging for an unattended run

The log guide of the headless operation (`EPIC-038`, task `038G`). The runbook (`EPIC-038H`) links here for log placement, rotation and the health line. Design: [`DESIGN_2026-10-09_headless_operation.md` §6, §12](../../Tasks/epics/EPIC-038_headless_operation/DESIGN_2026-10-09_headless_operation.md) · evidence: [`RESEARCH` §9](../../Tasks/epics/EPIC-038_headless_operation/RESEARCH_2026-10-09_headless_operation.md) · decision: O7.

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
# The unit name is the one EPIC-038H will ship.
journalctl -u sew-run -o cat | grep -E ' - (WARNING|ERROR|CRITICAL) - '
```

JSON logging would be a formatter the Engine owns. It is recorded, not built.

## 4. The health line

The `run` host (`EPIC-038D`) writes one INFO record per health interval (`--health-interval`, default 60 s) and one at each state change it makes (`SERVING`, `DRAINING`), through `log_health_line` in `src/modules/operations/application/health_line.py`, the only writer:

```text
[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0,recovering:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310
```

| Key | Value | Unknown |
| :--- | :--- | :--- |
| `state` | `BOOTING`, `SERVING`, `DRAINING`, `STOPPED` or `FAILED` | n/a |
| `up` | whole seconds since boot, suffixed `s` | n/a |
| `bots` | `running`, `paused`, `halted` and `recovering` counts, zeros included, in that order; `none` when the bots' section did not answer | n/a |
| `tick_age_s` | whole seconds since the last market tick (the freshest open feed) | `na` |
| `stream_down_s` | whole seconds the worst user-data stream has been out of `connected`; `0` when every stream is connected | `na` when none has reported |
| `skew_ms` | signed milliseconds, local clock minus the exchange's, as the host's probe last measured it (it asks the exchange its time before each snapshot); the venue furthest from zero when several are in use | `na` until the first measurement, and after one that found nothing |
| `rss_mb` | resident memory, whole megabytes | `na` |

Stability: a key is added at the end and never renamed or reordered, and the parser (`parse_health_line`) ignores keys it does not know, so an older monitor survives a newer host. The line holds counts, ages and names only, never free text, so a credential cannot reach it.

**The level is always INFO.** A stale feed is a large `tick_age_s`, not a WARNING; the escalation to a person is the alert source's job (`EPIC-036`). A health line that logged WARNING would also trip the CI run-log scan on every quiet-but-healthy run.

Progress, not liveness: the process being alive proves nothing about the bots, so a monitor alerts when the line stops appearing or when `tick_age_s`/`stream_down_s` grow past its threshold.

## 5. Known gaps and sources of volume (`EPIC-038C`)
- **Journal volume from the Engine's dispatcher: accepted and bounded** (`EPIC-038D`, recorded 2026-10-13). The Engine logs `Executing query: <name>` at INFO for every dispatch (`kernel/dispatcher.py`). The health snapshot's `bots` section dispatches two queries (`GetBotStatusReportQuery`, `ListBotsQuery`) per snapshot, so the host writes **two extra INFO lines per health interval**: 2 880 a day at the host's default 60 s (the 17 000 a day first counted were the GUI's 10 s snapshot, which `run` no longer uses). The count does not grow with the number of bots. The three ways out were weighed: demoting the line is an Engine change (decision O7: none in this epic); a filter on that logger is a settings change and would hide the queries of a failing run along with the healthy ones; accepting it costs under 0.2 MB a day in the journal, which journald's `SystemMaxUse=` and NSSM's rotation already bound. `test_a_health_interval_costs_two_dispatcher_lines_and_no_more` fails if a new dispatch is added to the tick, so the cost cannot grow unseen. Not a hot loop (`logging-rule.md` §6).
- **`stream_down_s` replaces `stream_age_s`** (`EPIC-038D`). The user-data stream publishes state *changes*, not each message, so "seconds since the last user-stream message" never existed. The field was renamed before any monitor parsed it, and is fed from the snapshot's `trading.stream_down_s`.
- **`tick_age_s` is the freshest feed.** In the snapshot `market_data.tick_age_s` is the age of the *most recent* candle across every open feed, so one dead symbol hides behind any live one, and a feed closed on purpose is never forgotten. The per-feed ages are published (`market_data.feeds`); a monitor that cares about one symbol reads those.

## 6. What `run` writes, by tag (`EPIC-038D`)

Everything on standard output, one record per line, in the format of §3. The tags are stable and greppable.

| Tag | Level | Meaning |
| :--- | :--- | :--- |
| `[run]` | INFO | the options in effect: stop policy, timeouts, pre-flight enforced or skipped, host signal |
| `[preflight]` | INFO / WARNING / ERROR | the checks that ran; each non-passing finding with its remedy; the `--skip-preflight` override (WARNING) |
| `[host]` | INFO | each state change (`BOOTING -> SERVING`, `SERVING -> DRAINING`, `DRAINING -> STOPPED`), each start-up step, the stop policy and how it ended; WARNING when the policy was given up on (timeout or second signal) and the bots it left |
| `[alerts]` | WARNING | no alert channel carries bot events (until `EPIC-036B`); the one WARNING a healthy `run` writes at start |
| `[recovering]` | WARNING | one per bot left RECOVERING after the restart, and whose move it is (decision O2) |
| `[resume-recovering]`, `[start-planned]` | INFO / WARNING | what `--resume-recovering` and `--start-planned` did, venue by venue and bot by bot |
| `[stop-policy]` | INFO / WARNING | `leave-orders`: each bot left and its orders resting; `stop-bots`: each stop requested and confirmed, and each stop refused |
| `[signals]` | INFO | which signals ask the host to stop |
| `[health]` | INFO | the health line (§4); WARNING `probe <name> failed` once per streak when the clock probe cannot ask the exchange |
| `[health-snapshot]` | INFO / ERROR | where the snapshot is written and how often; ERROR when a write fails |
