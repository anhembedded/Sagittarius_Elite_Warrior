"""`BUG-148` — the engine-pin check accepts only the installed engine at `engine.ref`'s commit."""

from __future__ import annotations

import base64
import hashlib
import shutil
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.engine_pin import (
    ENGINE_PACKAGE,
    EngineInstall,
    installed_engine,
    pin_problems,
    record_install,
)

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


def _install_engine(site: Path, source: str) -> None:
    """What an installer leaves in `site`: the package and a dist-info with its RECORD."""
    package = site / ENGINE_PACKAGE
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text(source, encoding="utf-8")
    dist_info = site / "sagittarius_engine-3.0.0.dist-info"
    shutil.rmtree(dist_info, ignore_errors=True)  # a reinstall replaces the directory
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: sagittarius-engine\nVersion: 3.0.0\n",
        encoding="utf-8",
    )
    digest = base64.urlsafe_b64encode(hashlib.sha256(source.encode()).digest()).rstrip(
        b"="
    )
    (dist_info / "RECORD").write_text(
        f"{ENGINE_PACKAGE}/__init__.py,sha256={digest.decode()},{len(source)}\n",
        encoding="utf-8",
    )


def test_an_engine_replaced_after_install_is_refused(tmp_path: Path) -> None:
    """`BUG-153`: a manual `pip install` leaves the recorded commit naming the old engine."""
    site, prefix = tmp_path / "site-packages", tmp_path / "prefix"
    site.mkdir()
    prefix.mkdir()
    _install_engine(site, "ENGINE = 'pinned'\n")
    record_install(_PINNED, prefix, (site,))
    assert pin_problems(_PINNED, installed_engine(prefix, (site,))) == []

    _install_engine(site, "ENGINE = 'another commit'\n")

    problems = pin_problems(_PINNED, installed_engine(prefix, (site,)))
    assert problems and "an unrecorded commit" in problems[0]


def test_an_installation_whose_record_file_is_unchanged_keeps_its_commit(
    tmp_path: Path,
) -> None:
    site, prefix = tmp_path / "site-packages", tmp_path / "prefix"
    site.mkdir()
    prefix.mkdir()
    _install_engine(site, "ENGINE = 'pinned'\n")
    record_install(_PINNED, prefix, (site,))

    _install_engine(site, "ENGINE = 'pinned'\n")

    assert pin_problems(_PINNED, installed_engine(prefix, (site,))) == []
