from unittest.mock import patch

from Sagittarius_Elite_Warrior.src.application.services.rate_limiter import (
    ThreadSafeRateLimiter,
)


def test_rate_limiter_initialization():
    limiter = ThreadSafeRateLimiter(delay_sec=0.5)
    assert limiter.delay_sec == 0.5

    limiter.delay_sec = 0.2
    assert limiter.delay_sec == 0.2


@patch("time.sleep")
def test_rate_limiter_acquire_sleeps_when_elapsed_is_less_than_delay(mock_sleep):
    limiter = ThreadSafeRateLimiter(delay_sec=0.2)

    # First acquire - no sleep
    limiter.acquire()
    assert mock_sleep.call_count == 0

    # Second immediate acquire - sleeps
    limiter.acquire()
    assert mock_sleep.call_count == 1
    assert 0 <= mock_sleep.call_args[0][0] <= 0.2


def test_rate_limiter_reset():
    limiter = ThreadSafeRateLimiter(delay_sec=0.2)
    limiter.acquire()
    limiter.reset()
    assert limiter._last_time == 0.0


@patch("time.sleep")
def test_rate_limiter_acquire_aborts_on_cancellation(mock_sleep):
    limiter = ThreadSafeRateLimiter(delay_sec=1.0)
    limiter.acquire()
    mock_sleep.reset_mock()

    limiter.acquire(cancellation_requested=lambda: True)
    assert mock_sleep.call_count == 0
