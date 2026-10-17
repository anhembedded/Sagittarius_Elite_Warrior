# Exit codes

The process exit status of every command-line command. A supervisor, a cron job
or a monitoring script branches on these numbers, so a number is never reused
for another meaning.

This file is **generated** from `ExitCode` (`src/core/contracts/cli_outcome.py`)
and `EXIT_CODE_TABLE` (`src/support/cli_host/exit_code_table.py`) by
`python3 scripts/render_exit_codes.py --write`; do not edit the table by hand,
a guard compares it with the generator.

| Code | Name | Meaning | Used by | Supervisor |
| :-: | :--- | :--- | :--- | :--- |
| 0 | `SUCCESS` | success, or a clean shutdown | all | — |
| 1 | `ERROR` | unexpected error: a failure nothing named (an unhandled exception has its traceback in the log) | all | restarted |
| 2 | `USAGE` | usage error or a designed refusal: a bad flag, an unknown format, a request that cannot be an order, or a command that declined to act (no data to work on yet, a safety limit); repeating it unchanged cannot help | all | not restarted |
| 3 | `LOCK_HELD` | another copy holds the data root | `run`, mutating commands | not restarted |
| 4 | `PREFLIGHT_FAILED` | a pre-flight check failed that is neither of the two below: the machine (disk, data root, Python), a clock skew the check measured over its threshold, a key without trading permission | `run`, `preflight` | not restarted |
| 5 | `CONFIGURATION` | only the operator can fix it, so a restart would repeat it: no key, a key the exchange rejects (`-2015`: key, address or permission), a bad signature (`-1022`), a key that can withdraw, Hedge Mode | `run`, `preflight`, `exchange-status`, trade commands, `bot stop`, `bot pause`, `bot resume`, `bot start` (this account has no control over the running host) | not restarted |
| 6 | `EXCHANGE` | the exchange was unreachable or out of service, or rejected the clock (`-1021`, which resyncs): a restart can outlast it | commands that touch the exchange | restarted with a delay |
| 10 | `HOST_NOT_RUNNING` | no host is running | `status`, `bot stop`, `bot pause`, `bot resume`, `bot start` | — |
| 11 | `HOST_UNHEALTHY` | a host is running but unhealthy (snapshot stale, a section unavailable or degraded), or a control command got no recorded answer in time | `status`, `bot stop`, `bot pause`, `bot resume`, `bot start` | — |

A systemd unit takes `RestartPreventExitStatus=2 3 4 5` from this table.

A command that prints a failure and then exits 0 is a bug, not a code.
