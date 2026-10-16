"""`EPIC-036D1` — the webhook URL is on no label, no log record, no notice and no exception text.


On success, on refusal and on failure, for Save and for Send test (N3). These are the
page's reason to be careful: a URL is the right to post in the owner's channel.
"""

from __future__ import annotations

import logging
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    SAVE,
    STATUS,
    URL,
    AlertsPage,
    assert_no_secret,
    build_page,
)


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch)


# -- the URL is never shown, logged or reported (N3) --------------------------


@pytest.mark.parametrize("path", ["saved", "invalid", "refused", "crash"])
def test_the_url_is_in_no_log_record_notice_or_label_on_save(
    path: str, request, monkeypatch, qapp, caplog: pytest.LogCaptureFixture
) -> None:
    store = UnavailableSecretStore() if path == "refused" else InMemorySecretStore()
    if path == "crash":

        class Crashing(InMemorySecretStore):
            def write(self, name: str, value: str) -> None:
                raise RuntimeError(f"backend exploded while storing {value}")

        store = Crashing()
    page = build_page(request, monkeypatch, store=store)
    page.type_in_field(URL.replace("https", "http") if path == "invalid" else URL)

    with caplog.at_level(logging.DEBUG):
        page.click(SAVE)

    assert caplog.records
    for record in caplog.records:
        rendered = " ".join(
            [record.getMessage(), str(record.args), str(record.exc_text)]
        )
        if record.exc_info:
            rendered += " ".join(
                str(v) for v in (record.exc_info[1], record.exc_info[1].args)
            )
        assert_no_secret(rendered, f"a log record ({record.name}) on {path}")
    assert_no_secret(page.told_the_user(), f"a notice on {path}")
    assert_no_secret(page.labels_only(), f"a label on {path}")
    if path == "crash":
        [notice] = page.notifier.failures
        assert notice.kind is FailureKind.COMMAND
        assert "unexpectedly" in notice.headline


def test_a_keyring_error_while_saving_is_told_in_words_on_the_page(
    request, monkeypatch, qapp
) -> None:
    class Crashing(InMemorySecretStore):
        def write(self, name: str, value: str) -> None:
            raise SecretStoreUnavailableError("the keyring is locked") from None

    page = build_page(request, monkeypatch, store=Crashing())
    page.type_in_field(URL)

    page.click(SAVE)

    assert "keyring" in page.label(STATUS).lower()
