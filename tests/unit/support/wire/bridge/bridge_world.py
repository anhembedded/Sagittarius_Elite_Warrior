"""`EPIC-047C` - what the bridge session's tests share: ports shaped from the ABCs, a clock that is a number, a desk."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    CANDLE_WINDOW_ROOT,
)
from Sagittarius_Elite_Warrior.src.shell.wire_roots import link_roots
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    BridgeSession,
    SessionPorts,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    BotReading,
    FactsLook,
    FactsState,
    Wired,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bots import (
    IBridgeBots,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    CandleQuery,
    IBridgeCandles,
    UnknownCandleSeriesError,
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
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_market_data import (
    full_candle_window,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_host_facts,
)

ROOTS = link_roots()
VERSION = "9.9.9"
REQUEST_ID = "0123456789abcdef0123456789abcdef"
SNAPSHOT_ROOT = "sew.bot-snapshot/1"
FACTS_ROOT = "sew.host-facts-document/1"


class FakeBots(IBridgeBots):
    """Files in a dict; a write is `put`, a removal is `remove`. Counts how often it was asked."""

    def __init__(self, *bots: BotSnapshot) -> None:
        self._files: dict[str, tuple[tuple[int, ...], BotReading]] = {}
        self._writes = 0
        self.asked = 0
        for bot in bots:
            self.put(bot)

    def put(self, bot: BotSnapshot, *, refused: str = "") -> None:
        self._writes += 1
        reading = (
            BotReading(refused=refused)
            if refused
            else BotReading(Wired(SNAPSHOT_ROOT, bot))
        )
        self._files[bot.bot_id] = ((self._writes,), reading)

    def remove(self, bot_id: str) -> None:
        del self._files[bot_id]

    def stamps(self) -> Mapping[str, tuple[int, ...]]:
        self.asked += 1
        return MappingProxyType({k: stamp for k, (stamp, _) in self._files.items()})

    def read(self, bot_id: str) -> BotReading:
        self.asked += 1
        return self._files[bot_id][1]

    def listing(self) -> Wired:
        self.asked += 1
        bots = tuple(
            r.bot.value  # type: ignore[union-attr]
            for _, r in self._files.values()
            if r.bot is not None
        )
        return Wired("sew.bot-list/1", BotList(bots))  # type: ignore[arg-type]


class FakeFacts(IBridgeFacts):
    def __init__(self) -> None:
        self.look_now = FactsLook(
            FactsState.LIVE,
            revision=41,
            age_s=3.0,
            document=Wired(FACTS_ROOT, full_host_facts()),
        )
        self.asked = 0

    def look(self) -> FactsLook:
        self.asked += 1
        return self.look_now

    def host_wrote(self, revision: int) -> None:
        document = full_host_facts()
        document = replace(document, header=replace(document.header, revision=revision))
        self.look_now = FactsLook(
            FactsState.LIVE, revision, 0.5, Wired(FACTS_ROOT, document)
        )


class FakeDocument(IBridgeFacts):
    """A host file the test moves: one root, a value and a revision. Counts how often it was asked."""

    def __init__(self, root: str, value: object, revision: int = 7) -> None:
        self._root = root
        self.look_now = FactsLook(FactsState.LIVE, revision, 0.2, Wired(root, value))
        self.asked = 0

    def look(self) -> FactsLook:
        self.asked += 1
        return self.look_now

    def host_wrote(self, value: object, revision: int) -> None:
        self.look_now = FactsLook(
            FactsState.LIVE, revision, 0.1, Wired(self._root, value)
        )


class FakeCandles(IBridgeCandles):
    """The host's candle store as the test seeds it; remembers what it was asked."""

    def __init__(self) -> None:
        self.asked: list[CandleQuery] = []
        self.answer = Wired(CANDLE_WINDOW_ROOT, full_candle_window())
        self.refusal: UnknownCandleSeriesError | None = None

    def window(self, query: CandleQuery) -> Wired:
        self.asked.append(query)
        if self.refusal is not None:
            raise self.refusal
        return self.answer


class FakeDoor(ICommandDoor):
    def __init__(self) -> None:
        self.sent: list[tuple[str, HostControlRequest, float]] = []
        self.reply = HostControlReply(
            HostControlStatus.DONE, "stopped", "c" * 32, "b-0001"
        )
        self.failure: Exception | None = None

    def send(
        self, request_id: str, request: HostControlRequest, wait_s: float
    ) -> HostControlReply:
        self.sent.append((request_id, request, wait_s))
        if self.failure is not None:
            raise self.failure
        return self.reply


class Desk:
    """The other end of the pipe: lines in, messages out, and a clock the test moves."""

    def __init__(
        self,
        *,
        bots: FakeBots | None = None,
        spawn: Callable[[Callable[[], None]], None] | None = None,
        documents: Mapping[str, IBridgeFacts] | None = None,
        candles: IBridgeCandles | None = None,
    ) -> None:
        self.bots = bots or FakeBots(full_bot(), minimal_bot())
        self.facts = FakeFacts()
        self.door = FakeDoor()
        self.out: list[dict[str, object]] = []
        self.now = 100.0
        self.deferred: list[Callable[[], None]] = []
        self.session = BridgeSession(
            ROOTS,
            VERSION,
            SessionPorts(self.bots, self.facts, self.door, documents or {}, candles),
            self.out.append,
            spawn or (lambda work: work()),
        )
        self._next_id = 0

    # -- the desk's side of the conversation --------------------------------------------

    def greet(self, hello: Hello | None = None) -> None:
        self.session.begin(self.now)
        self.send_hello(hello or hello_of(ROOTS, VERSION))

    def send_hello(self, hello: Hello) -> None:
        self.feed({"type": "hello", **hello.to_wire()})

    def feed(self, message: dict[str, object]) -> None:
        self.session.feed(json.dumps(message), self.now)

    def call(self, method: str, **params: object) -> int:
        self._next_id += 1
        self.feed(
            {"type": "call", "id": self._next_id, "method": method, "params": params}
        )
        return self._next_id

    def advance(self, seconds: float) -> None:
        self.now += seconds
        self.session.tick(self.now)

    # -- reading what the bridge said -----------------------------------------------------

    def sent(self, kind: str) -> list[dict[str, object]]:
        return [m for m in self.out if m["type"] == kind]

    def result_of(self, call_id: int) -> dict[str, object]:
        found = [m for m in self.out if m.get("id") == call_id]
        assert len(found) == 1, found
        assert found[0]["type"] == "result", found[0]
        data = found[0]["data"]
        assert isinstance(data, dict)
        return data

    def error_of(self, call_id: int) -> dict[str, object]:
        found = [m for m in self.out if m.get("id") == call_id]
        assert len(found) == 1, found
        assert found[0]["type"] == "error", found[0]
        return found[0]

    def events(self, kind: str) -> list[dict[str, object]]:
        return [m for m in self.sent("event") if m["kind"] == kind]
