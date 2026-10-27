"""`EPIC-047C` - the session on real pipes and real threads: end of input, a frozen peer, a line over the bound."""

from __future__ import annotations

import io
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_ENDED,
    EXIT_IDLE,
    EXIT_PROTOCOL,
    EXIT_REFUSED,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_runner import (
    MAX_LINE_BYTES,
    serve,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    SessionPorts,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import (
    PROTOCOL,
    Hello,
    hello_of,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    VERSION,
    FakeBots,
    FakeDoor,
    FakeFacts,
)


def _ports() -> SessionPorts:
    return SessionPorts(FakeBots(), FakeFacts(), FakeDoor())


def _line(message: dict[str, object]) -> str:
    return json.dumps(message) + "\n"


def _hello_line(hello: Hello | None = None) -> str:
    return _line({"type": "hello", **(hello or hello_of(ROOTS, VERSION)).to_wire()})


def _messages(out: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_a_desktop_that_says_hello_pings_and_hangs_up_gets_its_answers_and_a_clean_end() -> (
    None
):
    stdin = io.StringIO(_hello_line() + _line({"type": "ping"}))
    out = io.StringIO()

    status = serve(stdin, out, ROOTS, VERSION, _ports())

    assert status == EXIT_ENDED
    assert [m["type"] for m in _messages(out)] == ["hello", "welcome", "pong"]


def test_a_different_build_is_refused_and_the_status_is_3() -> None:
    stdin = io.StringIO(
        _hello_line(Hello(PROTOCOL, "0.0.1", hello_of(ROOTS, VERSION).root_hashes))
    )
    out = io.StringIO()
    ports = _ports()

    status = serve(stdin, out, ROOTS, VERSION, ports)

    assert status == EXIT_REFUSED
    assert [m["type"] for m in _messages(out)] == ["hello", "refused"]
    assert ports.bots.asked == 0  # type: ignore[attr-defined]


def test_a_line_over_the_bound_is_a_protocol_violation_not_a_buffer_to_grow() -> None:
    stdin = io.StringIO("x" * (MAX_LINE_BYTES + 10) + "\n")
    out = io.StringIO()

    status = serve(stdin, out, ROOTS, VERSION, _ports())

    assert status == EXIT_PROTOCOL
    assert _messages(out)[-1]["reason"] == "line_too_long"


def test_blank_lines_are_ignored() -> None:
    stdin = io.StringIO("\n\n" + _hello_line() + "\n   \n")

    assert serve(stdin, io.StringIO(), ROOTS, VERSION, _ports()) == EXIT_ENDED


class _ClosedOutput(io.StringIO):
    def write(self, text: str) -> int:
        raise BrokenPipeError

    def flush(self) -> None:
        raise BrokenPipeError


def test_an_output_that_closed_ends_the_session() -> None:
    stdin = io.StringIO(_hello_line())

    assert serve(stdin, _ClosedOutput(), ROOTS, VERSION, _ports()) == EXIT_ENDED


@contextmanager
def _open_pipe() -> Iterator[tuple[TextIO, TextIO]]:
    """A pipe whose write end stays open: a peer that froze, with no end of file (no FIN)."""
    read_fd, write_fd = os.pipe()
    reader, writer = os.fdopen(read_fd, "r"), os.fdopen(write_fd, "w")
    try:
        yield reader, writer
    finally:
        writer.close()
        reader.close()


def test_a_frozen_desktop_with_no_end_of_file_is_let_go_by_the_watchdog() -> None:
    """The half-open link of DERISK R5: the peer sent hello and then nothing, and never hung up."""
    with _open_pipe() as (reader, writer):
        writer.write(_hello_line())
        writer.flush()
        out = io.StringIO()
        result: list[int] = []
        worker = threading.Thread(
            target=lambda: result.append(
                serve(
                    reader,
                    out,
                    ROOTS,
                    VERSION,
                    _ports(),
                    heartbeat_s=0.05,
                    idle_watchdog_s=0.15,
                )
            )
        )
        worker.start()
        worker.join(timeout=10)

        assert not worker.is_alive(), "the bridge outlived its watchdog"
        assert result == [EXIT_IDLE]
