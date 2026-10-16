"""`EPIC-036D1` — Send test: its outcomes in words, off the UI thread, fenced."""

from __future__ import annotations

import logging
import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    REMOVE,
    SAVE,
    SEND_TEST,
    STATUS,
    URL,
    AlertsPage,
    assert_no_secret,
    build_page,
    stored_page,
)


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch)


# -- Send test ----------------------------------------------------------------


def test_send_test_posts_to_the_saved_webhook_and_says_sent(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)

    page.click(SEND_TEST)

    [post] = page.transport.posts
    assert post.url == URL
    assert page.label(STATUS) == "Test message sent to Discord. Check the channel."
    assert_no_secret(page.everything_on_screen(), "the page after a test")


def test_send_test_works_on_a_webhook_saved_after_the_app_started(
    request, monkeypatch, qapp
) -> None:
    page = build_page(request, monkeypatch, running=False)
    page.type_in_field(URL)
    page.click(SAVE)

    page.click(SEND_TEST)

    assert len(page.transport.posts) == 1
    assert "sent to discord" in page.label(STATUS).lower()


def test_send_test_says_plainly_when_discord_refuses_the_webhook(
    request, monkeypatch, qapp
) -> None:
    transport = FakeWebhookTransport(default=WebhookResponse(404, body=b"{}"))
    page = build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL}),
        running=True,
        transport=transport,
    )

    page.click(SEND_TEST)

    assert page.label(STATUS).startswith("Error:")
    assert "Discord refused the webhook message (404)" in page.label(STATUS)
    assert_no_secret(page.everything_on_screen(), "the page after a refused test")


def test_send_test_says_when_discord_did_not_answer(request, monkeypatch, qapp) -> None:
    transport = FakeWebhookTransport(default=WebhookUnreachableError("timed out"))
    page = build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL}),
        running=True,
        transport=transport,
    )

    page.click(SEND_TEST)

    assert "Discord did not answer (timed out)" in page.label(STATUS)


@pytest.mark.parametrize("answer", ["sent", "refused", "silent", "crash"])
def test_the_url_is_in_no_log_record_or_label_on_send_test(
    answer: str, request, monkeypatch, qapp, caplog: pytest.LogCaptureFixture
) -> None:
    transport = FakeWebhookTransport(
        default={
            "sent": WebhookResponse(204),
            "refused": WebhookResponse(404),
            "silent": WebhookUnreachableError("timed out"),
            "crash": WebhookResponse(204),
        }[answer]
    )
    if answer == "crash":

        def explode(url, body):
            raise RuntimeError(f"transport blew up posting to {url}")

        transport.post_json = explode  # type: ignore[method-assign]
    page = build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL}),
        running=True,
        transport=transport,
    )

    with caplog.at_level(logging.DEBUG):
        page.click(SEND_TEST)

    for record in caplog.records:
        rendered = " ".join(
            [record.getMessage(), str(record.args), str(record.exc_text)]
        )
        if record.exc_info:
            rendered += str(record.exc_info[1])
        assert_no_secret(rendered, f"a log record ({record.name}) on {answer}")
    assert_no_secret(page.told_the_user(), f"a notice on {answer}")
    assert_no_secret(page.everything_on_screen(), f"the page on {answer}")


def test_send_test_with_no_webhook_says_there_is_nothing_to_test(
    request, monkeypatch, qapp
) -> None:
    page = build_page(request, monkeypatch)

    page.presenter._settings_view_model.send_test_requested.emit()

    assert "no discord webhook is saved" in page.label(STATUS).lower()
    assert page.transport.posts == []


# -- off the UI thread, fenced -----------------------------------------------


def test_send_test_runs_off_the_ui_thread_and_the_page_answers_on_it(
    request, monkeypatch, qapp
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor(max_workers=1)
    request.addfinalizer(pool.shutdown)
    ran_on: list[int] = []

    class Recording(FakeWebhookTransport):
        def post_json(self, url, body):
            ran_on.append(threading.get_ident())
            return super().post_json(url, body)

    page = build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: URL}),
        running=True,
        transport=Recording(),
    )
    futures = []
    page.threads.submit = lambda task, *a, **k: futures.append(  # type: ignore[method-assign]
        pool.submit(task, *a, **k)
    )

    page.click(SEND_TEST)
    assert not page.button(SEND_TEST).isEnabled(), "busy while the test is out"
    assert page.label("lblAlertsWorking")
    futures[0].result(timeout=10)
    qapp.processEvents()

    assert ran_on == [ran_on[0]] and ran_on[0] != threading.get_ident()
    assert "sent to discord" in page.label(STATUS).lower()
    assert page.button(SEND_TEST).isEnabled()


def test_an_answer_that_arrives_after_the_page_shut_down_is_dropped(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)
    page.threads.held = []

    page.click(SEND_TEST)
    page.presenter.shutdown()
    for release in page.threads.held:
        release()

    assert "sent to discord" not in page.label(STATUS).lower()
    assert page.notifier.failures == []


def test_the_buttons_are_off_while_an_action_is_out_so_a_second_cannot_start(
    request, monkeypatch, qapp
) -> None:
    page = stored_page(request, monkeypatch, running=True)
    page.threads.held = []

    page.click(SEND_TEST)

    assert not page.button(SAVE).isEnabled()
    assert not page.button(REMOVE).isEnabled()
    assert not page.button(SEND_TEST).isEnabled()
    page.threads.held[0]()
    qapp.processEvents()
    assert page.button(SEND_TEST).isEnabled()


def test_an_answer_for_a_superseded_action_changes_nothing(
    request, monkeypatch, qapp
) -> None:
    """The fence is defence in depth (the buttons are off while an action runs), so it
    is driven directly: an answer carrying another action id is ignored."""
    page = stored_page(request, monkeypatch, running=True)
    page.threads.held = []
    page.click(SEND_TEST)
    presenter = page.presenter
    current = presenter._tracker.active_action
    assert current is not None

    presenter._on_action_done(
        (current.action_id + 1, current.kind, (), presenter._setup.state(), None)
    )

    assert page.label("lblAlertsWorking"), "the real action is still out"
    assert page.label(STATUS) == ""
    assert not page.button(SEND_TEST).isEnabled()
