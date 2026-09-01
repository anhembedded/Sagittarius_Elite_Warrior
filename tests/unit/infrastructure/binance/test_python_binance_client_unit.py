import gc
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests
from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    ExchangeRequestCancelledError,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    _KLINE_STREAM_CHUNK_SIZE,
    _MAX_TRANSIENT_RETRIES,
    PythonBinanceClient,
)


def _live_market_data_count() -> int:
    """Counts real, currently-alive `MarketData` instances via the GC heap
    — deterministic and reproducible across machines/CI, unlike sampling
    OS-level RSS (which is noisy and affected by allocator behavior, see
    BUG-025's own report for why an RSS-based test was rejected)."""
    gc.collect()
    return sum(1 for obj in gc.get_objects() if type(obj) is MarketData)


def _raw_kline(index: int) -> list:
    return [
        1672531200000 + index * 60_000,
        "100.0",
        "110.0",
        "90.0",
        "105.0",
        "1000.0",
        1672531259999 + index * 60_000,
        "105000.0",
        50,
        "500.0",
        "52500.0",
        "0",
    ]


def test_injected_client_is_used_directly_without_patching_the_sdk():
    """
    DIP: a pre-built client can be injected via __init__, so tests (and callers) don't
    need unittest.mock.patch reaching into the binance.client.Client construction.
    """
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = []

    client = PythonBinanceClient(client=injected_client)

    assert client.client is injected_client

    client.get_historical_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
    )
    injected_client.get_historical_klines_generator.assert_called_once()


def test_default_market_data_venue_uses_spot_klines_type():
    """`EPIC-021A`: `PythonBinanceClient` no longer constructs its own SDK
    client (`ExchangeSessionFactory` is the one place allowed to) — this
    replaces the old fallback-construction test. Default `market_data_venue`
    (`MAINNET_PUBLIC`) must still resolve to `HistoricalKlinesType.SPOT`,
    keeping every existing call site's behavior unchanged."""
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = []

    client = PythonBinanceClient(client=injected_client)

    client.get_historical_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
    )
    _, kwargs = injected_client.get_historical_klines_generator.call_args
    assert kwargs["klines_type"] == HistoricalKlinesType.SPOT


def test_get_historical_klines_propagates_underlying_client_errors():
    """Errors from the injected client must not be swallowed."""
    injected_client = Mock()
    injected_client.get_historical_klines_generator.side_effect = RuntimeError(
        "API rate limit"
    )

    client = PythonBinanceClient(client=injected_client)

    try:
        client.get_historical_klines(
            "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
        )
        raise AssertionError("Expected RuntimeError to propagate")
    except RuntimeError as exc:
        assert "API rate limit" in str(exc)


def test_python_binance_client_with_end_str():
    injected_client = Mock()

    # Simulate the generator returning one kline
    mock_kline = [
        1672531200000,
        "100.0",
        "110.0",
        "90.0",
        "105.0",
        "1000.0",
        1672531259999,
        "105000.0",
        50,
        "500.0",
        "52500.0",
        "0",
    ]
    injected_client.get_historical_klines_generator.return_value = [mock_kline]

    client = PythonBinanceClient(client=injected_client)

    start_dt = datetime(2023, 1, 1, tzinfo=UTC)
    end_dt = datetime(2023, 1, 2, tzinfo=UTC)

    klines = client.get_historical_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, start_dt, end_dt
    )

    # Assert the generator was called with formatted strings
    args, kwargs = injected_client.get_historical_klines_generator.call_args
    assert args == ("BTCUSDT", "1m", "01 Jan 2023 00:00:00", "02 Jan 2023 00:00:00")
    assert kwargs["klines_type"] == HistoricalKlinesType.SPOT

    assert len(klines) == 1
    assert klines[0].symbol == "BTCUSDT"
    assert klines[0].open_price == 100.0


def test_python_binance_client_without_end_str():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = []

    client = PythonBinanceClient(client=injected_client)
    start_dt = datetime(2023, 1, 1, tzinfo=UTC)

    client.get_historical_klines("ETHUSDT", TimeFrame.ONE_HOUR, start_dt)

    # end_str defaults to None
    args, kwargs = injected_client.get_historical_klines_generator.call_args
    assert args == ("ETHUSDT", "1h", "01 Jan 2023 00:00:00", None)
    assert kwargs["klines_type"] == HistoricalKlinesType.SPOT


def test_historical_kline_iteration_stops_cooperatively_when_cancelled():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = [
        [
            1672531200000 + index * 60_000,
            "100.0",
            "110.0",
            "90.0",
            "105.0",
            "1000.0",
            1672531259999 + index * 60_000,
            "105000.0",
            50,
            "500.0",
            "52500.0",
            "0",
        ]
        for index in range(10)
    ]
    cancellation_checks = 0

    def cancellation_requested() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 4

    client = PythonBinanceClient(client=injected_client)

    with pytest.raises(ExchangeRequestCancelledError):
        client.get_historical_klines(
            "BTCUSDT",
            TimeFrame.ONE_MINUTE,
            datetime(2023, 1, 1, tzinfo=UTC),
            cancellation_requested=cancellation_requested,
        )

    assert cancellation_checks == 4


def test_stream_historical_klines_yields_bounded_chunks_instead_of_one_giant_list():
    """BUG-025 regression test: the whole point of streaming is that no
    single chunk grows past the page size, regardless of how many klines
    the underlying generator produces in total — proving RAM usage per
    chunk is bounded, not proportional to the requested range."""
    total_raw_klines = _KLINE_STREAM_CHUNK_SIZE * 2 + 5
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = (
        _raw_kline(i) for i in range(total_raw_klines)
    )

    client = PythonBinanceClient(client=injected_client)

    chunks = list(
        client.stream_historical_klines(
            "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
        )
    )

    assert [len(c) for c in chunks] == [
        _KLINE_STREAM_CHUNK_SIZE,
        _KLINE_STREAM_CHUNK_SIZE,
        5,
    ]
    assert sum(len(c) for c in chunks) == total_raw_klines
    assert all(kline.symbol == "BTCUSDT" for chunk in chunks for kline in chunk)


def test_streaming_and_discarding_chunks_never_lets_more_than_one_chunk_stay_alive():
    """Real memory proof for BUG-025, not just a call-count assertion: this
    drives a 5000-kline stream while discarding each chunk right after it's
    yielded — exactly what the fixed handler now does via save_klines() —
    and counts real live `MarketData` objects on the GC heap at every step.
    If streaming secretly still built one giant list under the hood (the
    original bug), or something in the mapping path kept a stray reference
    to earlier chunks, the live count would grow across iterations instead
    of staying flat at (at most) one chunk's worth."""
    total_raw_klines = _KLINE_STREAM_CHUNK_SIZE * 5
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = (
        _raw_kline(i) for i in range(total_raw_klines)
    )
    client = PythonBinanceClient(client=injected_client)

    baseline = _live_market_data_count()
    peak_live_beyond_baseline = 0

    for chunk in client.stream_historical_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
    ):
        live_now = _live_market_data_count() - baseline
        peak_live_beyond_baseline = max(peak_live_beyond_baseline, live_now)
        del chunk  # mirrors the handler: save_klines(chunk) then move on

    final_live = _live_market_data_count() - baseline

    assert peak_live_beyond_baseline <= _KLINE_STREAM_CHUNK_SIZE
    assert final_live == 0


def test_stream_historical_klines_reports_progress_and_maps_fields_correctly():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = [_raw_kline(0)]
    progress_calls: list[int] = []

    client = PythonBinanceClient(client=injected_client)

    chunks = list(
        client.stream_historical_klines(
            "BTCUSDT",
            TimeFrame.ONE_MINUTE,
            datetime(2023, 1, 1, tzinfo=UTC),
            progress_callback=progress_calls.append,
        )
    )

    assert len(chunks) == 1
    assert progress_calls == [1]
    assert chunks[0][0].symbol == "BTCUSDT"
    assert chunks[0][0].open_price == 100.0


def test_stream_historical_klines_stops_cooperatively_when_cancelled():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = (
        _raw_kline(i) for i in range(10)
    )
    cancellation_checks = 0

    def cancellation_requested() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 4

    client = PythonBinanceClient(client=injected_client)

    with pytest.raises(ExchangeRequestCancelledError):
        list(
            client.stream_historical_klines(
                "BTCUSDT",
                TimeFrame.ONE_MINUTE,
                datetime(2023, 1, 1, tzinfo=UTC),
                cancellation_requested=cancellation_requested,
            )
        )

    assert cancellation_checks == 4


def test_get_available_symbols_returns_only_trading_status_symbols_sorted():
    """BOT-102 — BREAK/HALT/other non-TRADING symbols must not appear in the
    picker; the exchange lists them but they cannot actually be backtested
    against fresh data."""
    injected_client = Mock()
    injected_client.get_exchange_info.return_value = {
        "symbols": [
            {"symbol": "ETHUSDT", "status": "TRADING"},
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "DELISTEDUSDT", "status": "BREAK"},
        ]
    }

    client = PythonBinanceClient(client=injected_client)

    assert client.get_available_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_get_available_symbols_returns_empty_list_when_exchange_info_is_empty():
    injected_client = Mock()
    injected_client.get_exchange_info.return_value = {"symbols": []}

    client = PythonBinanceClient(client=injected_client)

    assert client.get_available_symbols() == []


# --------------------------------------------------------------------------- #
# BUG-063 — a single transient network error (ReadTimeout) during a long
# multi-page historical sync used to abort the whole request, discarding
# every kline the current attempt had already fetched. Real trigger: a 7-day
# 1-second-interval sync needs ~600 sequential Binance requests; python-
# binance's own generator has no retry, so any one of those 600 timing out
# killed the entire sync.
# --------------------------------------------------------------------------- #


def _failing_generator(*_args: object, **_kwargs: object):
    """A `get_historical_klines_generator` stand-in that raises on the first
    `next()` call — mirrors a page failing before yielding anything."""
    raise requests.exceptions.ReadTimeout("read timed out")
    yield  # pragma: no cover - unreachable; makes this a generator function


def test_stream_historical_klines_resumes_from_the_last_kline_after_a_transient_network_error(
    monkeypatch,
):
    """The regression case: 2 klines come through, the page after them times
    out, and the retry must continue from kline 1's close_time — not restart
    the whole sync from the original start_str (which would silently
    re-download data already saved) and not lose the 2 klines already
    fetched (which the old code did, since the exception unwound past the
    unfinished buffer before it was ever yielded)."""
    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.client.time.sleep",
        lambda _seconds: None,
    )
    injected_client = Mock()
    calls: list[tuple] = []

    def _generator_side_effect(symbol, interval, start_str, end_str, **_kwargs):
        calls.append((symbol, interval, start_str, end_str))
        if len(calls) == 1:

            def _first_attempt():
                yield _raw_kline(0)
                yield _raw_kline(1)
                raise requests.exceptions.ReadTimeout("read timed out")

            return _first_attempt()
        return (_raw_kline(i) for i in range(2, 5))

    injected_client.get_historical_klines_generator.side_effect = _generator_side_effect

    client = PythonBinanceClient(client=injected_client)

    chunks = list(
        client.stream_historical_klines(
            "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
        )
    )

    all_klines = [k for chunk in chunks for k in chunk]
    assert len(all_klines) == 5, "the 2 klines fetched before the timeout were lost"
    assert len(calls) == 2, "expected exactly one retry attempt"
    # BUG-022's inclusive-close_time convention: resume 1ms after the last
    # kline this attempt actually received, not from the original start_str.
    expected_resume_start = _raw_kline(1)[6] + 1
    assert calls[1][2] == expected_resume_start


def test_stream_historical_klines_gives_up_after_repeated_transient_errors_with_no_progress(
    monkeypatch,
):
    """A connection that never yields a single kline between failures is
    genuinely down, not flaky — this must surface as an error rather than
    retry forever or silently return an empty/partial result."""
    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.client.time.sleep",
        lambda _seconds: None,
    )
    injected_client = Mock()
    injected_client.get_historical_klines_generator.side_effect = _failing_generator

    client = PythonBinanceClient(client=injected_client)

    with pytest.raises(requests.exceptions.RequestException):
        list(
            client.stream_historical_klines(
                "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
            )
        )

    # The generator is called once per attempt: the first try plus every retry.
    assert (
        injected_client.get_historical_klines_generator.call_count
        == _MAX_TRANSIENT_RETRIES + 1
    )


def test_stream_historical_klines_cancellation_during_retry_backoff_stops_immediately(
    monkeypatch,
):
    """Cancellation must be honoured while waiting out the backoff delay, not
    only between pages — otherwise cancelling right after a timeout leaves
    the user waiting through the retry's own sleep first."""
    monkeypatch.setattr(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.client.time.sleep",
        lambda _seconds: None,
    )
    injected_client = Mock()
    failure_happened = {"flag": False}

    def _first_attempt(symbol, interval, start_str, end_str, **_kwargs):
        def _gen():
            yield _raw_kline(0)
            failure_happened["flag"] = True
            raise requests.exceptions.ReadTimeout("read timed out")

        return _gen()

    injected_client.get_historical_klines_generator.side_effect = _first_attempt

    client = PythonBinanceClient(client=injected_client)

    with pytest.raises(ExchangeRequestCancelledError):
        list(
            client.stream_historical_klines(
                "BTCUSDT",
                TimeFrame.ONE_MINUTE,
                datetime(2023, 1, 1, tzinfo=UTC),
                cancellation_requested=lambda: failure_happened["flag"],
            )
        )
