"""The registry row of the guard that keeps the command-line host free of domain and module code.

Split from `scanned_roots_registry.py`, which sits at the 400-line ceiling, the
way `scanned_roots_registry_order_paths.py` was (`EPIC-034I`): the registry spreads
`CLI_HOST_GUARDS` into `GUARDS`, so nothing that reads the registry changes.
Register the directories a guard *scans* (`EPIC-038B`, decision D7).
"""

from __future__ import annotations

CLI_HOST_GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "tests/unit/architecture/test_cli_host_imports_no_domain_or_module_code.py",
        (("src/support/cli_host", "*.py"),),
    ),
)
