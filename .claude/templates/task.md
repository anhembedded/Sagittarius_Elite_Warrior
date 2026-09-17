---
description: The format of a task file under Tasks/backlog/ (ONBOARDING §3). Copy it, fill every brace, delete this front matter.
---

# BOT-{nnn} — {the outcome, not the activity}

**Status:** 🔵 Backlog · 🟡 In progress · ✅ Done {YYYY-MM-DD}
**Source:** {who asked, when — the user's words quoted once, verbatim, then translated}
**Risk:** 🟢 · 🟡 · 🔴 — {what could break, one line}
**Complexity:** `S` · `M` · `L` — {why, one line}

---

## 1. Context and problem
{The real situation with evidence: `file:line`, a measured number, the symptom. Why now.}

## 2. Design
{The choice made and the reason for each non-obvious one; the named pattern or vetted project it applies (ONBOARDING §7: apply before you invent). A restructuring shows as-is and to-be.}

## 3. Changes, per file
| File | Change |
| :--- | :--- |
| {path} | {what, and why} |

## 4. Testing
{Which tier proves it (`ci-rule.md` §6) and the test names; what the gate must show.}

## Implementation notes (written when done)
{The real bugs met, decisions taken, test counts before → after, the gate's `LOG_FILE:` path. Then ONBOARDING §6: the `ROADMAP.md` line and the recomputed count table.}
