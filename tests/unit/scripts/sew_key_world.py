"""`BOT-200` — the world of `deploy/linux/sew-key` tests: writes, replaces, removes and lists a server's Binance
keys, and never lets a key into an argument, an output or a leftover file.

@details The real script runs under bash against a temp directory. Its overrides point the
credentials directory, `sew.env` and the unit directory at `tmp_path`, `SEW_KEY_CHECK_COMMAND`
at a stub that stands in for `key check` (no network, no app), and `SEW_KEY_EUID=0` /
`SEW_KEY_NO_CHOWN=1` let a test that is not root run the root-only paths. The stub records the
arguments it was called with and what it read on standard input to the files the test names,
so the tests can prove the key travelled by standard input and by no argument.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

SCRIPT = Path(__file__).resolve().parents[3] / "deploy" / "linux" / "sew-key"

#: Obviously fake, alphanumeric like a real key, and easy to grep for.
KEY = "SENTINELKEY" + "1" * 53
SECRET = "SENTINELSECRET" + "2" * 50
OLD_KEY = "OLDKEY" + "3" * 58
OLD_SECRET = "OLDSECRET" + "4" * 55

_STUB = """#!{python}
import json, os, sys
stdin = sys.stdin.read()
log = os.environ["STUB_LOG"]
with open(log, "w") as handle:
    json.dump({{"argv": sys.argv[1:], "stdin_lines": stdin.count("\\n")}}, handle)
with open(os.environ["STUB_STDIN"], "w") as handle:
    handle.write(stdin)
answer = json.loads(os.environ["STUB_ANSWER"])
print(json.dumps({{"schema": "sew.key/1", "generated_at": "x", "data": answer["data"]}}))
sys.exit(answer["exit"])
"""


def accepted(*venues: str) -> dict[str, object]:
    return {
        "exit": 0,
        "data": {
            "ok": True,
            "venues": list(venues),
            "environment": "mainnet" if "mainnet" in venues[0] else venues[0],
            "refusal": None,
            "message": "",
            "environments": [],
        },
    }


def refused(refusal: str, message: str, exit_code: int = 5) -> dict[str, object]:
    return {
        "exit": exit_code,
        "data": {
            "ok": False,
            "venues": [],
            "environment": None,
            "refusal": refusal,
            "message": message,
            "environments": [
                {
                    "environment": "mainnet",
                    "standing": "unknown",
                    "failure": None,
                    "reason": "-2008 Invalid Api-Key ID.",
                }
            ],
        },
    }


@dataclass
class Run:
    code: int
    out: str
    err: str


class World:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.credentials = root / "credentials"
        self.credentials.mkdir(mode=0o700)
        self.env_file = root / "sew.env"
        self.units = root / "units"
        self.units.mkdir()
        self.stub = root / "stub-key-check"
        self.stub.write_text(_STUB.format(python=sys.executable), encoding="utf-8")
        self.stub.chmod(0o755)
        self.stub_log = root / "stub.log"
        self.stub_stdin = root / "stub.stdin"

    def run(
        self,
        *args: str,
        answers: str = "",
        check: dict[str, object] | None = None,
        euid: str = "0",
        path: str | None = None,
        real_uid: str = "1000",
        extra_env: dict[str, str] | None = None,
    ) -> Run:
        import json

        env = {
            "PATH": f"{self.id_shim(real_uid)}:{path or os.environ['PATH']}",
            "HOME": str(self.root),
            "SEW_KEY_CREDENTIALS_DIR": str(self.credentials),
            "SEW_KEY_ENV_FILE": str(self.env_file),
            "SEW_KEY_UNIT_DIR": str(self.units),
            "SEW_KEY_CHECK_COMMAND": str(self.stub),
            "SEW_KEY_PYTHON": sys.executable,
            "SEW_KEY_EUID": euid,
            "SEW_KEY_NO_CHOWN": "1",
            "STUB_LOG": str(self.stub_log),
            "STUB_STDIN": str(self.stub_stdin),
            "STUB_ANSWER": json.dumps(check or accepted("futures_mainnet")),
        }
        env.update(extra_env or {})
        done = subprocess.run(
            [require_tool("bash"), str(SCRIPT), *args],
            input=answers,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        return Run(done.returncode, done.stdout, done.stderr)

    def id_shim(self, uid: str) -> Path:
        """A directory whose `id -u` answers `uid`: the script is never really root in a test,
        whoever runs the tests, so its refusal of test overrides under a real root can be
        driven by a shim too."""
        shim = self.root / f"id-shim-{uid}"
        shim.mkdir(exist_ok=True)
        tool = shim / "id"
        tool.write_text(f"#!/bin/sh\necho {uid}\n", encoding="utf-8")
        tool.chmod(0o755)
        return shim

    def mainnet(self, venue: str, suffix: str) -> Path:
        return self.credentials / f"{venue}_api_{suffix}"

    def seed_mainnet(
        self, venue: str, key: str = OLD_KEY, secret: str = OLD_SECRET
    ) -> None:
        for suffix, value in (("key", key), ("secret", secret)):
            path = self.mainnet(venue, suffix)
            path.write_text(value, encoding="utf-8")
            path.chmod(0o600)

    def leftovers(self) -> list[str]:
        found = [p.name for p in self.credentials.iterdir() if p.name.startswith(".")]
        found += [p.name for p in self.root.iterdir() if p.name.startswith(".sew-key")]
        return found


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def typed(venue: str) -> str:
    return f"{KEY}\n{SECRET}\n{venue}\n"


def nothing_leaked(run: Run) -> None:
    for sentinel in ("SENTINELKEY", "SENTINELSECRET"):
        assert sentinel not in run.out
        assert sentinel not in run.err
