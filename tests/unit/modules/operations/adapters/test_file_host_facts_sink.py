"""`EPIC-047B` - the file the host publishes, read the way a second process reads it."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_sink import (
    FileHostFactsSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.file_host_facts_source import (
    FileHostFactsSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.json_host_facts_codec import (
    JsonHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    document,
)


def _pair(path: Path) -> tuple[FileHostFactsSink, FileHostFactsSource]:
    codec = JsonHostFactsCodec()
    return FileHostFactsSink(path, codec), FileHostFactsSource(path, codec)


def test_there_is_no_file_until_the_host_writes_one(tmp_path: Path) -> None:
    _, source = _pair(tmp_path / "state" / "host-facts.json")

    assert source.read_header() is None


def test_what_the_host_publishes_a_reader_finds(tmp_path: Path) -> None:
    sink, source = _pair(tmp_path / "state" / "host-facts.json")

    sink.publish(document(revision=3))

    header = source.read_header()
    assert header is not None
    assert header.revision == 3


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_the_published_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "state" / "host-facts.json"
    sink, _ = _pair(path)

    sink.publish(document())

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_the_published_file_is_the_codecs_bytes(tmp_path: Path) -> None:
    path = tmp_path / "state" / "host-facts.json"
    sink, _ = _pair(path)

    sink.publish(document(revision=5))

    assert json.loads(path.read_bytes())["revision"] == 5


def test_a_file_that_cannot_be_trusted_is_unreadable_not_empty(tmp_path: Path) -> None:
    path = tmp_path / "state" / "host-facts.json"
    path.parent.mkdir()
    path.write_bytes(b"{torn")
    _, source = _pair(path)

    with pytest.raises(HostFactsUnreadableError):
        source.read_header()
