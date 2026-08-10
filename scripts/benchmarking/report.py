"""Report formatting — kept separate from measurement so the harness stays
usable from a test or another script without pulling in print formatting."""

from .qt_feed_harness import FeedBenchmarkResult


def format_result(result: FeedBenchmarkResult) -> str:
    return (
        f"[{result.scenario}] {result.candle_count:,} candles\n"
        f"  elapsed        : {result.elapsed_seconds:.4f}s\n"
        f"  emit count     : {result.emit_count:,}\n"
        f"  peak traced mem: {result.peak_traced_memory_bytes / 1024:.1f} KiB"
    )
