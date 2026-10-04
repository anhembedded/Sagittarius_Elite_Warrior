"""`EPIC-030M` — every test runs with `SEW_DATA_ROOT` outside the checkout.

Pins `tests/runtime_data_guard.py`'s session fixture: without it, the default
`data_root()` is the repository root and a test boot writes the real app state.

Retire when: `tests/runtime_data_guard.py` is retired.
"""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.core.repo_root import (
    DATA_ROOT_ENV,
    data_root,
    repo_root,
)


def test_the_data_root_is_set_for_every_test_and_is_outside_the_checkout() -> None:
    assert os.environ.get(DATA_ROOT_ENV), f"{DATA_ROOT_ENV} is not set"
    assert not data_root().resolve().is_relative_to(repo_root())
