"""`EPIC-038H` — the runbook states the figures the code and the service files hold.

The pinned-sentence pattern: prose that restates a number drifts from the code that returns
it, so the figures the runbook gives are computed from the same constants the unit is
rendered from and must appear in it. (That every pre-flight check has a row is asserted in
`tests/integration/modules/bots/test_preflight_on_the_fake_exchange.py`, where the checks
are read from the composed app.)
"""

from __future__ import annotations

import re
from pathlib import Path

from Sagittarius_Elite_Warrior.scripts.render_service_files import (
    mainnet_credential_names,
    supervisor_stop_wait_seconds,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import (
    LEAVE_PUBLISH_SECONDS,
    STOP_GRACE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.run_options import (
    DEFAULT_STOP_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.exit_code_table import (
    non_restarting_codes,
)

_RUNBOOK = (
    Path(__file__).resolve().parents[3] / "Docs" / "OPERATIONS" / "headless_runbook.md"
)
_TEXT = _RUNBOOK.read_text(encoding="utf-8")
_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def test_the_runbook_gives_the_restart_policy_the_unit_has() -> None:
    codes = " ".join(str(code) for code in non_restarting_codes())
    assert f"`RestartPreventExitStatus={codes}`" in _TEXT


def test_the_runbook_gives_the_stop_budget_the_unit_and_the_wrapper_use() -> None:
    seconds = supervisor_stop_wait_seconds(DEFAULT_STOP_TIMEOUT_SECONDS)
    formula = (
        f"ceil({DEFAULT_STOP_TIMEOUT_SECONDS:g} + {STOP_GRACE_SECONDS:g} + "
        f"{LEAVE_PUBLISH_SECONDS:g})"
    )
    assert f"`TimeoutStopSec={seconds}`" in _TEXT
    assert formula in _TEXT
    assert f"`AppStopMethodConsole {seconds * 1000}`" in _TEXT
    worst_case = int(
        DEFAULT_STOP_TIMEOUT_SECONDS + STOP_GRACE_SECONDS + LEAVE_PUBLISH_SECONDS
    )
    assert f"{worst_case} s at the latest" in _TEXT


def test_the_runbook_names_every_key_variable_and_credential_file() -> None:
    for name in (
        FUTURES_ENV_API_KEY,
        FUTURES_ENV_API_SECRET,
        SPOT_ENV_API_KEY,
        SPOT_ENV_API_SECRET,
        *mainnet_credential_names(),
    ):
        assert name in _TEXT, name


def test_the_first_page_says_what_is_not_supported_and_links_the_three_tasks() -> None:
    first_page = _TEXT.split("\n## 1.")[0]
    assert "not supported for unattended money" in first_page
    for task in ("EPIC-036B", "EPIC-036C", "EPIC-036E"):
        assert task in first_page, task


def test_every_relative_link_in_the_runbook_resolves() -> None:
    broken = [
        target
        for target in _LINK.findall(_TEXT)
        if not target.startswith("http")
        and not (_RUNBOOK.parent / target).resolve().exists()
    ]
    assert broken == []


def test_the_runbook_links_the_logging_guide_instead_of_restating_it() -> None:
    assert "(LOGGING.md)" in _TEXT
    assert "copytruncate" in _TEXT
    assert "/var/log/sew/sew.log {" not in _TEXT, "the stanza lives in LOGGING.md"


def test_the_runbook_has_the_container_note_and_the_signed_checklist() -> None:
    assert "does not work inside Docker" in _TEXT
    assert "Signed:" in _TEXT
