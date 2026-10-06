"""`BUG-148` — the one way to install the engine, and the check that it is `engine.ref`'s.

CI installed the commit `engine.ref` names; `run-ui.ps1` installed the engine's
moving `main`, `run.ps1` installed none, and `ci-local.ps1`'s mypy step put a
sibling engine checkout on `MYPYPATH`. A machine could therefore run, and
type-check against, an engine CI never built, and nothing said so.

`install` fetches the pinned commit without submodules (the engine carries a
private one, `install-rule.md` §1), replaces the engine in the running
interpreter's environment with it and records the commit beside that
environment, bound to the installed distribution's `RECORD` file: an install that
replaces the engine rewrites `RECORD`, so the record stops matching (`BUG-153`). It does nothing when `check` already passes, so a launcher can
call it on every start. `check` fails when the engine this interpreter imports
is not the installed one (a checkout on the path, an editable install) or when
the recorded commit is not `engine.ref`'s, or no longer describes the
installed distribution.

Stdlib only, no PEP 695 syntax: CI runs it on the runner's Python before the
dependencies are installed.

Retire when: the engine is published as a versioned package that
`requirements.txt` pins like any other dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import logging
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.machinery import PathFinder
from pathlib import Path

ENGINE_PACKAGE = "sagittarius_engine"
ENGINE_DISTRIBUTION = "sagittarius-engine"
ENGINE_REPOSITORY = "https://github.com/anhembedded/Sagittarius_Engine.git"
#: Written beside the environment by `install`: the commit it installed and a fingerprint of that installation.
RECORD_NAME = "sagittarius_engine.ref"
#: Second line of that file: the hash of the installed distribution's `RECORD` it describes.
FINGERPRINT_KEY = "record-sha256"
INSTALL_COMMAND = "python scripts/engine_pin.py install"

_REPO_ROOT = Path(__file__).resolve().parents[1]

logger = logging.getLogger("App.EnginePin")


@dataclass(frozen=True)
class EngineInstall:
    """The engine one interpreter imports, and the commit `install` recorded for it.

    @param origin The file `import sagittarius_engine` loads; `None` when not importable.
    @param site_dirs The interpreter's own package directories.
    @param recorded_ref The commit `install` wrote; `None` when it never ran here.
    """

    origin: Path | None
    site_dirs: tuple[Path, ...]
    recorded_ref: str | None


def pinned_ref(repo_root: Path) -> str:
    return (repo_root / "engine.ref").read_text(encoding="utf-8").strip()


def pin_problems(pinned: str, engine: EngineInstall) -> list[str]:
    """What keeps `engine` from being the pinned engine; empty when it is."""
    if engine.origin is None:
        return [f"{ENGINE_PACKAGE} is not installed"]
    if not any(engine.origin.is_relative_to(site) for site in engine.site_dirs):
        return [
            (
                f"{ENGINE_PACKAGE} is imported from {engine.origin.parent}, not "
                "from this environment's installed packages: take that checkout "
                "off PYTHONPATH, or replace the editable install"
            )
        ]
    if engine.recorded_ref != pinned:
        installed = engine.recorded_ref or "an unrecorded commit"
        return [f"the installed engine is {installed}; engine.ref pins {pinned}"]
    return []


def installed_engine(
    prefix: Path | None = None, site_dirs: tuple[Path, ...] | None = None
) -> EngineInstall:
    """The engine `site_dirs` hold (this interpreter's by default) and its recorded commit."""
    if site_dirs is None:
        paths = sysconfig.get_paths()
        site_dirs = tuple(
            {Path(paths[key]).resolve() for key in ("purelib", "platlib")}
        )
        search_path = None
        spec = importlib.util.find_spec(ENGINE_PACKAGE)
    else:
        search_path = [str(site) for site in site_dirs]
        spec = PathFinder.find_spec(ENGINE_PACKAGE, search_path)
    origin = Path(spec.origin).resolve() if spec and spec.origin else None
    return EngineInstall(origin, site_dirs, _recorded_commit(prefix, search_path))


def check(repo_root: Path) -> int:
    problems = pin_problems(pinned_ref(repo_root), installed_engine())
    if not problems:
        logger.info("[engine-pin] %s is engine.ref's commit", ENGINE_PACKAGE)
        return 0
    for problem in problems:
        logger.error("[engine-pin] %s", problem)
    logger.error("[engine-pin] Fix: %s", INSTALL_COMMAND)
    return 1


def install(repo_root: Path) -> int:
    pinned = pinned_ref(repo_root)
    if not pin_problems(pinned, installed_engine()):
        logger.info("[engine-pin] %s already at %s", ENGINE_PACKAGE, pinned)
        return 0
    logger.info("[engine-pin] installing %s at %s", ENGINE_PACKAGE, pinned)
    with tempfile.TemporaryDirectory() as checkout:
        _fetch(pinned, Path(checkout))
        _record_path().unlink(missing_ok=True)
        _pip(["uninstall", ENGINE_DISTRIBUTION], check=False)
        _pip(["install", checkout], check=True)
    record_install(pinned)
    return check(repo_root)


def record_install(
    commit: str, prefix: Path | None = None, site_dirs: tuple[Path, ...] | None = None
) -> None:
    """Record `commit` as the engine now installed, bound to that installation's files."""
    search_path = None if site_dirs is None else [str(site) for site in site_dirs]
    fingerprint = _distribution_fingerprint(search_path)
    if fingerprint is None:
        raise SystemExit(
            f"[engine-pin] {ENGINE_DISTRIBUTION} has no installed RECORD to bind to"
        )
    lines = [commit, f"{FINGERPRINT_KEY} {fingerprint}"]
    _record_path(prefix).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _recorded_commit(
    prefix: Path | None, search_path: Sequence[str] | None
) -> str | None:
    """The commit `install` recorded, only while it describes the distribution installed now."""
    record = _record_path(prefix)
    if not record.exists():
        return None
    lines = record.read_text(encoding="utf-8").splitlines()
    fingerprint = _distribution_fingerprint(search_path)
    if fingerprint is None or lines[1:] != [f"{FINGERPRINT_KEY} {fingerprint}"]:
        return None
    return lines[0].strip()


def _distribution_fingerprint(search_path: Sequence[str] | None) -> str | None:
    """Hash of the installed distribution's `RECORD`, which every install rewrites.

    `RECORD` lists each installed file with its hash, so an install that replaces
    the engine (`pip install`, `pip install -U`, `uv pip install`) changes it, and
    a record bound to it stops matching. `None` when no distribution is installed.
    """
    if search_path is None:
        found = importlib.metadata.distributions(name=ENGINE_DISTRIBUTION)
    else:
        found = importlib.metadata.distributions(
            name=ENGINE_DISTRIBUTION, path=list(search_path)
        )
    for distribution in found:
        record = distribution.read_text("RECORD")
        if record is not None:
            return hashlib.sha256(record.encode("utf-8")).hexdigest()
    return None


def _record_path(prefix: Path | None = None) -> Path:
    return (prefix or Path(sys.prefix)) / RECORD_NAME


def _fetch(ref: str, checkout: Path) -> None:
    git = shutil.which("git")
    if git is None:
        raise SystemExit("[engine-pin] git is not on PATH")
    for args in (
        ["init", "-q"],
        ["fetch", "-q", "--depth", "1", ENGINE_REPOSITORY, ref],
        ["checkout", "-q", "FETCH_HEAD"],
    ):
        subprocess.run([git, "-C", str(checkout), *args], check=True)  # noqa: S603 -- absolute git, fixed arguments


def _pip(args: list[str], *, check: bool) -> None:
    """pip in this interpreter; `uv pip` for an environment created without pip."""
    if importlib.util.find_spec("pip") is not None:
        confirm = ["-y"] if args[0] == "uninstall" else []
        command = [sys.executable, "-m", "pip", *args, *confirm]
    else:
        uv = shutil.which("uv")
        if uv is None:
            raise SystemExit("[engine-pin] neither pip nor uv is available")
        command = [uv, "pip", args[0], "--python", sys.executable, *args[1:]]
    subprocess.run(command, check=check)  # noqa: S603 -- this interpreter or an absolute uv, fixed arguments


def main(argv: list[str] | None = None) -> int:
    # A command-line run has no app logging configured; the verdict goes to stdout.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("check", "install"))
    action = parser.parse_args(argv).action
    if action == "install":
        return install(_REPO_ROOT)
    return check(_REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
