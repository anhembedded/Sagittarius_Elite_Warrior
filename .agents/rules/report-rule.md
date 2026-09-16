---
name: Report Rule
description: The shape of every report back to the user — context, one diagram, then the numbers with their targets; Vietnamese in chat, English in the repository.
trigger: always_on
---

# Reporting rule — how work is reported back to the user

**Why this rule exists.** On 2026-09-14 the user read a report of `EPIC-025` PR 0.3 and said
*"bạn report kiểu vậy tui không hiểu gì hết"* — "reporting like that, I understand nothing." The
report was not wrong; it was written from inside the work. It opened with an allowlist count, named
six modules by file path, and explained a deferral in terms of `PythonBinanceClient` — none of
which means anything to someone who did not just spend an hour in the code. A report the reader
cannot use is not a report, it is a log.

This rule is about **the shape of the answer**, not its honesty: nothing here licenses hiding a
failure, softening a number, or dropping the bad news. It says where the bad news goes so the
reader actually sees it.

## 1. Every report has the same three parts, in this order

| Part | Answers | Length |
| :--- | :--- | :--- |
| **Context** | Where are we, what was the problem, why does this step exist at all? | 2–4 sentences |
| **Design** | A picture of the mechanism or the change — before / after, or the shape of the thing | 1 diagram |
| **Applied** | What is now true in the running system, what the numbers moved to, what the reader must decide | a table plus one short list |

A report missing **Context** reads as a changelog. Missing **Design**, the reader has to build the
picture from prose. Missing **Applied**, the reader cannot tell whether anything reached the app
they actually run.

## 2. Context comes before vocabulary, always

- **Name the problem in the user's terms first**, the code's terms second. "Two screens rebuilt the
  same logic twice" before `59 duplicated member names`; "the app used to paint every widget itself"
  before `qdarktheme`.
- **Every identifier gets one plain-language gloss at first mention**, in the same sentence.
  `ContributionRegistry` → "the one object a module hands its panels to". No gloss, no identifier:
  say what it does and leave the name out.
- **Locate the step in the plan.** "Third of five pull requests in Phase 0" is one clause and it
  tells the reader how much is left.
- **Never open with a count.** A number the reader cannot yet interpret is noise; move it to
  **Applied**, where the table gives it a unit and a target.

## 3. The design part is a real diagram, and it is the centre of the report

- **One diagram per report, showing the mechanism that changed.** Prefer *before → after* when the
  change is structural, a flow when the change is a sequence, a containment box when the change is
  about who-owns-what.
- **Text diagrams in chat, rendered diagrams in a page.** In the terminal, box-drawing characters
  or a table; in a published page, inline SVG or a Mermaid block
  ([`ui-presentation-rule.md`](ui-presentation-rule.md) governs the look of the page itself).
- **The diagram must be readable with the prose deleted.** Label every box with a role
  ("the one place allowed to build a Binance client"), not only a file name.
- **No decorative diagrams.** A box-and-arrow picture of three files that do not interact is worse
  than no picture; say it in a sentence instead.

## 4. The applied part carries the numbers, and each number carries its target

Every measurement appears in a table with the direction it is supposed to move — a number with no
target cannot be judged:

| Measure | Before | Now | Target |
| :--- | :-: | :-: | :-: |

Then, in at most five bullets: what a user of the app would notice, what the reader must decide, and
what is still open. A report ends on the reader's next action, never on a summary of the work.

## 5. Language and length

- **Vietnamese in chat, Vietnamese in a report page for the user** — that is a conversation with
  the user, and `CLAUDE.md`'s language rule puts conversation in Vietnamese. Everything committed to
  the repository (task files, `Docs/`, ADRs, commit messages, pull-request bodies) stays **English**.
- **A chat report is at most ~250 words plus its diagram and table.** Anything longer belongs in a
  published page, with the chat message carrying the three parts in miniature plus the link.
- **One idea per sentence.** No sentence carries two file paths.

## 6. When a report is owed

- After every pull request that is pushed, merged, or blocked.
- At the end of every phase of a multi-phase epic, with the phase's measurements.
- Whenever the user asks — *"report"*, *"làm được gì rồi"*, *"sao rồi"* — which is a request for all
  three parts, not for the last commit's subject line.
- When a decision was taken on the user's behalf under [`ONBOARDING.md`](../ONBOARDING.md) §7: the
  report says what was decided, what the alternatives were, and where it is written down.

**Bad news keeps the same shape.** A red gate, a deferral, a design that turned out unbuildable —
Context (what the constraint really is), Design (the picture of why it does not fit), Applied (what
is true now and what the reader must choose). Failure reported in this shape is actionable; failure
reported as an apology is not.
