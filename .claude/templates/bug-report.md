---
description: The format of a bug report under Tasks/bug_report/incomplete/ (fix-bug-rule.md §7). Copy it, fill every brace, delete this front matter.
---

# BUG-{nnn} — {the symptom as the user met it, one line}

- **Reported:** {YYYY-MM-DD} ({by whom and where: chat, a review, a scheduled run})
- **Severity:** {🔴 P1 / 🟡 P2 / 🟢 P3} — {what it costs the user}
- **Status:** {Open / ✅ Fixed (YYYY-MM-DD)}
- **Environment:** {OS, app and engine commit/version, relevant configuration; Unknown if not captured. Never include credentials.}

<!-- Choose one severity and status. An open report may say Not yet established or Not run; never invent a root cause or a passing check to fill the form. Delete instructional comments. -->

## Reproduction
{Preconditions and the minimum numbered steps, with expected and actual results. State frequency, or Not yet reproduced and the missing evidence.}

## Symptom
{The real evidence, pasted: the traceback, the log lines, the screenshot path. What was expected instead.}

## Root cause
{The mechanism with `file:line`, and why the fix resolves it without crossing a layer. When the gate was green: which net was silent, and whether a case study follows (`fix-bug-rule.md` §6.5).}

## Fix
{What changed, per file, and why it is the mechanism and not the symptom (`fix-bug-rule.md` §2).}

## Regression test
{`tests/{tier}/{file}::{test}` — failed before the fix for this reason: {…}; passes after. The tier reaches the crash; no `Mock` stands in for it.}

## Verification
{Not run, or the commands, results, checked commit and log path. Include positive evidence that the repaired mechanism ran when reproducing again (`fix-bug-rule.md` §3), plus the required gate result. Link the case study when one was required.}

## Suggested next steps
{Only while the status is Open.}
