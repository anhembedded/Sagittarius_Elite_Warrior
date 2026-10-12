"""The command-line host: everything that turns a command's result into a process exit status and a report in a chosen format.

`EPIC-038B`, decision D7 (`DECISION_2026-10-09_headless_operation.md` §4a). This
package is the host half of the command line and none of its content: it knows
what an exit code and a report are, never what `sync` or a bot is. It imports
the Python standard library, the Engine, and exactly four kernel contracts
(`ICliCommandHandler`, `ICliRegistry`, `CliOutcome`, `Report` with its two
renderer ports) — no module, no domain value object, no infrastructure, no
shell, no presentation, no other support package.
`tests/unit/architecture/test_cli_host_imports_no_domain_or_module_code.py`
holds that line, so that moving this package to the Engine later is a move of
one directory plus those four contract files, not a rewrite.

Why `support/` and not a new top-level package: the boundary rules already say
a support package imports no module, which is the half of the isolation this
location gives for free; the guard adds the rest.

@par Extension cases
  · a new output format — a subclass of `IReportRenderer` in `adapters/` and
    one `register` call where the registry is built;
  · a new exit code — see `core/contracts/cli_outcome.py`;
  · a new launcher verb (`gui`, `shell`, a future `run`) — one `LauncherVerb`
    in the entry point's list; the parser and the exit mapping do not change.
"""
