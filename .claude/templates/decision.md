---
description: The format of a decision record (ADR, Nygard 2011) inside an epic — DECISION_{date}_{slug}.md. Copy it, fill every brace, delete this front matter.
---

# ADR — {the decision as one sentence}

<!-- Choose one status. Acceptance records a decision; it does not prove implementation. Remove optional fields and instructional comments when copying. -->
**Epic:** {EPIC-nnn, linked to its README.md}
**Date:** {YYYY-MM-DD}
**Status:** {Proposed / Accepted / Rejected / Superseded}
**Decided by:** {Pending, or the user or agent and the authority under ONBOARDING §7; quote a user decision once, then translate}
**Supersedes / superseded by (optional):** {link to the other record}

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |
| 🤖 Agent decision | delegated by the user and decided under ONBOARDING §7: a named pattern, broad precedent |
| ❓ Open | blocks the named phase until answered |

## 1. Context
{The forces: the problem, the constraints, the measured evidence, what was tried.}

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | {the choice} | {Proposed / Accepted / Rejected / Superseded; link a replacement} | {Pending / user / agent, with authority} | {what it costs and what it buys} |

<!-- The labels above qualify evidence and attribution in the prose; they are not implementation states. -->

## 3. Alternatives considered
{Each with the reason it lost; a named pattern or vetted project per alternative.}

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | {…} | {phase} | {date} |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | {task link, or Not assigned} | {Not started / In progress / Verified / Not applicable with reason} | {Not yet verified, or checked code and test evidence with commit/date} |
