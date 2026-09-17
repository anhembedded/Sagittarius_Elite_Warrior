---
name: Report Rule
description: Every report to the user — context, one diagram, the numbers with targets; Vietnamese in chat, English in the repository.
trigger: always_on
---

# Reporting to the user

Written from the reader's side, not from inside the work (2026-09-14: *"bạn report kiểu vậy tui không hiểu gì hết"*). Shape only — never a licence to soften bad news.

## 1. Three parts, in order
| Part | Answers | Length |
| :--- | :--- | :--- |
| **Context** | where we are, what the problem was, why this step exists | 2–4 sentences |
| **Design** | one diagram of the mechanism or the change (before/after, a flow, a containment box) | 1 diagram |
| **Applied** | what is now true in the running system, the numbers, what the reader must decide | a table + ≤5 bullets |

## 2. Context before vocabulary
The user's terms first, the code's second; every identifier glossed once at first mention or left out; locate the step in the plan ("third of five PRs in Phase 0"); never open with a count.

## 3. The diagram
One per report, labelled by role not file name, readable with the prose deleted; text diagrams in chat, SVG/Mermaid in a page; none if the boxes do not interact.

## 4. The numbers
| Measure | Before | Now | Target |
| :--- | :-: | :-: | :-: |

A number without a target cannot be judged. End on the reader's next action, never on a summary of the work.

## 5. Language and length
Vietnamese in chat and in a page for the user; everything committed is English. A chat report is ≤ ~250 words plus diagram and table — longer goes to a page with the three parts in miniature and a link. One idea per sentence; never two file paths in one.

## 6. When owed
After every pull request pushed, merged or blocked; at the end of every epic phase with its measurements; whenever the user asks ("report", "sao rồi"); whenever a decision was taken on the user's behalf (`ONBOARDING.md` §7) — say what, the alternatives, where it is written. Bad news keeps the same three parts.

## 7. A question to the user carries its context (user decision 2026-09-13)
What the code does today; why it became a decision now; each option by the consequence the user will feel; your recommendation; what "yes" commits them to. One screen, no reading required. A question made of labels ("approve D17") is sent back.
