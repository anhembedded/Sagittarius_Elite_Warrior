"""`EPIC-047C` — one session of the bridge: the protocol, driven by lines in and a clock.

The bridge is a second process on the VPS host that `sshd` starts for each session behind a
forced-command key, speaking newline-delimited JSON on stdin and stdout (remote link record D2,
D3). This class is its whole behaviour and has no I/O of its own: `feed` takes a line, `tick`
takes the time, and both answer through `emit`. `bridge_runner` gives it real pipes and threads;
a test gives it a list and a number.

@par The conversation
  1. **hello** — before anything is read, the bridge says its protocol, app version and one digest
     per wire root, and how often it wants a ping (`heartbeat_s`) and how long it tolerates
     silence (`idle_watchdog_s`). The desktop answers with its own hello.
  2. **welcome**, or **refused** — the same build gets a welcome. A difference gets
     `Refusal.to_wire()` and exit status 3 *before the bots' files are read* (decision D6; there is
     no read-only mode across versions in v1). A hello that is not one gets status 4.
  3. **calls** — `{"type":"call","id":n,"method":…,"params":{…}}`, answered by
     `{"type":"result","id":n,"data":…}` or `{"type":"error","id":n,"code":…,"message":…}`:
       · `snapshot` — every bot as `sew.bot-list/1`, the revision of each, the latest host facts
         and the sequence number of the last event sent;
       · `subscribe` — from now on, one **event** per change;
       · `command` — `{"request_id": <32 hex>, "request": sew.host-control-request/1,
         "wait_s": n}` through the host's control door; the reply is `sew.host-control-reply/1`.
  4. **events** — `{"type":"event","seq":n,"kind":"bot",…}` for every write to a bot's file (found
     by listing the directory every `POLL_S`), `kind":"facts"` when the host-facts file's revision
     or liveness changes.
  5. **ping**/**pong** — the desktop pings at a third of the watchdog; any line it sends resets it.

@par Revisions
A bot's revision is the bridge's own counter for that bot, +1 each time its file's stamp changes
(a first sighting is 1, a deletion is a change). It lives as long as the bridge: the desktop makes
a fresh `RevisionGate` for each connection and takes a snapshot first, so a restarted bridge's
counters never meet an older one's. The bridge is single-threaded for the bots: snapshot and events
come from one sequence, so the gate sees them in an order that cannot contradict itself. Only a
command runs on another thread, and only its result races the rest.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_commands import (
    BridgeCommands,
    Send,
    Spawn,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_ENDED,
    EXIT_IDLE,
    EXIT_INTERNAL,
    EXIT_PROTOCOL,
    EXIT_REFUSED,
    FACTS_LOOK_S,
    HEARTBEAT_S,
    HELLO_TIMEOUT_S,
    IDLE_WATCHDOG_S,
    MESSAGE_LIMIT,
    POLL_S,
    CallError,
    error_message,
    parse_line,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    BotReading,
    FactsLook,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bots import (
    IBridgeBots,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_facts import (
    IBridgeFacts,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_command_door import (
    ICommandDoor,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import (
    Hello,
    hello_of,
    judge,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots

logger = logging.getLogger("App.LinkBridge")


@dataclass(frozen=True, slots=True)
class SessionPorts:
    bots: IBridgeBots
    facts: IBridgeFacts
    door: ICommandDoor


class BridgeSession:
    def __init__(
        self,
        roots: WireRoots,
        app_version: str,
        ports: SessionPorts,
        emit: Send,
        spawn: Spawn,
        *,
        heartbeat_s: float = HEARTBEAT_S,
        idle_watchdog_s: float = IDLE_WATCHDOG_S,
        hello_timeout_s: float = HELLO_TIMEOUT_S,
    ) -> None:
        self._roots = roots
        self._hello = hello_of(roots, app_version)
        self._ports = ports
        self._emit = emit
        self._heartbeat_s = heartbeat_s
        self._idle_watchdog_s = idle_watchdog_s
        self._hello_timeout_s = hello_timeout_s
        self._write_lock = threading.Lock()
        self._commands = BridgeCommands(roots, ports.door, spawn, self._send)
        self._greeted = False
        self._started_at = 0.0
        self._last_inbound = 0.0
        self._next_poll = 0.0
        self._next_facts = 0.0
        self._subscribed = False
        self._seq = 0
        self._seen: dict[str, tuple[int, ...]] = {}
        self._revision: dict[str, int] = {}
        self._facts_key: tuple[int, str] | None = None
        self.exit_code: int | None = None
        self.events_sent = 0
        self._calls_served = 0

    @property
    def calls_served(self) -> int:
        return self._calls_served + self._commands.served

    # -- the two inputs -------------------------------------------------------------------

    def begin(self, now: float) -> None:
        """Say hello. Nothing is read from the host yet."""
        self._started_at = self._last_inbound = now
        self._send({"type": "hello", **self._hello.to_wire()} | self._timings())
        logger.info(
            "[link-bridge] hello sent: protocol %s, app version %s, heartbeat %.1f s, watchdog %.1f s",
            self._hello.protocol,
            self._hello.app_version,
            self._heartbeat_s,
            self._idle_watchdog_s,
        )

    def feed(self, line: str, now: float) -> None:
        """One line from the desktop."""
        if self.exit_code is not None:
            return
        self._last_inbound = now
        try:
            document = parse_line(line)
            if not self._greeted:
                self._greet(document, now)
                return
            self._serve(document)
        except CallError as failure:
            self._violate(failure.code, failure.message)
        except Exception:  # noqa: BLE001 - last resort at the seam: a port raised; the cause goes to the log
            self._fail_internally()

    def tick(self, now: float) -> None:
        """The clock moved: end a silent session, look at the files."""
        if self.exit_code is not None:
            return
        try:
            self._tick(now)
        except Exception:  # noqa: BLE001 - last resort at the seam: a port raised; the cause goes to the log
            self._fail_internally()

    def _tick(self, now: float) -> None:
        if not self._greeted:
            if now - self._started_at > self._hello_timeout_s:
                self._violate(
                    "no_hello", f"no hello within {self._hello_timeout_s:g} s"
                )
            return
        if now - self._last_inbound > self._idle_watchdog_s:
            logger.warning(
                "[link-bridge] idle for %.1f s, over the %.1f s watchdog: the session ends",
                now - self._last_inbound,
                self._idle_watchdog_s,
            )
            self._end(EXIT_IDLE)
            return
        if now >= self._next_poll:
            self._next_poll = now + POLL_S
            self._poll(announce=True)
        if now >= self._next_facts:
            self._next_facts = now + FACTS_LOOK_S
            self._look_at_facts(announce=True)

    def violate_line_too_long(self) -> None:
        """The reader met a line over its bound."""
        self._violate(
            "line_too_long", "a line is far longer than any message of this protocol"
        )

    def ended(self) -> None:
        """The input closed: the desktop is gone."""
        if self.exit_code is None:
            self._end(EXIT_ENDED)

    # -- the conversation -----------------------------------------------------------------

    def _greet(self, document: dict[str, object], now: float) -> None:
        if document.get("type") != "hello":
            raise CallError("no_hello", "the first line must be the desktop's hello")
        body = {key: value for key, value in document.items() if key != "type"}
        try:
            desk = Hello.from_wire(body)
        except WireDecodeError as failure:
            raise CallError("bad_hello", str(failure)[:MESSAGE_LIMIT]) from failure
        refusal = judge(self._hello, desk)
        if refusal is not None:
            self._send(refusal.to_wire())
            logger.warning(
                "[link-bridge] refused before any read: %s", ", ".join(refusal.differs)
            )
            self._end(EXIT_REFUSED)
            return
        self._greeted = True
        self._send({"type": "welcome", **self._timings()})
        self._next_poll = self._next_facts = now
        self._poll(announce=False)
        self._look_at_facts(announce=False)

    def _serve(self, document: dict[str, object]) -> None:
        kind = document.get("type")
        if kind == "ping":
            self._send({"type": "pong"})
        elif kind == "call":
            self._call(document)
        else:
            raise CallError("unknown_message", f"no message of type {str(kind)[:40]!r}")

    def _call(self, document: dict[str, object]) -> None:
        call_id, method, params = (
            document.get("id"),
            document.get("method"),
            document.get("params", {}),
        )
        if type(call_id) is not int or call_id < 1:
            raise CallError("bad_call", "a call has an id, a whole number from 1")
        if type(method) is not str or type(params) is not dict:
            raise CallError("bad_call", "a call has a method and an object of params")
        try:
            data = self._answer(call_id, method, params)
        except CallError as failure:
            self._send(error_message(call_id, failure.code, failure.message))
            return
        if data is not None:
            self._send({"type": "result", "id": call_id, "data": data})
        self._calls_served += 1

    def _answer(
        self, call_id: int, method: str, params: dict[str, object]
    ) -> dict[str, object] | None:
        if method == "snapshot":
            return self._snapshot()
        if method == "subscribe":
            self._subscribed = True
            return {"seq": self._seq}
        if method == "command":
            self._commands.start(call_id, params)
            return None
        raise CallError("unknown_method", f"no method {method[:40]!r}")

    # -- reads ----------------------------------------------------------------------------

    def _snapshot(self) -> dict[str, object]:
        self._poll(announce=True)
        listing = self._ports.bots.listing()
        look = self._ports.facts.look()
        self._facts_key = _facts_key(look)
        return {
            "seq": self._seq,
            "list": self._roots.encode(listing.root, listing.value),
            "revisions": {
                bot_id: self._revision[bot_id] for bot_id in sorted(self._seen)
            },
            "facts": self._facts_payload(look),
        }

    def _poll(self, *, announce: bool) -> None:
        stamps = self._ports.bots.stamps()
        changed = [
            bot_id
            for bot_id in sorted(stamps)
            if self._seen.get(bot_id) != stamps[bot_id]
        ]
        gone = sorted(self._seen.keys() - stamps.keys())
        for bot_id in (*changed, *gone):
            if bot_id in stamps:
                self._seen[bot_id] = stamps[bot_id]
            else:
                del self._seen[bot_id]
            self._revision[bot_id] = self._revision.get(bot_id, 0) + 1
            if announce and self._subscribed:
                reading = (
                    self._ports.bots.read(bot_id) if bot_id in stamps else BotReading()
                )
                self._bot_event(bot_id, reading)

    def _bot_event(self, bot_id: str, reading: BotReading) -> None:
        revision = self._revision[bot_id]
        bot = (
            None
            if reading.bot is None
            else self._roots.encode(
                reading.bot.root, reading.bot.value, revision=revision
            )
        )
        self._event(
            {
                "kind": "bot",
                "bot_id": bot_id,
                "revision": revision,
                "bot": bot,
                "refused": reading.refused,
            }
        )

    def _look_at_facts(self, *, announce: bool) -> None:
        look = self._ports.facts.look()
        key = _facts_key(look)
        if key == self._facts_key:
            return
        self._facts_key = key
        if announce and self._subscribed:
            self._event({"kind": "facts", **self._facts_payload(look)})

    def _facts_payload(self, look: FactsLook) -> dict[str, object]:
        document = (
            None
            if look.document is None
            else self._roots.encode(look.document.root, look.document.value)
        )
        return {
            "state": look.state.value,
            "revision": look.revision,
            "age_s": look.age_s,
            "problem": look.problem,
            "document": document,
        }

    def _event(self, body: dict[str, object]) -> None:
        self._seq += 1
        self.events_sent += 1
        self._send({"type": "event", "seq": self._seq, **body})

    # -- output ---------------------------------------------------------------------------

    def _timings(self) -> dict[str, object]:
        return {
            "heartbeat_s": self._heartbeat_s,
            "idle_watchdog_s": self._idle_watchdog_s,
        }

    def _send(self, message: dict[str, object]) -> None:
        with self._write_lock:
            self._emit(message)

    def _violate(self, code: str, message: str) -> None:
        logger.warning("[link-bridge] protocol violation (%s): %s", code, message)
        self._send({"type": "refused", "reason": code, "differs": [], "words": message})
        self._end(EXIT_PROTOCOL)

    def _fail_internally(self) -> None:
        """A failure nobody planned for: the cause is logged with its traceback, the desktop gets a word
        (never the exception's text) and the process ends with its own status, not a bare traceback."""
        logger.exception("[link-bridge] the session failed on an unforeseen error")
        self._send(
            {
                "type": "refused",
                "reason": "internal",
                "differs": [],
                "words": "the bridge failed on an unforeseen error; its log on the host says why",
            }
        )
        self._end(EXIT_INTERNAL)

    def _end(self, code: int) -> None:
        self.exit_code = code
        logger.info(
            "[link-bridge] session ended with status %d: %d calls served, %d events sent",
            code,
            self.calls_served,
            self.events_sent,
        )


def _facts_key(look: FactsLook) -> tuple[int, str]:
    return (look.revision, look.state.value)
