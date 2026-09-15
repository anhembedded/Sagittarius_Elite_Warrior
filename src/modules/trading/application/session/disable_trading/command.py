from dataclasses import dataclass


@dataclass(frozen=True)
class DisableTradingCommand:
    """@brief Command to turn live trading off for this session (`EPIC-021I`).
    @details No fields, symmetric with `EnableTradingCommand` — there is
    nothing for a caller to parameterize. Unlike enabling, disabling never
    refuses: it always succeeds, so there is no `DisableTradingResult`
    with a block reason to report.
    """
