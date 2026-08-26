"""`IndicatorCoordinator` — built with no presenter, no view, no container."""

from __future__ import annotations

from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    IndicatorCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.chart_canvas_view import (
    ChartDisplayMode,
)


class _Card:
    def __init__(self) -> None:
        self.visibility: list[tuple[str, bool]] = []

    def set_indicator_visible(self, name: str, visible: bool) -> None:
        self.visibility.append((name, visible))


class _Runner:
    """Records what the coordinator asks of `IndicatorScriptRunner`."""

    def __init__(self, active=None) -> None:
        self.active = dict(active or {})
        self.drawn: list[tuple] = []
        self.removed: list[str] = []
        self.added: list[str] = []
        self.reset_calls = 0

    def draw(self, card, name, x, y) -> None:
        self.drawn.append(("line", name, len(x)))

    def draw_region(self, host, key, spans) -> None:
        self.drawn.append(("region", key, len(spans)))

    def draw_info(self, host, key, fields) -> None:
        self.drawn.append(("info", key, len(fields)))

    def draw_markers(self, host, key, markers) -> None:
        self.drawn.append(("markers", key, len(markers)))

    def remove_script(self, key, card) -> None:
        self.removed.append(key)
        self.active.pop(key, None)

    def add_script(self, key, klines) -> None:
        self.added.append(key)

    def reset_after_host_replaced(self) -> None:
        self.reset_calls += 1


def _build(
    *, card=None, runner=None, enabled=(), klines=None, mode=ChartDisplayMode.OHLC
):
    runner = runner or _Runner()
    lines: set[str] = set()
    fallback_calls: list[tuple[str, int]] = []
    emitted_lines: list[tuple] = []
    emitted_regions: list[tuple] = []
    script_keys: list[list[str]] = []

    def fallback(label, draw, *, drawn_count):
        fallback_calls.append((label, drawn_count))
        draw(card)

    view_model = SimpleNamespace(
        script_model=SimpleNamespace(enabled_keys=list(enabled))
    )
    coordinator = IndicatorCoordinator(
        view_model=view_model,
        strategy_registry=SimpleNamespace(available=dict),
        logger=SimpleNamespace(info=lambda _m: None),
        script_runner=runner,
        get_first_chart_card=lambda: card,
        get_active_strategy_lines=lambda: lines,
        get_current_raw_klines=lambda: list(klines or []),
        get_chart_mode=lambda: mode,
        apply_after_native_fallback=fallback,
        emit_strategy_line=lambda *a: emitted_lines.append(a),
        emit_strategy_region=lambda *a: emitted_regions.append(a),
        set_chart_script_keys=script_keys.append,
    )
    return SimpleNamespace(
        coordinator=coordinator,
        runner=runner,
        lines=lines,
        fallback_calls=fallback_calls,
        emitted_lines=emitted_lines,
        emitted_regions=emitted_regions,
        script_keys=script_keys,
        card=card,
    )


def test_region_info_and_marker_each_report_their_own_label_and_count() -> None:
    """The three share one implementation now; if the label or the count
    were wired to the wrong argument, every one of them would still draw."""
    ctx = _build(card=_Card())

    ctx.coordinator.on_script_region("rsi", [1, 2, 3])
    ctx.coordinator.on_script_info("rsi", [1, 2])
    ctx.coordinator.on_script_marker("rsi", [1])

    assert ctx.fallback_calls == [
        ("script regions", 3),
        ("script info", 2),
        ("script markers", 1),
    ]
    assert ctx.runner.drawn == [
        ("region", "rsi", 3),
        ("info", "rsi", 2),
        ("markers", "rsi", 1),
    ]


def test_nothing_is_drawn_before_a_chart_card_exists() -> None:
    ctx = _build(card=None)

    ctx.coordinator.on_script_line("ema", [1], [2])
    ctx.coordinator.on_script_region("rsi", [1])
    ctx.coordinator.set_strategy_lines_visible(True)

    assert ctx.runner.drawn == []
    assert ctx.fallback_calls == []


def test_host_rebuild_drops_stale_lines_and_resets_the_runner() -> None:
    """BUG-013: skipping the runner reset leaves a dispose callback bound to
    a deleted host, and the next run crashes in shiboken. Clearing only the
    line names would look right and still crash."""
    ctx = _build(card=_Card())
    ctx.lines.add("ema_20")

    ctx.coordinator.reset_bookkeeping_after_host_rebuild()

    assert ctx.lines == set()
    assert ctx.runner.reset_calls == 1


def test_only_overlay_scripts_are_hidden_for_equity_mode() -> None:
    """BOT-065: subplot scripts don't share the main plot, so hiding them
    fixes nothing and loses the user's indicator."""
    card = _Card()
    runner = _Runner(
        {
            "rsi": SimpleNamespace(overlay=False, registered_lines=["rsi"]),
            "ema": SimpleNamespace(overlay=True, registered_lines=["fast"]),
        }
    )
    ctx = _build(card=card, runner=runner)

    ctx.coordinator.set_script_overlay_lines_visible(False)

    assert [name for name, _ in card.visibility] == ["ema:fast"]


def test_toggling_a_script_off_removes_it_and_on_adds_it() -> None:
    runner = _Runner({"old": SimpleNamespace(overlay=True, registered_lines=[])})
    ctx = _build(card=_Card(), runner=runner, enabled=["new"], klines=[object()])

    ctx.coordinator.on_script_selection_changed()

    assert runner.removed == ["old"]
    assert runner.added == ["new"]
    assert ctx.script_keys == [["new"]]


def test_a_script_enabled_during_equity_mode_starts_hidden() -> None:
    """Adding an overlay script while the chart shows equity would otherwise
    drag the shared plot's auto-range back onto price."""
    card = _Card()
    runner = _Runner()
    runner.add_script = lambda key, klines: runner.active.__setitem__(
        key, SimpleNamespace(overlay=True, registered_lines=["fast"])
    )
    ctx = _build(
        card=card,
        runner=runner,
        enabled=["ema"],
        klines=[object()],
        mode=ChartDisplayMode.EQUITY,
    )

    ctx.coordinator.on_script_selection_changed()

    assert ("ema:fast", False) in card.visibility


def test_an_unknown_strategy_key_emits_nothing() -> None:
    ctx = _build(card=_Card())

    config = SimpleNamespace(strategy_key="nope", strategy_params={})
    ctx.coordinator.emit_strategy_indicator_lines(1, config, [])
    ctx.coordinator.emit_strategy_trend_zones(1, config, [])

    assert ctx.emitted_lines == []
    assert ctx.emitted_regions == []
