# Logging for an unattended run

The log guide of the headless operation (`EPIC-038`, task `038G`). The runbook (`EPIC-038H`) links here for log placement, rotation and the health line. Design: [`DESIGN_2026-10-09_headless_operation.md` §6, §12](../../Tasks/epics/EPIC-038_headless_operation/DESIGN_2026-10-09_headless_operation.md) · evidence: [`RESEARCH` §9](../../Tasks/epics/EPIC-038_headless_operation/RESEARCH_2026-10-09_headless_operation.md) · decision: O7.

## 1. Where the log goes

The application writes every record to **standard output** (`log.console.enabled`, on in `app_config.json`) and to no file. The supervisor owns the stream:

| Platform | Who captures stdout | Who bounds it |
| :--- | :--- | :--- |
| Linux, systemd | the journal | journald (`SystemMaxUse=`, `journalctl --vacuum-time`) |
| Windows, NSSM | the wrapper's captured output | NSSM rotation (`AppRotateFiles`, `AppRotateBytes`, `AppRotateOnline`) |

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

The `run` host writes one INFO record per health interval (`--health-interval`, default 60 s; the flag and the host arrive with `EPIC-038D`), through `log_health_line` in `src/modules/operations/application/health_line.py`, the only writer:

```text
[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0 tick_age_s=2 stream_age_s=5 skew_ms=-120 rss_mb=310
```

| Key | Value | Unknown |
| :--- | :--- | :--- |
| `state` | `BOOTING`, `SERVING`, `DRAINING`, `STOPPED` or `FAILED` | n/a |
| `up` | whole seconds since boot, suffixed `s` | n/a |
| `bots` | `state:count` pairs in the host's order; `none` when it holds no bot | n/a |
| `tick_age_s`, `stream_age_s` | whole seconds since the last market tick / user-stream message | `na` |
| `skew_ms` | signed milliseconds, local clock minus the exchange's | `na` |
| `rss_mb` | resident memory, whole megabytes | `na` |

Stability: a key is added at the end and never renamed or reordered, and the parser (`parse_health_line`) ignores keys it does not know, so an older monitor survives a newer host. The line holds counts, ages and names only, never free text, so a credential cannot reach it.

**The level is always INFO.** A stale feed is a large `tick_age_s`, not a WARNING; the escalation to a person is the alert source's job (`EPIC-036`). A health line that logged WARNING would also trip the CI run-log scan on every quiet-but-healthy run.

Progress, not liveness: the process being alive proves nothing about the bots, so a monitor alerts when the line stops appearing or when `tick_age_s`/`stream_age_s` grow past its threshold.
