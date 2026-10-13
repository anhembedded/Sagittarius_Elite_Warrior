"""`EPIC-038H` — an upgrade or a rollback that meets a bot file it cannot read.

The real `JsonBotStore` on a directory holding one bot this build writes and one a newer
build wrote (`schema_version` 99). The restore service must leave the newer file byte for
byte as it found it, and the pre-flight must name it, so the person upgrading a server
learns before the host serves that a bot is missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import CheckStatus
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_files_readable_check import (
    BotFilesReadableCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)

_NEWER = {"schema_version": 99, "definition": {"bot_id": "newer1"}, "future": "field"}


def _seeded(directory: Path) -> tuple[JsonBotStore, Path]:
    store = JsonBotStore(directory)
    store.save(sample_bot("abc123"))
    newer = directory / "newer1.json"
    newer.write_text(json.dumps(_NEWER, indent=1), encoding="utf-8")
    return store, newer


def test_the_preflight_names_a_bot_file_this_build_cannot_read(tmp_path: Path) -> None:
    store, _ = _seeded(tmp_path)

    result = BotFilesReadableCheck(store).run(PreflightScope())

    assert result.status is CheckStatus.WARN
    [finding] = result.findings
    assert "newer1" in finding.subject
    assert "schema_version" in finding.reason
    assert "99" in finding.reason
    assert "rollback" in finding.remedy


def test_a_readable_directory_passes(tmp_path: Path) -> None:
    store = JsonBotStore(tmp_path)
    store.save(sample_bot("abc123"))

    result = BotFilesReadableCheck(store).run(PreflightScope())

    assert result.status is CheckStatus.PASS


def test_restoring_leaves_a_newer_file_byte_for_byte_and_the_readable_bot_loaded(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, newer = _seeded(tmp_path)
    before = newer.read_bytes()

    BotRestoreService(store, FakeBotClock()).restore_all()

    assert newer.read_bytes() == before
    assert "newer1.json was not restored: unknown schema_version 99" in caplog.text
    reading = store.load_all()
    assert [stored.bot.bot_id.value for stored in reading.bots] == ["abc123"]
    assert [refused.name for refused in reading.refused] == ["newer1.json"]
