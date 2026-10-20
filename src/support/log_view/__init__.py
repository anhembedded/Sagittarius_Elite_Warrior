"""Read plain log lines and show them with the substituted values coloured (`PRO-019`, `BOT-199`).

Capability: Show a plain log, with the values a log call substituted coloured apart from its fixed text
    Also: log viewer, log colour, colour logs, coloured log, log param, log argument, journalctl pipe, logs command, tail log, log filter
    Use: run_logs, configure_logs_parser, system_environment
    User: src/main.py
    Status: stable

The stored record keeps its exact bytes (`logging-rule.md` §8, `LOGGING.md` §3);
colour is added here, at the screen, from the plain line. The package imports
nothing of the application and nothing of the Engine.
"""
