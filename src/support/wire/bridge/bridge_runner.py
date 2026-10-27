"""`EPIC-047C` — give a `BridgeSession` real pipes, a clock and threads, and run it to its end.

Three threads and no socket: one reads standard input a line at a time and hands it over, the
main thread feeds the session and ticks it, and a command's wait runs on a short-lived thread of
its own (the host answers in about a second; the rest of the session must not stand still). The
session ends when it says so, when the input closes, or when the output does.

A line longer than `MAX_LINE_BYTES` is a protocol violation, not a buffer to grow: the bridge is
the only door from a desktop to a real-money host and reads what it is given with a bound.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Final, TextIO

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_ENDED,
    POLL_S,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    BridgeSession,
    SessionPorts,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

logger = logging.getLogger("App.LinkBridge")

MAX_LINE_BYTES: Final = 1_048_576
#: Longest the main thread waits for a line before it looks at the clock and the files again.
_TICK_S: Final = POLL_S / 2

_END = object()
_TOO_LONG = object()


def serve(
    stdin: TextIO,
    stdout: TextIO,
    roots: WireRoots,
    app_version: str,
    ports: SessionPorts,
    *,
    monotonic: Callable[[], float] = time.monotonic,
    **timings: float,
) -> int:
    """Run one session on `stdin` and `stdout`; the exit status of the bridge process."""
    inbox: queue.Queue[object] = queue.Queue()
    threading.Thread(
        target=_read_lines, args=(stdin, inbox), name="link-bridge-reader", daemon=True
    ).start()
    output_closed = threading.Event()

    def emit(message: dict[str, object]) -> None:
        # Encoding is outside the `try`: a message that cannot be encoded is the session's failure,
        # not a closed pipe.
        line = json.dumps(message, separators=(",", ":"), allow_nan=False) + "\n"
        try:
            stdout.write(line)
            stdout.flush()
        except (BrokenPipeError, ValueError):
            output_closed.set()

    def spawn(work: Callable[[], None]) -> None:
        threading.Thread(target=work, name="link-bridge-command", daemon=True).start()

    session = BridgeSession(roots, app_version, ports, emit, spawn, **timings)
    session.begin(monotonic())
    while session.exit_code is None:
        if output_closed.is_set():
            session.ended()
            break
        _step(session, inbox, monotonic)
    return EXIT_ENDED if session.exit_code is None else session.exit_code


def _step(
    session: BridgeSession, inbox: queue.Queue[object], monotonic: Callable[[], float]
) -> None:
    try:
        item = inbox.get(timeout=_TICK_S)
    except queue.Empty:
        session.tick(monotonic())
        return
    if item is _END:
        session.ended()
    elif item is _TOO_LONG:
        session.violate_line_too_long()
    elif isinstance(item, str):
        session.feed(item, monotonic())
        session.tick(monotonic())


def _read_lines(stdin: TextIO, inbox: queue.Queue[object]) -> None:
    try:
        while True:
            line = stdin.readline(MAX_LINE_BYTES + 1)
            if not line:
                inbox.put(_END)
                return
            if len(line) > MAX_LINE_BYTES:
                inbox.put(_TOO_LONG)
                return
            if line.strip():
                inbox.put(line)
    except (OSError, ValueError):
        inbox.put(_END)
