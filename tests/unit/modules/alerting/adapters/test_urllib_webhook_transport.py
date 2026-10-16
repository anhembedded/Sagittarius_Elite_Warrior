"""`EPIC-036G` — the real transport against a server on the loopback interface
(a unit test may open a loopback connection, `ci-rule.md` §2): it passes the
transport contract the fake passes."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.urllib_webhook_transport import (
    USER_AGENT,
    UrllibWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.contract_webhook_transport import (
    SECRET_PATH,
    TransportUnderTest,
    WebhookTransportContract,
)

#: Short, so the test of a slow server ends quickly; nothing here sleeps.
_TIMEOUT_S = 2.0


class _Server:
    """Answers each POST with the next scripted response and keeps what it got."""

    def __init__(self) -> None:
        self.answers: list[WebhookResponse] = []
        self.bodies: list[str] = []
        self.agents: list[str] = []
        server = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                server.bodies.append(self.rfile.read(length).decode("utf-8"))
                server.agents.append(self.headers.get("User-Agent", ""))
                answer = server.answers.pop(0)
                self.send_response(answer.status)
                for name, value in answer.headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(answer.body)))
                self.end_headers()
                self.wfile.write(answer.body)

            def log_message(self, format: str, *args: object) -> None:
                return  # the test reads the server's lists, not its stderr

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.http.server_address[1]}{SECRET_PATH}"


def _closed_port() -> int:
    """A loopback port nobody listens on."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = int(probe.getsockname()[1])
    probe.close()
    return port


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Server]:
    # A configured proxy must not carry a loopback request away.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    running = _Server()
    running.thread.start()
    try:
        yield running
    finally:
        running.http.shutdown()
        running.http.server_close()


class TestTheUrllibTransport(WebhookTransportContract):
    @pytest.fixture
    def impl(self, server: _Server) -> TransportUnderTest:
        return TransportUnderTest(
            transport=UrllibWebhookTransport(_TIMEOUT_S),
            url=server.url,
            answer=server.answers.append,
            last_body=lambda: server.bodies[-1],
            dead_url=f"http://127.0.0.1:{_closed_port()}{SECRET_PATH}",
            prepare_no_answer=lambda: None,
        )


def test_the_app_names_itself_to_the_server(server: _Server) -> None:
    """Discord refuses Python's default User-Agent."""
    server.answers.append(WebhookResponse(204))

    UrllibWebhookTransport(_TIMEOUT_S).post_json(server.url, {"content": "hi"})

    assert server.agents == [USER_AGENT]
