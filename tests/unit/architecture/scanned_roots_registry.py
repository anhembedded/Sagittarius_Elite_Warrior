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

from .ui_trees import UI_TREE_PATHS

#: The UI trees as registry rows. Four guards below read `UI_TREES` from
#: `ui_trees.py`, so their registered roots are derived from the same tuple
#: rather than repeated here — `EPIC-025` moved the UI three times and each
#: move meant editing the guard *and* its row, which is two chances to forget
#: one.
UI_TREE_ROWS: tuple[tuple[str, str], ...] = tuple(
    (path, "*.py") for path in UI_TREE_PATHS
)

#: The rows where finding **nothing** is the point, not a lost subject.
#:
#: `test_scanned_roots_are_not_empty.py` exists because a path-scanning guard
#: whose tree moved passes faster rather than failing — four times in
#: `EPIC-025` alone. Exactly one rule inverts that: ADR D21 drives `.qml` to
#: **zero**, which `EPIC-025` PR 4.3l reached. `test_no_new_qml.py` is a ban
#: now rather than a ratchet, and an empty scan is it succeeding.
#:
#: This is deliberately a list of (guard, root, pattern) triples rather than a
#: flag on a guard: an exemption has to name the exact scan it excuses, so a
#: guard that later gains a second, genuinely-emptied root still fails.
#: `test_scanned_roots_are_not_empty.py` also checks every entry here is a real
#: registered row, so a stale exemption cannot sit unnoticed.
EMPTY_BY_DESIGN: tuple[tuple[str, str, str], ...] = (
    ("tests/unit/architecture/test_no_new_qml.py", "src", "*.qml"),
    # `EPIC-025` PR 4.4e — `src/presentation/ui/screens/` deleted for good;
    # see the row's own comment above.
    (
        "tests/unit/architecture/test_no_cross_screen_imports.py",
        "src/presentation/ui/screens",
        "*.py",
    ),
    # `tests/sanity/test_composition_root.py`'s "Mode 12" check
    # (`test_every_screen_package_has_a_navigable_route`) reads
    # `_screen_packages()`, which walks this same now-deleted tree. Unlike
    # the row above, this one is a genuinely *temporary* exemption, not a
    # permanent design decision: the rule it enforces (a screen package on
    # disk that nothing routes to) still applies under `modules/*/ui/`, and
    # `Tasks/backlog/BOT-141_retarget_event_flow_guard_3_to_module_ui.md` is
    # the follow-up that retargets it there. It belongs here rather than
    # failing silently in the meantime.
    ("tests/sanity/test_composition_root.py", "src/presentation/ui/screens", "*.py"),
)

#: (guard file, ((scanned root, file glob), ...)) — paths relative to the repo root.
GUARDS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    # --- tests/unit/architecture (EPIC-025) --------------------------------
    ("tests/unit/architecture/test_module_boundaries.py", (("src", "*.py"),)),
    # `BUG-127` / `CS-003` — every type the app resolves must be bound. Scans
    # both roots for both halves of the question: `scripts/` probes resolve real
    # ports and bind their own doubles, so leaving them out would miss
    # violations and invent them in equal measure.
    (
        "tests/unit/architecture/test_every_resolved_type_is_bound.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
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
    # `BUG-124`/`BUG-125` — every method called on an engine port (the event
    # bus, and `self.logger` inside a presenter) must exist on it. It scans
    # `src/` and `scripts/` because those are what runs as the real
    # application; `tests/` is deliberately absent (a test may build its own
    # recorder around the bus).
    (
        "tests/unit/architecture/test_engine_port_calls_are_real.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    # `BUG-126` — a class that subscribes to the event bus must be named
    # somewhere else in the application, or nothing can construct it and its
    # events reach nobody. Two roots: `src/` is where a subscriber may be
    # defined, `scripts/` is a legitimate place for the construction (a probe
    # or an end-to-end script is a real consumer). An empty `scripts/` scan
    # would silently turn every script-only subscriber into a false positive,
    # which is the opposite failure but registered for the same reason.
    (
        "tests/unit/architecture/test_a_bus_subscriber_is_constructed.py",
        (("src", "*.py"), ("scripts", "*.py")),
    ),
    # PR 1.6g — every name declared to be the repository root must resolve to
    # it. A hop count breaks on any change of depth, which is every move this
    # epic makes, and it did so twice in two pull requests.
    (
        "tests/unit/architecture/test_no_root_is_found_by_counting.py",
        (
            ("src", "*.py"),
            ("tests", "*.py"),
            ("scripts", "*.py"),
            ("tools", "*.py"),
        ),
    ),
    # `CS-001`'s own index guard. `Docs/` rather than `src/`, and registered
    # for the same reason as the rest: a case-study directory that moved would
    # otherwise leave every check in that file passing over an empty scan.
    (
        "tests/unit/architecture/test_case_study_index_is_consistent.py",
        (("Docs/CASE_STUDIES", "*.md"),),
    ),
    # --- legacy presentation guards -----------------------------------------
    (
        "tests/unit/architecture/test_screen_layer_structure.py",
        (("src/presentation/ui", "*.py"),),
    ),
    (
        "tests/unit/architecture/test_card_layer_structure.py",
        UI_TREE_ROWS,
    ),
    (
        "tests/unit/presentation/ui/test_widget_guards_hold.py",
        UI_TREE_ROWS,
    ),
    # Permanent ban, not a ratchet, since PR 4.4e: `EPIC-025` Phase 4 deleted
    # `src/presentation/ui/screens/` for good (settings was the last screen),
    # exactly as this guard's own `test_screens_root_is_where_we_think_it_is`
    # predicted. Registered here (not simply dropped) so check (3) below
    # still confirms this file's own scan is accounted for; `EMPTY_BY_DESIGN`
    # is what tells check (2) that finding nothing is the guard succeeding,
    # the same shape as `test_no_new_qml.py`'s zero.
    (
        "tests/unit/architecture/test_no_cross_screen_imports.py",
        (("src/presentation/ui/screens", "*.py"),),
    ),
    (
        "tests/unit/presentation/ui/test_preview_fixtures_exist.py",
        (("src/support/ui_kit/sidebar", "*.py"),),
    ),
    # Two roots since `EPIC-025` PR 1.6a: `Palette` itself now lives under
    # `support/ui_kit/assets/`, while most of its consumers are still in the
    # legacy tree. An empty scan of either root would silently stop guarding
    # half the files.
    (
        "tests/unit/presentation/ui/test_palette_is_the_only_color_source.py",
        UI_TREE_ROWS,
    ),
    # Retargeted by `EPIC-025` PR 4.3l: `src/presentation/ui/qml/` is deleted,
    # and the rule (a shared widget library may not import a screen) moved to
    # the two libraries that replaced it. `test_qml_style_discipline.py` had a
    # row here too and went with the tree — its subject was `.qml` files.
    (
        "tests/unit/architecture/test_qml_library_does_not_import_screens.py",
        (("src/support/ui_kit", "*.py"), ("src/support/charting", "*.py")),
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
        (*UI_TREE_ROWS, ("scripts", "*.py"), ("tests", "*.py")),
    ),
    (
        "tests/unit/modules/backtesting/ui/test_backtest_view_contract.py",
        (("src/modules/backtesting/ui", "*.py"),),
    ),
    (
        "tests/unit/modules/trading/ui/trading/test_trading_view_contract.py",
        (("src/modules/trading/ui/trading", "*.py"),),
    ),
    ("tests/unit/presentation/test_enum_labels.py", (("src/presentation", "*.py"),)),
    # --- application / domain / infrastructure ------------------------------
    # PR 3.1c retargeted this guard: `src/application/` is **empty** now, and a
    # path-scanning guard that has lost its subject passes faster rather than
    # failing. The row is what caught it — `src/modules/*/application` is a glob
    # the registry cannot express, so the guard keeps its own non-emptiness
    # assertion and this row names the parent it walks.
    (
        "tests/unit/architecture/test_application_layer_structure.py",
        (("src/modules", "*.py"),),
    ),
    # PR 3.1c rescued the `i_*.py` naming rule the retarget above would have
    # dropped. `src/` rather than `src/modules`, because `support/*` packages
    # publish contracts too and the convention is the repository's.
    (
        "tests/unit/architecture/test_contract_file_naming.py",
        (("src", "*.py"),),
    ),
    (
        "tests/unit/support/indicators/test_indicator_script_conventions.py",
        (
            # `src/support/indicators/indicator_scripts` since PR 1.6g. This
            # row named the right path from the start, but the guard's own
            # `_SCRIPTS_DIR`/`_DOMAIN_DIR` kept pointing at the deleted
            # `src/domain` tree for three days regardless — this registry
            # never checks that a guard's source actually reads the path
            # registered for it (`BUG-131`), only that the registered path
            # itself exists.
            ("src/support/indicators/indicator_scripts", "*.py"),
        ),
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
    # Guard 3 used to register a second root here (`src/presentation/ui/
    # screens`) for its own cross-screen check. `EPIC-025` Phase 4 emptied
    # that tree for good (settings was the last screen, PR 4.4e) — the row
    # is retired, not retargeted; Guard 3's own docstring records the
    # dormancy and `BOT-141` is the follow-up that retargets it.
    ("tests/unit/test_event_flow_guards.py", (("src", "*.py"),)),
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
        ((".claude/rules", "*.md"),),
    ),
    (
        "tests/unit/architecture/test_claude_tree_is_wired.py",
        (
            (".claude/rules", "*.md"),
            (".claude/skills", "SKILL.md"),
            (".claude/agents", "*.md"),
            (".claude/templates", "*.md"),
        ),
    ),
    ("tests/unit/test_task_board_is_consistent.py", (("Tasks", "*.md"),)),
    (
        "tests/unit/architecture/test_spec_index_is_consistent.py",
        (("Docs/SPEC", "SPEC-*.md"),),
    ),
    # --- sanity ---------------------------------------------------------------
    (
        "tests/sanity/test_composition_root.py",
        (
            ("src", "*.py"),
            ("src/presentation/ui/screens", "*.py"),
            # PR 2.1b — the two roots this file scans by name, both of which it
            # had wrong until the gate said so. `modules/*/application` is
            # derived from disk by `_use_case_roots()` and so cannot go stale;
            # these two are written down and can, which is exactly what a row
            # here is for. PR 3.1c is the second time that paid: the legacy
            # `application/use_cases` root emptied out when `backtest/` became
            # `modules/backtesting/application/`, and this row failed rather
            # than the scan quietly reading nothing.
            ("src/modules/backtesting/application", "*.py"),
            ("src/modules/strategy/domain/strategies", "*.py"),
        ),
    ),
    ("tests/sanity/test_self_check_process.py", (("src", "main.py"),)),
    (
        "tests/sanity/test_python_floor.py",
        (("src", "*.py"), ("scripts", "*.py"), ("tests", "*.py")),
    ),
)
