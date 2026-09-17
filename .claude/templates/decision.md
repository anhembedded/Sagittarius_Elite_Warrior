---
description: The format of a decision record (ADR, Nygard 2011) inside an epic — DECISION_{date}_{slug}.md. Copy it, fill every brace, delete this front matter.
---

# ADR — {the decision as one sentence}

**Epic:** {EPIC-nnn, linked to its README.md} · **Date:** {YYYY-MM-DD} · **Status:** 🔵 Proposed · 🟢 Approved ({by whom; the user's words quoted once}) · ❌ Superseded by {…}

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | settled in the session; not yet implemented |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context
{The forces: the problem, the constraints, the measured evidence, what was tried.}

## 2. Decisions
| # | Decision | Status | Consequence |
| :-- | :--- | :-- | :--- |
| D1 | {…} | ✅ | {what it costs and what it buys} |

## 3. Alternatives considered
{Each with the reason it lost; a named pattern or vetted project per alternative.}

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | {…} | {phase} | {date} |
