"""`BOT-204` - the world of the `sew-install` / `sew-update` tests.

@details The real scripts run under bash against a temporary root (`SEW_DEPLOY_ROOT` prefixes every
path they use). What a test cannot have is stood in for by scripts on `PATH` that append one
line per call to a shared log, so a test reads the order the scripts acted in: `systemctl`,
`useradd`, `getent`, `apt-get`, `timedatectl`, `journalctl`, `sudo` (drops `-u sew`), the venv's
`python`/`pip`, and `python3.12` (makes the venv). `git` is the real one, against a local
origin repository that carries the real `deploy/linux` files, so a clone, a fetch and a
checkout really happen. A real systemd, a real `useradd`, `chown` to the `sew` account and a
real pip install are not provable here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

REPO = Path(__file__).resolve().parents[3]
DEPLOY = REPO / "deploy" / "linux"
BRANCH = "master-warrior"

#: The release files a checkout needs, copied from this repository into the fake origin.
_RELEASE_FILES = (
    *(f"deploy/linux/{p.name}" for p in DEPLOY.iterdir() if p.is_file()),
    "requirements-headless.txt",
    "requirements.lock",
)

_LOG_STUB = """#!/bin/sh
# {name}: one line in the shared log, then whatever the world says.
printf '%s %s\\n' "{name}" "$*" >> "$STUB_LOG"
"""

_SYSTEMCTL = (
    _LOG_STUB.format(name="systemctl")
    + """
state="$STUB_STATE"
case "$1" in
  --version) echo "systemd $(cat "$state/systemd_version" 2>/dev/null || echo 255) (255.4-1ubuntu8)"; exit 0 ;;
  is-active)
    if [ -e "$state/active" ]; then echo active; exit 0; fi
    if [ -e "$state/activating" ]; then echo activating; exit 3; fi
    echo inactive; exit 3 ;;
  stop) rm -f "$state/active" "$state/activating"; exit 0 ;;
  start) [ -e "$state/start_fails" ] && exit 1; : > "$state/active"; exit 0 ;;
  show)
    case "$*" in
      *Result*) cat "$state/result" 2>/dev/null || echo success ;;
      *ExecMainStatus*) cat "$state/main_status" 2>/dev/null || echo 0 ;;
    esac
    exit 0 ;;
  cat)
    unit="$SEW_DEPLOY_ROOT/etc/systemd/system"
    printf '# %s\\n' "$unit/sew-run.service"; cat "$unit/sew-run.service"
    for f in "$unit"/sew-run.service.d/*.conf; do [ -e "$f" ] && { printf '# %s\\n' "$f"; cat "$f"; }; done
    exit 0 ;;
  daemon-reload)
    echo "systemctl-saw unit=$(md5sum "$SEW_DEPLOY_ROOT/etc/systemd/system/sew-run.service" | cut -c1-8)" >> "$STUB_LOG" ;;
esac
exit 0
"""
)

_VENV_PYTHON = (
    _LOG_STUB.format(name="venv-python")
    + """
for arg in "$@"; do
  case "$arg" in
    status) exit "$(cat "$STUB_STATE/status_exit" 2>/dev/null || echo 10)" ;;
    *engine_pin.py|compileall)
      echo "checkout-saw $(git -C "$SEW_DEPLOY_ROOT/opt/sew/Sagittarius_Elite_Warrior" rev-parse --short HEAD)" >> "$STUB_LOG" ;;
  esac
done
exit 0
"""
)

_VENV_PIP = (
    _LOG_STUB.format(name="venv-pip")
    + """
[ -e "$STUB_STATE/pip_fails" ] && exit 1
echo "pip-saw checkout=$(git -C "$SEW_DEPLOY_ROOT/opt/sew/Sagittarius_Elite_Warrior" rev-parse --short HEAD) unit=$(md5sum "$SEW_DEPLOY_ROOT/etc/systemd/system/sew-run.service" 2>/dev/null | cut -c1-8) umask=$(umask)" >> "$STUB_LOG"
exit 0
"""
)

_PYTHON312 = (
    _LOG_STUB.format(name="python3.12")
    + """
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  cp "$STUB_BIN/venv-python" "$3/bin/python"
  cp "$STUB_BIN/venv-pip" "$3/bin/pip"
  exit 0
fi
case "$*" in
  *ensurepip*) [ -e "$STUB_STATE/no_venv_module" ] && exit 1 ;;
esac
exit 0
"""
)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


@dataclass
class Run:
    code: int
    out: str
    err: str


class DeployWorld:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.root = tmp / "root"
        self.state = tmp / "stub-state"
        self.bin = tmp / "stub-bin"
        self.log = tmp / "calls.log"
        self.origin = tmp / "origin"
        for directory in (
            self.state,
            self.bin,
            self.root / "run" / "systemd" / "system",
        ):
            directory.mkdir(parents=True)
        (self.root / "etc" / "systemd" / "system").mkdir(parents=True)
        (self.root / "etc").mkdir(exist_ok=True)
        (self.root / "etc" / "os-release").write_text(
            'NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="24.04"\n', encoding="utf-8"
        )
        self.log.write_text("", encoding="utf-8")
        self._stubs()
        self._origin()

    # --- the stand-ins ------------------------------------------------------------------

    def _stubs(self) -> None:
        _write(self.bin / "systemctl", _SYSTEMCTL)
        _write(self.bin / "venv-python", _VENV_PYTHON)
        _write(self.bin / "venv-pip", _VENV_PIP)
        _write(self.bin / "python3.12", _PYTHON312)
        _write(
            self.bin / "timedatectl",
            _LOG_STUB.format(name="timedatectl")
            + 'cat "$STUB_STATE/ntp" 2>/dev/null || echo yes\n',
        )
        _write(
            self.bin / "useradd",
            _LOG_STUB.format(name="useradd") + ': > "$STUB_STATE/account"\n',
        )
        _write(
            self.bin / "getent",
            "#!/bin/sh\n"
            '[ -e "$STUB_STATE/account" ] && echo "sew:x:999:999::/var/lib/sew:/usr/sbin/nologin"\n'
            '[ -e "$STUB_STATE/account" ]\n',
        )
        _write(self.bin / "apt-get", _LOG_STUB.format(name="apt-get"))
        _write(
            self.bin / "sudo",
            "#!/bin/sh\n"
            'if [ "$1" = "-u" ]; then printf "sudo-as %s\\n" "$2" >> "$STUB_LOG"; shift 2; fi\n'
            'exec "$@"\n',
        )
        _write(
            self.bin / "journalctl",
            _LOG_STUB.format(name="journalctl")
            + "echo '[preflight] credentials-present: ok'\n"
            "echo '[recovering] bot 44wa1x'\n",
        )
        _write(
            self.bin / "ln-check",
            "#!/bin/sh\nexit 0\n",
        )

    def stub(self, name: str, body: str) -> None:
        """Replace or add a stand-in in `PATH`, logging its call first."""
        _write(self.bin / name, _LOG_STUB.format(name=name) + textwrap.dedent(body))

    def set_state(self, name: str, value: str = "") -> None:
        (self.state / name).write_text(value, encoding="utf-8")

    def clear_state(self, name: str) -> None:
        (self.state / name).unlink(missing_ok=True)

    def id_shim(self, uid: str) -> Path:
        shim = self.tmp / f"id-shim-{uid}"
        shim.mkdir(exist_ok=True)
        _write(shim / "id", f"#!/bin/sh\necho {uid}\n")
        return shim

    # --- the origin repository ----------------------------------------------------------

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        done = subprocess.run(
            [require_tool("git"), "-c", "commit.gpgsign=false", *args],
            cwd=cwd or self.origin,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        return done.stdout.strip()

    def _origin(self) -> None:
        self.origin.mkdir()
        self._git("init", "-q", "-b", BRANCH)
        for relative in _RELEASE_FILES:
            target = self.origin / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        config = self.origin / "src" / "config"
        config.mkdir(parents=True)
        (config / "user_config.json").write_text(
            '{"bots.account_loss_cap": ""}\n', encoding="utf-8"
        )
        self.commit("first release")

    def commit(self, message: str, **files: str) -> str:
        """A new commit on the origin; `files` maps a path (with `__` for `/`) to its text."""
        for relative, text in files.items():
            target = self.origin / relative.replace("__", "/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", message)
        return self._git("rev-parse", "HEAD")

    def tag(self, name: str) -> None:
        self._git("tag", name)

    def drop_from_origin(self, relative: str) -> str:
        self._git("rm", "-q", relative)
        self._git("commit", "-q", "-m", f"remove {relative}")
        return self._git("rev-parse", "HEAD")

    # --- the installed host -------------------------------------------------------------

    @property
    def checkout(self) -> Path:
        return self.root / "opt" / "sew" / "Sagittarius_Elite_Warrior"

    @property
    def unit_dir(self) -> Path:
        return self.root / "etc" / "systemd" / "system"

    @property
    def sbin(self) -> Path:
        return self.root / "usr" / "local" / "sbin"

    def head(self) -> str:
        return self._git("rev-parse", "HEAD", cwd=self.checkout)

    def short_head(self) -> str:
        return self._git("rev-parse", "--short", "HEAD", cwd=self.checkout)

    def lines(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines()

    def calls(self, prefix: str) -> list[str]:
        return [line for line in self.lines() if line.startswith(prefix)]

    def snapshot(self) -> dict[str, str]:
        """Every path under the root with its kind and, for a file, its text."""
        found: dict[str, str] = {}
        for path in sorted(self.root.rglob("*")):
            if ".git" in path.parts:
                continue
            relative = str(path.relative_to(self.root))
            if path.is_symlink():
                found[relative] = f"-> {os.readlink(path)}"
            elif path.is_file():
                found[relative] = path.read_text(encoding="utf-8", errors="replace")
            else:
                found[relative] = "dir"
        return found

    def run(
        self,
        script: str,
        *args: str,
        uid: str = "1000",
        extra_env: dict[str, str] | None = None,
        euid: str = "0",
    ) -> Run:
        env = {
            "PATH": f"{self.id_shim(uid)}:{self.bin}:{os.environ['PATH']}",
            "HOME": str(self.tmp),
            "SEW_DEPLOY_ROOT": str(self.root),
            "SEW_DEPLOY_EUID": euid,
            "SEW_DEPLOY_NO_CHOWN": "1",
            "STUB_LOG": str(self.log),
            "STUB_STATE": str(self.state),
            "STUB_BIN": str(self.bin),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        env.update(extra_env or {})
        done = subprocess.run(
            [require_tool("bash"), str(DEPLOY / script), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
            check=False,
        )
        return Run(done.returncode, done.stdout, done.stderr)

    def install(self, *args: str, **kwargs: object) -> Run:
        return self.run("sew-install", "--repo-url", str(self.origin), *args, **kwargs)  # type: ignore[arg-type]

    def update(self, *args: str, **kwargs: object) -> Run:
        self.stand_in_for_sew_backup()
        return self.run("sew-update", *args, **kwargs)  # type: ignore[arg-type]

    def stand_in_for_sew_backup(self) -> None:
        """Replace the link to the real `sew-backup` (which refuses a non-root caller, as it
        must) by a script that logs its environment and the checkout it ran against; the real
        one is tested by `test_sew_backup.py`. Does nothing before an install."""
        link = self.sbin / "sew-backup"
        if not self.sbin.is_dir() or (link.exists() and not link.is_symlink()):
            return
        link.unlink(missing_ok=True)
        _write(
            link,
            "#!/bin/sh\n"
            '[ -d "$SEW_BACKUP_ROOT/var/lib/sew/state" ] || { echo "sew-backup: no state" >&2; exit 2; }\n'
            'echo "sew-backup root=$SEW_BACKUP_ROOT dir=$SEW_BACKUP_DIR '
            f'head=$(git -C {self.checkout} rev-parse --short HEAD)" >> "$STUB_LOG"\n',
        )

    def running_with_a_new_release(self, new_unit: str) -> str:
        """An installed, running host with a bot file, and a second release that changes the unit."""
        self.installed()
        self.set_state("active")
        bots = self.root / "var" / "lib" / "sew" / "state" / "bots"
        bots.mkdir(parents=True)
        (bots / "44wa1x.json").write_text('{"id": "44wa1x"}', encoding="utf-8")
        return self.commit("release 2", **{"deploy__linux__sew-run.service": new_unit})

    def installed(self) -> DeployWorld:
        """A host the install has run on, its log cleared, the service not running."""
        done = self.install()
        assert done.code == 0, done.err + done.out
        self.stand_in_for_sew_backup()
        self.log.write_text("", encoding="utf-8")
        return self
