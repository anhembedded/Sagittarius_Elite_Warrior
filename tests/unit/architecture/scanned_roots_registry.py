"""The registry of path-scanning guards and the directories each one scans.

Data only — read by `test_scanned_roots_are_not_empty.py`. This registry is how
HLD §9.3 rule 4 ("every guard that scans a path gains an assertion that the scan
found at least one file") is satisfied: once, centrally, for every guard, instead
of a copy of the same assertion in twenty files. A guard may still keep its own
root check where it already had one. Paths are relative
to the repository root. Register the directories a guard *scans*, not the
repository root it derives them from: scanning the repository root is never
empty and proves nothing. When `EPIC-025` moves a tree, the guard is
retargeted and its row here changes in the same commit.
"""

from __future__ import annotations

#: (guard file, ((scanned root, file glob), ...)) — paths relative to the repo root.
GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    # --- tests/unit/architecture (EPIC-025) --------------------------------
    ("tests/unit/architecture/test_module_boundaries.py", (("src", "*.py"),)),
    ("tests/unit/architecture/test_no_new_qml.py", (("src", "*.qml"),)),
    (
        "tests/unit/architecture/test_module_domain_is_qt_free.py",
        (("src/core", "*.py"), ("src/support/binance_gateway", "*.py")),
    ),
    ("tests/unit/architecture/test_module_declarations.py", (("src/shell", "*.py"),)),
    (
        "tests/unit/architecture/test_no_global_stylesheet.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    (
        "tests/unit/architecture/test_scanned_roots_are_not_empty.py",
        (("tests", "test_*.py"),),
    ),
    # `EPIC-025` PR 0.4a-3 — HLD §10.3 rule 4's guard. It scans `tests/`, not
    # `src/`: the thing it forbids is a *test* substituting another module's
    # port with a `Mock` instead of that module's verified fake.
    (
        "tests/unit/architecture/test_no_foreign_port_is_mocked.py",
        (("tests", "*.py"),),
    ),
    # `BUG-120` — the other half of HLD §10.3's "verified fake". The guard
    # above stops a consumer reaching past the fake; this one stops the fake
    # itself from growing a query helper that no contract covers. It scans
    # `src/` for the fakes and `tests/unit/modules/` for the tests that must
    # exercise their extra helpers, so both roots are registered: a fake tree
    # that moved in a later phase and a module test tree that did are equally
    # able to make the scan silently empty.
    (
        "tests/unit/architecture/test_fake_helpers_are_verified.py",
        (
            ("src/modules", "fake_*.py"),
            ("tests/unit/modules", "*.py"),
        ),
    ),
    # --- legacy presentation guards -----------------------------------------
    (
        "tests/unit/architecture/test_screen_layer_structure.py",
        (("src/presentation/ui", "*.py"),),
    ),
    (
        "tests/unit/architecture/test_card_layer_structure.py",
        (("src/presentation/ui", "*.py"),),
    ),
    (
        "tests/unit/presentation/ui/test_widget_guards_hold.py",
        (("src/presentation/ui", "*.py"), ("src/support/ui_kit", "*.py")),
    ),
    (
        "tests/unit/architecture/test_no_cross_screen_imports.py",
        (("src/presentation/ui/screens", "*.py"),),
    ),
    (
        "tests/unit/presentation/ui/test_preview_fixtures_exist.py",
        (
            ("src/presentation/ui/screens", "*.py"),
            ("src/presentation/ui/components/sidebar", "*.py"),
        ),
    ),
    # Two roots since `EPIC-025` PR 1.6a: `Palette` itself now lives under
    # `support/ui_kit/assets/`, while most of its consumers are still in the
    # legacy tree. An empty scan of either root would silently stop guarding
    # half the files.
    (
        "tests/unit/presentation/ui/test_palette_is_the_only_color_source.py",
        (("src/presentation/ui", "*.py"), ("src/support/ui_kit", "*.py")),
    ),
    (
        "tests/unit/architecture/test_qml_library_does_not_import_screens.py",
        (("src/presentation/ui/qml", "*.py"),),
    ),
    (
        "tests/unit/presentation/ui/qml/test_qml_style_discipline.py",
        (("src/presentation/ui/qml", "*.qml"),),
    ),
    # `BUG-115`/`BOT-133`, widened 2026-09-15 (review finding S1). Two rules
    # with two scopes, so all three roots are registered: building a
    # `QQuickWidget` is forbidden in `src/presentation/ui` and `scripts/`
    # (what a user or a screenshot actually runs), while seeding the theme by
    # hand is forbidden in `tests/` as well. It shipped scanning only the
    # first, and a violation planted in `scripts/` left it green — which is
    # exactly the silently-empty scan this registry exists to catch, one root
    # at a time rather than in total.
    (
        "tests/unit/architecture/test_quick_widget_only_in_embed.py",
        (
            ("src/presentation/ui", "*.py"),
            ("scripts", "*.py"),
            ("tests", "*.py"),
        ),
    ),
    (
        "tests/unit/presentation/ui/qml/test_select_list_bodies.py",
        (("src/presentation/ui/qml/SelectList", "*.qml"),),
    ),
    (
        "tests/unit/presentation/ui/qml/test_stat_grid_and_checkbox_list_bodies.py",
        (("src/presentation/ui/qml", "*.qml"),),
    ),
    (
        "tests/unit/presentation/ui/screens/backtest/test_backtest_view_contract.py",
        (("src/presentation/ui/screens/backtest", "*.py"),),
    ),
    (
        "tests/unit/presentation/ui/screens/trading/test_trading_view_contract.py",
        (("src/presentation/ui/screens/trading", "*.py"),),
    ),
    ("tests/unit/presentation/test_enum_labels.py", (("src/presentation", "*.py"),)),
    # --- application / domain / infrastructure ------------------------------
    (
        "tests/unit/architecture/test_application_layer_structure.py",
        (("src/application", "*.py"),),
    ),
    (
        "tests/unit/domain/test_indicator_script_conventions.py",
        (("src/domain/indicator_scripts", "*.py"), ("src/domain", "*.py")),
    ),
    (
        "tests/unit/architecture/test_only_the_session_factory_constructs_binance_client.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    (
        "tests/unit/architecture/test_order_submission_mode_live_is_restricted.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    # --- whole-tree guards --------------------------------------------------
    ("tests/unit/test_logging_namespace_guard.py", (("src", "*.py"),)),
    (
        "tests/unit/test_event_flow_guards.py",
        (("src", "*.py"), ("src/presentation/ui/screens", "*.py")),
    ),
    (
        "tests/unit/config/test_binance_endpoint_config_keys_are_dead.py",
        (("src/config", "*.json"),),
    ),
    (
        "tests/unit/config/test_credentials_never_reach_a_git_tracked_file.py",
        (("src", "*.py"), ("src/config", "*.json")),
    ),
    # --- repository bookkeeping guards -------------------------------------
    (
        "tests/unit/test_rule_navigation_is_complete.py",
        ((".agents/rules", "*-rule.md"),),
    ),
    (
        "tests/unit/architecture/test_claude_rule_pointers_match_agents_rules.py",
        ((".agents/rules", "*-rule.md"), (".claude/rules", "*.md")),
    ),
    ("tests/unit/test_task_board_is_consistent.py", (("Tasks", "*.md"),)),
    (
        "tests/unit/architecture/test_spec_index_is_consistent.py",
        (("Docs/SPEC", "SPEC-*.md"),),
    ),
    # --- sanity ---------------------------------------------------------------
    (
        "tests/sanity/test_composition_root.py",
        (("src", "*.py"), ("src/presentation/ui/screens", "*.py")),
    ),
    ("tests/sanity/test_self_check_process.py", (("src", "main.py"),)),
    (
        "tests/sanity/test_python_floor.py",
        (("src", "*.py"), ("scripts", "*.py"), ("tests", "*.py")),
    ),
)
