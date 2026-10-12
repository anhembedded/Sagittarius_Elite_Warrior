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
| 4 | `PREFLIGHT_FAILED` | a pre-flight check failed | `run`, `preflight` | not restarted |
| 5 | `CONFIGURATION` | configuration or credentials are missing, or the application refuses them (no key, a key that can withdraw, Hedge Mode) | `run`, `preflight`, `exchange-status`, trade commands | not restarted |
| 6 | `EXCHANGE` | the exchange was unreachable or rejected the request (including `-2015` and `-1021`) | commands that touch the exchange | restarted with a delay |
| 10 | `HOST_NOT_RUNNING` | no host is running | `status` | — |
| 11 | `HOST_UNHEALTHY` | a host is running but unhealthy (snapshot stale, a section unavailable) | `status` | — |

A systemd unit takes `RestartPreventExitStatus=2 3 4 5` from this table.

A command that prints a failure and then exits 0 is a bug, not a code.
