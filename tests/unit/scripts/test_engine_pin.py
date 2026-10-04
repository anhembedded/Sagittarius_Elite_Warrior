"""`BUG-148` — the engine-pin check accepts only the installed engine at `engine.ref`'s commit."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.engine_pin import EngineInstall, pin_problems

_PINNED = "934b830f5b4e6c0a5442b94833edacf443f87c79"
_SITE = Path("/env/lib/python3.12/site-packages")
_INSTALLED = _SITE / "sagittarius_engine" / "__init__.py"


def test_the_installed_engine_at_the_pinned_commit_passes() -> None:
    assert pin_problems(_PINNED, EngineInstall(_INSTALLED, (_SITE,), _PINNED)) == []


def test_an_engine_installed_at_another_commit_is_named() -> None:
    problems = pin_problems(_PINNED, EngineInstall(_INSTALLED, (_SITE,), "72e4042"))

    assert problems == [f"the installed engine is 72e4042; engine.ref pins {_PINNED}"]


def test_an_engine_installed_without_the_installer_is_refused() -> None:
    problems = pin_problems(_PINNED, EngineInstall(_INSTALLED, (_SITE,), None))

    assert problems and "an unrecorded commit" in problems[0]


def test_a_checkout_on_the_path_is_refused_even_with_the_right_record() -> None:
    checkout = Path("/work/Sagittarius_Engine/sagittarius_engine/__init__.py")

    problems = pin_problems(_PINNED, EngineInstall(checkout, (_SITE,), _PINNED))

    assert problems and str(checkout.parent) in problems[0]
    assert "PYTHONPATH" in problems[0]


def test_a_missing_engine_is_named() -> None:
    assert pin_problems(_PINNED, EngineInstall(None, (_SITE,), None)) == [
        "sagittarius_engine is not installed"
    ]
