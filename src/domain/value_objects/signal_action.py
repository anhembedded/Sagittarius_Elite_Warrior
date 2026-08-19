from enum import Enum


class SignalAction(str, Enum):
    #: Opens (or pyramids into) a LONG position. Meaning never changes
    #: regardless of what other positions are open — a strategy that only
    #: ever trades long can keep using BUY/SELL exactly as before BOT-050.
    BUY = "BUY"
    #: Closes an open LONG position. Never opens a SHORT — see SHORT below.
    SELL = "SELL"
    HOLD = "HOLD"
    #: BOT-050 — opens (or pyramids into) a SHORT position. A strategy that
    #: wants to reverse from Long to Short sends SELL then SHORT as two
    #: explicit signals; `PaperExchange` never infers a reversal from one
    #: signal's context (see BOT-050 §3 — the strategy states its own
    #: intent, the exchange never guesses from position state).
    SHORT = "SHORT"
    #: BOT-050 — closes an open SHORT position (a "buy to cover").
    COVER = "COVER"
