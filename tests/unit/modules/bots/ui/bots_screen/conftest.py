"""Every Bots screen a test opens is disposed when the test ends, as
`PresenterManager` disposes it in the app: its timers and its bus
subscriptions must not outlive the test that made them."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot

from .bots_screen_fixtures import Answers, BotsScreen, open_screen

type OpenBotsScreen = Callable[..., BotsScreen]


@pytest.fixture
def open_bots_screen(tmp_path: Path, qtbot: Any) -> Iterator[OpenBotsScreen]:
    opened: list[BotsScreen] = []

    def _open(
        bots: Sequence[StoredBot] = (), answers: Answers | None = None
    ) -> BotsScreen:
        screen = open_screen(tmp_path, qtbot, bots, answers)
        opened.append(screen)
        return screen

    yield _open
    for screen in opened:
        screen.presenter.dispose()
