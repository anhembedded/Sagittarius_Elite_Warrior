"""`BOT-133` — the engine-build preflight, and the live check that this app's
declared engine dependencies actually hold against the installed build.

Two different jobs in one file on purpose: the mechanism must both *work*
(report a stale build in a way an operator can act on) and *be true* (its
declarations still match reality). A declaration list nobody verifies is the
hand-maintained copy of state this repo keeps getting bitten by.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_capabilities import (
    REINSTALL_COMMAND,
    REQUIRED_ENGINE_CAPABILITIES,
    RequiredEngineCapability,
    find_missing_capabilities,
    format_missing_capabilities,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_capability_validator_extension import (
    EngineCapabilityValidatorExtension,
)


def test_the_installed_engine_satisfies_every_declared_capability():
    """The live half: if this goes red, the venv's engine is older than the
    app's source — which is the whole failure `BOT-133` exists to name."""
    assert find_missing_capabilities() == [], (
        "installed sagittarius_engine is stale:\n"
        + format_missing_capabilities(find_missing_capabilities())
    )


def test_declarations_are_not_empty_and_carry_their_origin():
    """A guard that declares nothing passes for the wrong reason, and an entry
    with no `since` cannot tell a reader what the dependency is for."""
    assert REQUIRED_ENGINE_CAPABILITIES
    for capability in REQUIRED_ENGINE_CAPABILITIES:
        assert capability.since, capability.attribute


def test_a_missing_attribute_is_reported():
    missing = find_missing_capabilities(
        (
            RequiredEngineCapability(
                module="sagittarius_engine.extensions.pyside_mvc",
                attribute="no_such_engine_api",
                since="TEST",
            ),
        )
    )
    assert len(missing) == 1
    assert "attribute missing" in missing[0]


def test_a_missing_parameter_is_reported_not_just_a_missing_symbol():
    """The stale-build case that actually happened: the function exists, the
    parameter does not, and calling it raises `TypeError` far from the cause."""
    missing = find_missing_capabilities(
        (
            RequiredEngineCapability(
                module="sagittarius_engine.extensions.pyside_mvc.workbench.configure_item_view",
                attribute="configure_item_view",
                parameter="no_such_parameter",
                since="TEST",
            ),
        )
    )
    assert len(missing) == 1
    assert "no_such_parameter" in missing[0]


def test_an_unimportable_module_is_reported():
    missing = find_missing_capabilities(
        (
            RequiredEngineCapability(
                module="sagittarius_engine.no_such_module",
                attribute="anything",
                since="TEST",
            ),
        )
    )
    assert len(missing) == 1
    assert "not importable" in missing[0]


def test_the_report_names_the_fix_not_just_the_symptom():
    report = format_missing_capabilities(["something [TASK-X] — attribute missing"])
    assert REINSTALL_COMMAND in report
    assert "install-rule.md" in report
    assert "not a bug in the app" in report


def test_the_extension_passes_silently_when_the_engine_is_current():
    """No `SystemExit`, and the boot log says so once."""
    logged: list[str] = []

    class _Context:
        class logger:  # noqa: N801 - stands in for the engine's logger object
            @staticmethod
            def info(message: str) -> None:
                logged.append(message)

    EngineCapabilityValidatorExtension().boot(_Context())
    assert any("Pre-flight engine check passed" in line for line in logged)


def test_the_extension_fails_the_boot_when_a_capability_is_missing():
    errors: list[str] = []

    class _Context:
        class logger:  # noqa: N801 - stands in for the engine's logger object
            @staticmethod
            def error(message: str) -> None:
                errors.append(message)

    extension = EngineCapabilityValidatorExtension(
        (
            RequiredEngineCapability(
                module="sagittarius_engine.extensions.pyside_mvc",
                attribute="no_such_engine_api",
                since="TEST",
            ),
        )
    )
    with pytest.raises(SystemExit) as exit_info:
        extension.boot(_Context())

    assert exit_info.value.code == 1
    assert errors and REINSTALL_COMMAND in errors[0]
