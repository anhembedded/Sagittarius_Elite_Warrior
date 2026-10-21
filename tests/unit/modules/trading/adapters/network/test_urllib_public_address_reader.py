"""`BOT-224` — the real reader against a server on the loopback interface (a unit
test may open a loopback connection, `ci-rule.md` §2): the first usable answer wins,
the second service is the fallback, and every way of not getting an address is a
lookup, never an exception."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.network.urllib_public_address_reader import (
    USER_AGENT,
    UrllibPublicAddressReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressFailure,
)

#: A global IPv4 address (TEST-NET ranges are not global, so they would be refused).
PUBLIC = "93.184.216.34"
_TIMEOUT_S = 2.0


class _Server:
    """Answers `GET /<name>` with the status and body a test scripted for it."""

    def __init__(self) -> None:
        self.answers: dict[str, tuple[int, bytes]] = {}
        self.asked: list[str] = []
        self.agents: list[str] = []
        server = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                server.asked.append(self.path)
                server.agents.append(self.headers.get("User-Agent", ""))
                status, body = server.answers[self.path]
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def url(self, name: str) -> str:
        return f"http://127.0.0.1:{self.http.server_address[1]}/{name}"


@pytest.fixture
def server() -> Iterator[_Server]:
    running = _Server()
    yield running
    running.http.shutdown()
    running.http.server_close()


def _closed_port_url() -> str:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return f"http://127.0.0.1:{port}/nobody"


def _reader(*sources: str) -> UrllibPublicAddressReader:
    return UrllibPublicAddressReader(sources, timeout_s=_TIMEOUT_S)


def test_the_first_service_that_answers_gives_the_address_and_the_second_is_not_asked(
    server,
) -> None:
    server.answers = {"/a": (200, f"{PUBLIC}\n".encode()), "/b": (200, b"8.8.8.8")}

    lookup = _reader(server.url("a"), server.url("b")).read()

    assert lookup.address == PUBLIC
    assert server.asked == ["/a"]
    assert server.agents == [USER_AGENT]


def test_a_service_that_answers_an_error_is_skipped_for_the_next(server) -> None:
    server.answers = {"/a": (503, b"busy"), "/b": (200, PUBLIC.encode())}

    lookup = _reader(server.url("a"), server.url("b")).read()

    assert lookup.address == PUBLIC
    assert server.asked == ["/a", "/b"]


def test_a_service_nobody_listens_on_is_skipped_for_the_next(server) -> None:
    server.answers = {"/b": (200, PUBLIC.encode())}

    lookup = _reader(_closed_port_url(), server.url("b")).read()

    assert lookup.address == PUBLIC


def test_no_service_answering_is_unreachable_and_raises_nothing(server) -> None:
    server.answers = {"/a": (500, b"")}

    lookup = _reader(server.url("a"), _closed_port_url()).read()

    assert lookup.address is None
    assert lookup.failure is PublicAddressFailure.UNREACHABLE


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"<html>sign in to the wifi</html>", id="a web page"),
        pytest.param(b"192.168.1.20", id="a LAN address"),
        pytest.param(b"127.0.0.1", id="loopback"),
        pytest.param(
            b"2606:4700:4700::1111", id="IPv6, not the IPv4 a whitelist holds"
        ),
        pytest.param(b"", id="nothing"),
    ],
)
def test_an_answer_that_is_not_a_public_ipv4_address_is_unreadable(
    server, body
) -> None:
    server.answers = {"/a": (200, body), "/b": (200, body)}

    lookup = _reader(server.url("a"), server.url("b")).read()

    assert lookup.address is None
    assert lookup.failure is PublicAddressFailure.UNREADABLE


def test_a_service_that_gave_junk_outweighs_one_that_gave_nothing(server) -> None:
    server.answers = {"/b": (200, b"not an address")}

    lookup = _reader(_closed_port_url(), server.url("b")).read()

    assert lookup.failure is PublicAddressFailure.UNREADABLE
