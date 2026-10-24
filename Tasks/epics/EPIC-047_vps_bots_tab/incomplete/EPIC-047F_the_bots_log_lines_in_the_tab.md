# EPIC-047F — The selected VPS bot's own log lines appear in the tab, read-only

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24, settled as G4: the host's log lines in the tab, read-only, only the selected bot's own events, in a later child. The owner's pain is charter §1.3 (the BUG-268 investigation needed `tar`, `scp` and an upload).
**Risk:** 🟢 — read-only; a bot's lines may contain figures, so the filter must not let another bot's or the host's lines in.
**Complexity:** M — a log source on the host side of the bridge, a stream on the link, and the existing `BotLogFeed` surface on the desktop.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047E](EPIC-047E_the_vps_bots_tab.md)

---

## 1. Context and problem
The Bots tab shows a bot's events through `BotLogFeed`, an in-process log handler on the bus. The host writes its log to its own files, and reading a bot's lines on the VPS today needs SSH, `tar` and `scp`. De-risk R1 listed this stream as a later one ("the log lines later (G4)") beside `BotChangedEvent` and `ArmedStrategyChangedEvent` (DERISK §1.3).

## 2. Acceptance criteria
- [ ] Selecting a VPS bot shows its own log lines in the same panel as the Bots tab, newest last, with the age of the last line.
- [ ] Only the selected bot's lines cross the link: the filter is on the host side of the bridge, by bot id and by the existing log tags, never in the tab (a test with two bots in one log).
- [ ] The panel is read-only, and nothing in it sends a command.
- [ ] The stream is bounded (a maximum number of lines and bytes per bot, and per second), and a slow desktop drops old lines instead of slowing the bridge (a test).
- [ ] Switching bots stops the old stream; the bridge holds none after the tab closes or the link drops.
- [ ] A line contains no key or secret: a test greps a sample of the host's lines for key-shaped text, and the task checks `logging-rule.md` for what a line may carry; if the rule does not forbid secrets in a line, the bridge drops a line that matches and the task says so in its notes.

## 3. Design
The host's log is read from its files by the bridge, as the store is (no socket, no host change beyond what 047B and 047C add); the lines are events on the link with a revision. The desktop adapts them to the existing `BotLogFeed` surface so the panel is the Bots tab's own class (AC7). The transport is the 047D one, with the 047A codec for the line record.

## 3a. Reuse
`BotLogFeed` and the Bots tab's log panel: `used`. The logging namespaces and tags of `logging-rule.md` decide the filter: `used`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/…` (bridge log reader) | tail and filter the selected bot's lines |
| `src/modules/bots/ui/…` | adapt the remote lines to `BotLogFeed` |
| `tests/…` | filter, bound and secret tests |

## 5. Testing
Tier: unit and integration on a fake host log, then the full gate. Not run.

## 6. Docs touched
`Docs/OPERATIONS/LOGGING.md` (a line on the remote reader), `Docs/MODULES/bots/06-runtime.md`.

## Implementation notes (written when done)
Not written: not started.
