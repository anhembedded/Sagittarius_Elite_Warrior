# EPIC-043C — B1 + B2: PnL toned everywhere, and state badges

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** 043B, BOT-209 merged (the Plan dock structure)

---

## 1. Context and problem
Every PnL, return and change figure on the Bots, trading and market screens takes its colour from `Tone`, with sign and ▲ ▼ kept in the text; a bot's or connection's state is a word plus an icon, coloured by a small extension of the meaning table: running, paused, halted, recovering, disconnected. In the Bots Plan dock, the banner, checks list and figures take their tones from the meaning table on top of BOT-209's structure.

## 2. Acceptance criteria
- [ ] Every PnL, return and change figure on the three screens is toned by `Tone` and still carries its sign and arrow.
- [ ] Each state in the list has a word, an icon and a tone from the meaning table; no new colour is written outside it.
- [ ] Readable in light, dark and Windows High Contrast (palette-aware, tested as in `test_meaning_colours.py`).
- [ ] A before/after `preview.py` frame for each touched screen.

## 3. Design
To be written when the task starts; it applies PRO-009 §2 and `EPIC-033` D1 and D8 as amended 2026-10-20. No style sheet, no app palette, no third-party theme package.

## 3a. Reuse
To be filled when the task starts (`.claude/rules/capabilities.md`): `meaning_colours.py`, `Tone`, `series_colours.py`, the Lucide icon set.

## 4. Changes, per file
To be filled when the task starts.

## 5. Testing
To be filled when the task starts; preview frames at 1024×700, 1366×768 and 1920×1080 in both schemes (code tasks).

## 6. Docs touched
To be filled when the task starts.
