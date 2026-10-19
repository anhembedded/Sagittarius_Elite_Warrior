# BOT-182 — The desktop app tells the owner when the machine's clock is far from the exchange's

**Status:** ✅ Done (2026-10-19)
**Priority:** P2
**Board:** The desktop app said nothing about a large clock skew (the owner's PC ran 127 s ahead of Binance); the Bots screen now shows one dismissible bar per venue above 1 s, in either direction, from the skew the Connect step already measures. The headless pre-flight stays at 1000 ms, failing closed on real money.
**Source:** the coordinating session, 2026-10-17, after `BUG-223`: "the desktop app should tell the owner about a large clock skew (a notice bar above 1 s), because run_started_at and log times come from the local clock. Leave the headless preflight at 1000 ms as it is. Failing closed on real money is the conservative choice."
**Risk:** 🟢 — a notice only; no order, no setting and no start is changed.
**Complexity:** S — the skew is already measured (`ExchangeConnectionStatus.server_time_skew_ms`, and the offset a session keeps); what is missing is a surface for it.
**Depends on:** None

---

## 1. Context and problem
`BUG-223` (owner's Futures Testnet, 2026-10-17): the DEBUG log read `[clock-offset] futures exchange clock is -127211 ms from this machine's`, so the PC ran about 127 s ahead of Binance, and nothing in the desktop app said so. The clock-skew pre-flight (`trading/adapters/preflight/clock_skew_check.py`: warns above 500 ms, fails at 1000 ms) and the health probe (`trading/adapters/health/clock_skew_probe.py`, with `ClockSkewAlarm`) belong to the headless host and the CLI (`run`, `preflight`); the desktop app runs neither. Signed requests are corrected by the session's offset (`BUG-111`, `BUG-189`), so the skew does not break them, but everything taken from the local clock is that far off: `run_started_at`, the times in the log and on the screens, the start of a history read.

The headless pre-flight keeps failing a skew of 1000 ms or more even though the offset already makes such a machine work. That is the conservative choice on real money (an unattended host with a clock that far off is a machine nobody has looked at) and this task leaves it as it is.

## 2. Acceptance criteria
- [x] When a venue's measured skew is above 1 s in either direction, the desktop app shows one notice bar (`INotifier`, the inline message bar of `ui-presentation-rule.md` §10) at the top of the affected mode, saying the machine's clock is that far from the exchange's and that times shown come from it; dismissible, one bar per venue, gone when the skew is back under the threshold.
- [x] Under 1 s nothing is shown. A venue that cannot be read shows no skew notice (the connection failure has its own bar, `BUG-181`).
- [x] The notice does not stop or change anything: no start, resume or order is refused because of it.
- [x] The headless pre-flight and health probe are unchanged (500 ms warn, 1000 ms fail).

## 3. Design
Reuse the measurement the Connect step already makes (`ExchangeConnectionStatus.server_time_skew_ms`) and the one notifier port; no new probe thread. The threshold is one named constant beside the pre-flight's, so the two cannot drift silently. A skew of this size is stated as seconds, sign kept ("this computer's clock is 127 s ahead of Binance's").

## 3a. Reuse
`INotifier` and the mode message bars (`capabilities.md` row "Tell the user about a failure or an event"): used. `ExchangeConnectionStatus.server_time_skew_ms`: used. `ClockSkewProbe`: not used, it is the headless host's.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `trading/` (the Connect step's consumer) | publish the skew notice through `INotifier` when the measured skew passes the threshold |
| `trading/adapters/preflight/clock_skew_check.py` | export the threshold the notice shares |

## 5. Testing
Unit: the notice at 1001 ms and at -1001 ms, none at 1000 ms, none for an unread skew, cleared when the skew is back. Integration on the fake exchange with its clock skewed (`exchange_clock_skewed_by`): a Connect shows the bar, and a start is still accepted.

## 6. Docs touched
None expected beyond `Docs/SPEC/` if the Connect step's words are specified there; check when starting.

## Implementation notes (written when done)
The Connect step's snapshot (`VenueAccountSnapshot.server_time_skew_ms`, optional, default `None`) now carries the skew the account check measured. `bots/ui/bots_screen/clock_skew_notice.py` → `ClockSkewNotice` judges it against `trading/contracts/clock_skew_limit.py` → `CLOCK_SKEW_LIMIT_MS` (the constant the pre-flight's `FAIL_AT_MS` now takes from, a test pins them equal) and tells it through `INotifier` as a `BACKGROUND` notice with cause `bots.clock_skew.<venue>` and no Retry. It is told once per episode (a dismissed bar does not come back with the next minute's read), is cleared when the skew is back at or under 1 s, when the account cannot be read, or when the screen moves to a bot on another venue. Only the Bots screen has a Connect step, so it is the only mode that shows the bar; the Desk and Market modes read the status without a bar. No probe thread, no start or order is gated on it.
