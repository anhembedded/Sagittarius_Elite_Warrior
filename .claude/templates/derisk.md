---
description: The format of an epic's De-risk index in the README.md of the epic's derisk/ folder (Tasks/epics/README.md) — throwaway experiments that confirm or overturn provisional decisions, one file per experiment beside it. Conditional: section 4 of the create-epic skill decides. Copy it, fill every brace, delete this front matter and instructional comments.
---

# De-risk — EPIC-{nnn} {short title}

<!-- Write De-risk only when section 4 of the create-epic skill calls for one. This file is the index; each experiment is its own R{n}_{slug}.md beside it, in the experiment format below. Spike code lives outside the repository or inside a fenced block of the experiment file: a .py file here makes the pull request code (ONBOARDING §7). -->
| Field | Value |
| :--- | :--- |
| Document type | De-risk: throwaway experiments that confirm or overturn the provisional decisions |
| Epic | EPIC-{nnn} — {the outcome} |
| Version | {0.1} ({Draft / Complete}) |
| Status | {which experiments ran, which wait for whom} |
| Inputs | {charter version · Discover version · code at {branch} {sha}} |
| Next step | {the decision records for G…} |

**Revision history**

| Version | Date | Description |
| :--- | :--- | :--- |
| {0.1} | {YYYY-MM-DD} | {…} |

---

## Summary
| ID | Question (short) | Verdict | Effect | File |
| :--- | :--- | :--- | :--- | :--- |
| R1 | {…} | {Confirmed / Overturned / Inconclusive / Measured} | {what it does to G…} | [R1](R1_{slug}.md) |

## Amendments this evidence asks for
{Numbered: the charter, decision or acceptance line each verdict changes.}

<!--
Experiment file R{n}_{slug}.md:

# R{n} — {the question as one line}

- **Question:** {what would make the provisional decision wrong}
- **What was run:** {setup, commands, machine, commit sha; spike code in a fenced block}
- **Result:** {measured numbers and raw evidence}
- **Verdict:** {Confirmed / Overturned / Inconclusive / Measured}
- **What it does to G…:** {the decision line it confirms or changes}
-->
