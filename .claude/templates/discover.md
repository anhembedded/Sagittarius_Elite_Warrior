---
description: The format of an epic's Discover survey in the README.md of the epic's discover/ folder (Tasks/epics/README.md) — the system read before any technical decision, layer by layer, ending in the unknowns De-risk must prove. Conditional: section 4 of the create-epic skill decides. Copy it, fill every brace, delete this front matter and instructional comments.
---

# Discover — EPIC-{nnn} {short title}

<!-- Write a survey only when section 4 of the create-epic skill calls for one. Cite code by path and symbol at a named commit. A long section, a diagram or an external survey may live in its own file beside this one (Markdown or an image only; any other file makes the pull request code, ONBOARDING §7). -->
| Field | Value |
| :--- | :--- |
| Document type | Discover: system survey before any technical decision |
| Epic | EPIC-{nnn} — {the outcome} |
| Version | {0.1} ({Draft / Reviewed}) |
| Status | {For the owner's review; no solution is chosen here} |
| Inputs | {charter version or PRO-nnn · code read at {branch} {sha} · Engine pin {sha}} |
| Next step | {De-risk / decision records} |

**The question this survey answers:** *{which parts of the system must be understood to settle G…}*

---

## 1. Context — where does the problem live?
{The modules, processes and users involved.}

## 2. Architecture — how is the area organised?
{Components, ports and edges the decision depends on; the size of the seam, measured.}

## 3. Implementation — one flow traced end to end
{The real path, step by step, `path` → `symbol`; what the trace shows.}

## 4. Verification — how would we know it works?
{The test tiers and guards that would prove the outcome; what exists, what is missing.}

## 5. How others solve it (optional)
{Comparable systems or standards, with sources.}

## 6. Findings and the unknowns for De-risk
| ID | Finding or unknown | Effect on the charter | Proved by |
| :--- | :--- | :--- | :--- |
| R1 | {…} | {G… holds / changes} | {De-risk R1 / not needed} |

## Sources
{Links and commit shas read.}
