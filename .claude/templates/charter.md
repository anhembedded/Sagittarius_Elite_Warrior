---
description: The format of an epic's charter (Clarify) in the README.md of the epic's charter/ folder (Tasks/epics/README.md) — why the epic exists, its scope, constraints and acceptance; no solution chosen. Conditional: section 4 of the create-epic skill decides. Copy it, fill every brace, delete this front matter and instructional comments.
---

# Charter — EPIC-{nnn} {short title}

<!-- Write a charter only when section 4 of the create-epic skill calls for one. An accepted PRO-nnn replaces it: link the proposal from the epic README instead of restating it. -->
| Field | Value |
| :--- | :--- |
| Document type | Charter (Clarify): why, what, scope, constraints, acceptance; no solution is chosen |
| Epic | EPIC-{nnn} — {the outcome} |
| Version | {0.1} ({Draft / Approved}) |
| Status | {one line: what is settled, what waits for whom} |
| Origin | {the owner's words quoted once and translated} |
| Next step | {Discover / De-risk / decision records / scaffolding} |

**Revision history**

| Version | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| {0.1} | {YYYY-MM-DD} | {who} | {initial draft from …} |

---

## 1. Problem
### 1.1 Background
{The context the reader needs, linked rather than restated.}

### 1.2 Problem statement
{The current pain, with dated evidence: logs, incidents, measurements. Separate facts from unknowns.}

## 2. Objectives
### 2.1 Requirement versus solution
{The requirement in the owner's terms. Candidate solutions are listed for Discover and De-risk to examine; none is chosen here.}

### 2.2 Objectives
| ID | Objective | Measure |
| :--- | :--- | :--- |
| O1 | {…} | {…} |

## 3. Deliverables
| ID | Deliverable | Objective |
| :--- | :--- | :--- |
| D1 | {…} | {O1} |

## 4. Scope and open decisions
**In scope:** {bullets}

**Out of scope:** {bullets, and where each lives instead}

| ID | Open decision | Candidates | Settled by |
| :--- | :--- | :--- | :--- |
| G1 | {…} | {…} | {Discover / De-risk / owner} |

## 5. Constraints and assumptions
### 5.1 Constraints
{Real money, layers, dependencies, Engine, secrets: each one line, cited to its rule.}

### 5.2 Assumptions
| ID | Assumption | How it is verified | Status |
| :--- | :--- | :--- | :--- |
| A1 | {…} | {De-risk Rn / owner's run} | {Open / Holds / False} |

## 6. Acceptance
| ID | Criterion | Metric | Target | How measured |
| :--- | :--- | :--- | :--- | :--- |
| AC1 | {…} | {…} | {…} | {test, measurement or owner's check} |

## 7. Approval
Approval of the scope and constraints, to proceed to the next step (not to build, not a choice of solution).

| Name | Role | Decision | Date |
| :--- | :--- | :--- | :--- |
| {owner} | Owner | {Pending} | {Pending} |
