"""The registry rows of the guards that keep a module's dependents honest.

Split from `scanned_roots_registry.py`, which sits at the 400-line ceiling; the
registry spreads `MODULE_DEPENDENCY_GUARDS` into `GUARDS`, so nothing that reads
the registry changes. Same shape, same rules: register the directories a guard
*scans*.
"""

from __future__ import annotations

MODULE_DEPENDENCY_GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "tests/unit/architecture/test_no_module_depends_on_operations.py",
        (("src", "*.py"),),
    ),
    # `EPIC-038B` (D7) — the command-line host imports no domain or module code.
    (
        "tests/unit/architecture/test_cli_host_imports_no_domain_or_module_code.py",
        (("src/support/cli_host", "*.py"),),
    ),
    # `EPIC-044` - every hand-written set of bot lifecycle states is classified state by state.
    (
        "tests/unit/architecture/test_every_state_set_classifies_every_state.py",
        (
            ("src/modules/bots", "*.py"),
            ("src/modules/alerting", "*.py"),
            ("src/modules/operations", "*.py"),
        ),
    ),
    # `EPIC-039A` - bots decides the market in one place, the venue profile.
    (
        "tests/unit/architecture/test_bots_decide_the_market_in_one_place.py",
        (("src/modules/bots", "*.py"),),
    ),
    # `EPIC-042B` - a state set that names HALTED answers for AWAITING_RECOVERY.
    (
        "tests/unit/architecture/test_every_state_set_that_names_halted_answers_for_awaiting_recovery.py",
        (("src", "*.py"),),
    ),
    # `BOT-177` - the bots service shell stays grouped and kind-neutral.
    (
        "tests/unit/architecture/test_bots_services_stay_grouped.py",
        (("src/modules/bots/application/services", "*.py"),),
    ),
    # `EPIC-045D` - every `*Command` the Bots tab dispatches has a host verb or a reasoned exclusion.
    (
        "tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py",
        (
            ("src/modules/bots/ui", "*.py"),
            ("src/modules/bots/application/use_cases", "*.py"),
        ),
    ),
    # `EPIC-048A` - the UI reaches the application only through its doors.
    (
        "tests/unit/architecture/test_ui_reaches_the_application_through_its_doors.py",
        (("src/modules", "*.py"), ("src", "*.py")),
    ),
    # `EPIC-047E` - the VPS tab's composition reaches no Binance client (AC10).
    (
        "tests/unit/architecture/test_the_vps_tab_reaches_no_binance_client.py",
        (
            ("src/modules/bots/adapters/remote_host", "*.py"),
            ("src/shell/vps_link", "*.py"),
        ),
    ),
)
