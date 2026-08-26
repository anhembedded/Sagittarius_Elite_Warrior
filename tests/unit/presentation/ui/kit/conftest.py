"""Shared fixtures for `widgets/` tests.

`get_theme_bridge()` is a process-wide, first-caller-wins singleton (see
its own docstring) — some other test module in the full session (e.g.
`test_overlay_host.py`'s all-`#000000` placeholder, which is fine there
since that suite "doesn't exercise theming") can and does win the race
when the whole engine suite runs together, silently making every token
this package reads collide with every other. Two fixtures follow from that:

- `_theme_bridge_ready` (autouse): guarantees SOME palette is present, for
  tests that only need presence/structure, not cross-token distinctness
  (does this role produce non-empty QSS containing `background-color:`,
  does the live value of a single named token appear in the output, ...).
- `fake_theme_bridge`: for tests that specifically need two DIFFERENT
  tokens (e.g. `muted` vs `accent`, distinguishing a disabled button from
  an enabled one) to actually differ — the only session-order-independent
  way to test that is to not depend on the real shared singleton at all.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge

#: Arbitrary but valid, and deliberately DISTINCT per token — unlike
#: test_overlay_host.py's all-#000000 placeholder (fine there: that suite
#: "doesn't exercise theming"). This suite tests that different roles/states
#: render different QSS, which an all-identical palette silently masks —
#: e.g. a disabled button's background reads the `muted` token, which would
#: be indistinguishable from `accent` if both were `#000000`. Not real
#: visual constants; only distinctness from each other matters.
_PLACEHOLDER_PALETTE = {
    "bg": "#100000",
    "bgSidebar": "#200000",
    "bgCard": "#300000",
    "bgCardHeader": "#400000",
    "border": "#500000",
    "textPrimary": "#600000",
    "accent": "#700000",
    "success": "#800000",
    "warning": "#b00000",
    "danger": "#900000",
    "muted": "#a00000",
}


@pytest.fixture(scope="package", autouse=True)
def _theme_bridge_ready() -> None:
    get_theme_bridge(_PLACEHOLDER_PALETTE)


class _FakeThemeBridge:
    """A `get_theme_bridge()` stand-in with guaranteed-distinct values per
    token name — see module docstring for why the real singleton cannot be
    relied on for this."""

    def contains(self, name: str) -> bool:
        """Every name resolves here — this stand-in exists to make token
        values distinguishable, not to model which tokens an app defines.
        A test that needs the real bridge's fail-fast on an unknown name
        must not take this fixture."""
        return True

    def value(self, name: str) -> str:
        return f"<{name}>"


@pytest.fixture
def fake_theme_bridge(monkeypatch: pytest.MonkeyPatch) -> _FakeThemeBridge:
    fake = _FakeThemeBridge()
    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.presentation.ui.kit.style.get_theme_bridge",
        lambda: fake,
    )
    return fake
