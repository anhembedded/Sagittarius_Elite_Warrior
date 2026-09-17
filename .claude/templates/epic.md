---
description: The format of an epic's README.md under Tasks/epics/EPIC-nnn_slug/ (Tasks/epics/README.md). Copy it, fill every brace, delete this front matter.
---

# EPIC-{nnn} — {the outcome}

<!-- Choose one status and repository scope. Remove optional fields and instructional comments when copying. -->
- **Status:** {🔵 Planned / 🟡 Phase n in progress / ✅ Done (YYYY-MM-DD) / ❌ Cancelled (YYYY-MM-DD; reason)}
- **Repositories:** {Elite / Engine / both}
- **Origin:** {PRO-nnn, or the user's words quoted once and translated}
- **North star:** {the design document under `Docs/` this epic implements; the epic summarises it and does not repeat it}
- **Decisions (optional):** {DECISION_{date}_{slug}.md — one line per record}
- **Dependencies:** {other epic/task links and prerequisites, or None}

---

## 1. Decisions already made
{Numbered, one line each, pointing at the decision record.}

## 2. Goals — measurable
| Metric | Today (measured {date}) | When the epic is done |
| :--- | :-: | :-: |
| {…} | {…} | {…} |

## 3. Sub-tasks, ordered by risk
{Order executable tasks by risk while respecting dependencies. Create each child from the task template, using its EPIC-nnnA id.}

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| {EPIC-nnnA, linked to its task file} | {…} | {Elite / Engine} | {task ids or None} | {🟢 / 🟡 / 🔴} | {Planned / In progress / Done / Cancelled} |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| {phase} | {observable result and target, linked to the goals above} | {test, measurement or manual check; record Not run until verified} |

## 5. Out of scope
{What this epic deliberately does not do, and where that lives instead.}

## Notes (newest first)
- **{YYYY-MM-DD}** — {what changed and why, one line; the commit or pull request}
