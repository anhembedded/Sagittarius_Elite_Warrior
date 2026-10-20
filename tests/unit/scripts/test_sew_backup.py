"""`BOT-204` - `deploy/linux/sew-backup`, moved out of the runbook's heredoc into a file.

Run for real under bash against a temporary root (`SEW_BACKUP_ROOT`, `SEW_BACKUP_DIR`); `id` is
stood in for, as in the other script tests. `systemctl` is a stand-in too.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tarfile
import time
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.scripts.deploy_world import DEPLOY
from Sagittarius_Elite_Warrior.tests.unit.scripts.service_files_world import (
    require_tool,
)

SCRIPT = DEPLOY / "sew-backup"


class Host:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.root = tmp / "root"
        self.dest = tmp / "backups"
        state = self.root / "var" / "lib" / "sew" / "state"
        (state / "bots").mkdir(parents=True)
        (state / "control").mkdir()
        (state / "bots" / "44wa1x.json").write_text('{"id":"44wa1x"}', encoding="utf-8")
        (state / "bots" / "55xb2y.json").write_text('{"id":"55xb2y"}', encoding="utf-8")
        (state / "bots" / "scratch.json.tmp").write_text("half", encoding="utf-8")
        (state / "loss_cap.json").write_text("{}", encoding="utf-8")
        (state / "alerts.sqlite3").write_text("queue", encoding="utf-8")
        (state / "alerts.sqlite3-wal").write_text("queue", encoding="utf-8")
        (state / "health.json").write_text("{}", encoding="utf-8")
        (state / "instance.lock").write_text("1", encoding="utf-8")
        (state / "control" / "cmd.json").write_text("{}", encoding="utf-8")
        config = (
            self.root / "opt" / "sew" / "Sagittarius_Elite_Warrior" / "src" / "config"
        )
        config.mkdir(parents=True)
        (config / "user_config.json").write_text(
            '{"bots.account_loss_cap": "500 USDT"}', encoding="utf-8"
        )
        drop_in = self.root / "etc" / "systemd" / "system" / "sew-run.service.d"
        drop_in.mkdir(parents=True)
        (drop_in / "plan.conf").write_text("[Service]\n", encoding="utf-8")
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.set_uid("0")
        systemctl = self.bin / "systemctl"
        systemctl.write_text('#!/bin/sh\n[ -e "$ACTIVE" ]\n', encoding="utf-8")
        systemctl.chmod(0o755)

    def set_uid(self, uid: str) -> None:
        tool = self.bin / "id"
        tool.write_text(f"#!/bin/sh\necho {uid}\n", encoding="utf-8")
        tool.chmod(0o755)

    def run(
        self, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "SEW_BACKUP_ROOT": str(self.root),
            "SEW_BACKUP_DIR": str(self.dest),
            "ACTIVE": str(self.tmp / "no-such-file"),
        }
        env.update(extra_env or {})
        return subprocess.run(
            [require_tool("bash"), str(SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )

    def archives(self) -> list[Path]:
        return sorted(self.dest.glob("sew-state-*.tar.gz"))


def _names(archive: Path) -> list[str]:
    with tarfile.open(archive) as tar:
        return tar.getnames()


def test_it_writes_a_dated_private_archive_of_what_a_restore_needs(
    tmp_path: Path,
) -> None:
    host = Host(tmp_path)

    done = host.run()

    assert done.returncode == 0, done.stderr
    [archive] = host.archives()
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600
    assert stat.S_IMODE(host.dest.stat().st_mode) == 0o700
    names = _names(archive)
    assert "var/lib/sew/state/bots/44wa1x.json" in names
    assert "var/lib/sew/state/bots/55xb2y.json" in names
    assert "var/lib/sew/state/loss_cap.json" in names
    assert "opt/sew/Sagittarius_Elite_Warrior/src/config/user_config.json" in names
    assert "etc/systemd/system/sew-run.service.d/plan.conf" in names
    assert "2 bot file(s)" in done.stdout


def test_it_leaves_out_what_the_next_start_rewrites_and_every_secret(
    tmp_path: Path,
) -> None:
    host = Host(tmp_path)
    secrets = host.root / "etc" / "sew"
    (secrets / "credentials").mkdir(parents=True)
    (secrets / "credentials" / "futures_mainnet_api_key").write_text(
        "SECRET", encoding="utf-8"
    )
    (secrets / "sew.env").write_text(
        "BINANCE_SPOT_TESTNET_API_KEY=SECRET", encoding="utf-8"
    )

    host.run()

    names = _names(host.archives()[0])
    for left_out in (
        "alerts.sqlite3",
        "health.json",
        "instance.lock",
        "control",
        "scratch.json.tmp",
    ):
        assert not [n for n in names if left_out in n], left_out
    assert not [
        n for n in names if "etc/sew" in n or "credentials" in n or "sew.env" in n
    ]


def test_it_refuses_unless_root_and_without_a_state_directory(tmp_path: Path) -> None:
    host = Host(tmp_path)
    host.set_uid("1000")
    refused = host.run()
    host.set_uid("0")
    (host.root / "var" / "lib" / "sew" / "state" / "bots" / "44wa1x.json").unlink()
    for path in sorted(
        (host.root / "var" / "lib" / "sew" / "state").rglob("*"), reverse=True
    ):
        path.unlink() if path.is_file() else path.rmdir()
    (host.root / "var" / "lib" / "sew" / "state").rmdir()
    missing = host.run()

    assert refused.returncode == 2
    assert "run this as root" in refused.stderr
    assert missing.returncode == 2
    assert "does not exist" in missing.stderr
    assert host.archives() == []


def test_a_running_host_gets_the_hot_copy_warning_and_still_a_whole_archive(
    tmp_path: Path,
) -> None:
    host = Host(tmp_path)
    (tmp_path / "active").write_text("", encoding="utf-8")

    done = host.run({"ACTIVE": str(tmp_path / "active")})

    assert done.returncode == 0, done.stderr
    assert "hot copy" in done.stderr
    assert len(host.archives()) == 1


def test_archives_older_than_the_keep_window_are_removed_and_newer_kept(
    tmp_path: Path,
) -> None:
    host = Host(tmp_path)
    host.dest.mkdir(mode=0o700)
    old = host.dest / "sew-state-20200101T000000Z.tar.gz"
    new = host.dest / "sew-state-20261019T000000Z.tar.gz"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    long_ago = time.time() - 40 * 86400
    os.utime(old, (long_ago, long_ago))

    done = host.run({"SEW_BACKUP_KEEP_DAYS": "30"})

    assert done.returncode == 0, done.stderr
    assert not old.exists()
    assert new.exists()


def test_the_timer_runs_the_linked_script_daily() -> None:
    service = (DEPLOY / "sew-backup.service").read_text(encoding="utf-8")
    timer = (DEPLOY / "sew-backup.timer").read_text(encoding="utf-8")

    assert "ExecStart=/usr/local/sbin/sew-backup" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*-*-* 03:17:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
