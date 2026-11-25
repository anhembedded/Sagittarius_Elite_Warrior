"""`EPIC-047G` - the world of the `deploy/linux/sew-link-key` and `sew-bridge-shell` tests.

@details The real scripts run under bash against a temp directory. Every path is an override
(`SEW_LINK_*`); `SEW_LINK_EUID=0` and `SEW_LINK_NO_CHOWN=1` let a test that is not root run the
root-only paths; a passwd-format file stands in for `getent`; `usermod` and `sshd` are stubs that
rewrite that file and print a settable `sshd -T`. `ssh-keygen` is the real one: a key is accepted
only when it says so.
"""

from __future__ import annotations

import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

DEPLOY = Path(__file__).resolve().parents[3] / "deploy" / "linux"
SCRIPT = DEPLOY / "sew-link-key"
GUARD_REAL = DEPLOY / "sew-bridge-shell"

#: What `sshd -T` says for a well set up host; a test overrides single lines.
SSHD_GOOD = {
    "pubkeyauthentication": "yes",
    "authorizedkeysfile": ".ssh/authorized_keys .ssh/authorized_keys2",
    "usepam": "yes",
    "passwordauthentication": "yes",
    "kbdinteractiveauthentication": "no",
    "allowtcpforwarding": "no",
    "allowagentforwarding": "no",
    "x11forwarding": "no",
    "permittty": "no",
}

_USERMOD = """#!/bin/sh
# usermod -s SHELL ACCOUNT, on the passwd-format file the script was given
[ "$1" = "-s" ] || exit 64
sed -i "s#^\\($3:[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:\\).*#\\1$2#" "$SEW_LINK_PASSWD"
echo "usermod $*" >> "$SEW_LINK_CALLS"
"""

_SSHD = """#!/bin/sh
[ "$1" = "-T" ] || exit 64
cat "$SEW_LINK_SSHD_OUT"
"""


@dataclass
class Run:
    code: int
    out: str
    err: str


class World:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "var-lib-sew"
        self.home.mkdir(mode=0o700)
        self.ssh = self.home / ".ssh"
        self.auth = self.ssh / "authorized_keys"
        self.launcher = root / "opt-sew-bridge"
        self.launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.launcher.chmod(0o755)
        self.guard_source = root / "checkout-sew-bridge-shell"
        self.guard_source.write_text(self.guard_text(), encoding="utf-8")
        self.guard_source.chmod(0o755)
        self.guard = root / "usr-local-sbin-sew-bridge-shell"
        self.shells = root / "shells"
        self.shells.write_text("/bin/sh\n/bin/bash\n", encoding="utf-8")
        self.passwd = root / "passwd"
        self.set_account_shell("/usr/sbin/nologin")
        self.calls = root / "calls.log"
        self.sshd_out = root / "sshd.out"
        self.set_sshd()
        self.usermod = self._stub("usermod", _USERMOD)
        self.sshd = self._stub("sshd", _SSHD)
        self.lock = root / "lock"

    def guard_text(self) -> str:
        """The real guard shell with its launcher line pointing at this world's launcher."""
        text = GUARD_REAL.read_text(encoding="utf-8")
        old = "LAUNCHER=/opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-bridge"
        assert old in text
        return text.replace(old, f"LAUNCHER={self.launcher}")

    def _stub(self, name: str, body: str) -> Path:
        stub = self.root / f"stub-{name}"
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
        return stub

    def set_account_shell(self, shell: str) -> None:
        self.passwd.write_text(
            f"root:x:0:0:root:/root:/bin/bash\nsew:x:990:990::{self.home}:{shell}\n",
            encoding="utf-8",
        )

    def set_sshd(self, **changes: str) -> None:
        values = {**SSHD_GOOD, **changes}
        self.sshd_out.write_text(
            "".join(f"{k} {v}\n" for k, v in values.items() if v), encoding="utf-8"
        )

    def run(
        self,
        *args: str,
        stdin: str = "",
        euid: str = "0",
        real_uid: str = "1000",
        extra_env: dict[str, str] | None = None,
    ) -> Run:
        env = {
            "PATH": f"{self.id_shim(real_uid)}:{os.environ['PATH']}",
            "HOME": str(self.root),
            "TMPDIR": str(self.root),
            "SEW_LINK_HOME": str(self.home),
            "SEW_LINK_LAUNCHER": str(self.launcher),
            "SEW_LINK_GUARD_SOURCE": str(self.guard_source),
            "SEW_LINK_GUARD": str(self.guard),
            "SEW_LINK_SHELLS": str(self.shells),
            "SEW_LINK_PASSWD": str(self.passwd),
            "SEW_LINK_USERMOD": str(self.usermod),
            "SEW_LINK_SSHD": str(self.sshd),
            "SEW_LINK_SSHD_OUT": str(self.sshd_out),
            "SEW_LINK_CALLS": str(self.calls),
            "SEW_LINK_LOCK": str(self.lock),
            "SEW_LINK_EUID": euid,
            "SEW_LINK_NO_CHOWN": "1",
        }
        env.update(extra_env or {})
        done = subprocess.run(
            [require_tool("bash"), str(SCRIPT), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        return Run(done.returncode, done.stdout, done.stderr)

    def id_shim(self, uid: str) -> Path:
        """A directory whose `id -u` answers `uid` (the script is never really root in a test)."""
        shim = self.root / f"id-shim-{uid}"
        shim.mkdir(exist_ok=True)
        tool = shim / "id"
        tool.write_text(f"#!/bin/sh\necho {uid}\n", encoding="utf-8")
        tool.chmod(0o755)
        return shim

    # -- keys ----------------------------------------------------------------------------------

    def make_key(
        self, name: str, comment: str = "desk", kind: str = "ed25519", bits: str = ""
    ) -> Path:
        """A real key pair made by ssh-keygen; the public file's path (the private one sits beside it)."""
        path = self.root / name
        command = [
            require_tool("ssh-keygen"),
            "-q",
            "-t",
            kind,
            "-N",
            "",
            "-C",
            comment,
        ]
        if bits:
            command += ["-b", bits]
        subprocess.run([*command, "-f", str(path)], check=True, capture_output=True)
        return Path(f"{path}.pub")

    def body_of(self, public: Path) -> str:
        return public.read_text(encoding="utf-8").split()[1]

    def auth_lines(self) -> list[str]:
        return (
            self.auth.read_text(encoding="utf-8").splitlines()
            if self.auth.exists()
            else []
        )

    def restricted_line(self, public: Path, comment: str = "desk") -> str:
        kind, body = public.read_text(encoding="utf-8").split()[:2]
        return f'restrict,command="{self.launcher}" {kind} {body} {comment}'

    def mode(self, path: Path) -> int:
        return stat.S_IMODE(path.stat().st_mode)

    def leftovers(self) -> list[str]:
        """Temporary files the script left in the ssh directory or the temp directory."""
        found = (
            [p.name for p in self.ssh.glob(".sew-link-key.*")]
            if self.ssh.exists()
            else []
        )
        return found + [p.name for p in self.root.glob("sew-link-key.*")]
