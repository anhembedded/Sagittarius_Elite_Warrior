from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestCancelled:
    """Explicit, non-result outcome for a cooperatively cancelled run.

    A cancelled calculation must never be represented as a partial
    ``BacktestResult``: metrics and trades from a partial pass would look
    authoritative even though the requested historical range was not run.
    """

    phase: str
    processed_bars: int
    total_bars: int
