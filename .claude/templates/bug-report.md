---
description: The format of a bug report under Tasks/bug_report/incomplete/ (bug-fix-rule.md §7). Copy it, fill every brace, delete this front matter.
---

# BUG-{nnn} — {the symptom as the user met it, one line}

- **Reported:** {YYYY-MM-DD} ({by whom and where: chat, a review, a scheduled run})
- **Severity:** 🔴 P1 · 🟡 P2 · 🟢 P3 — {what it costs the user}
- **Status:** Open · ✅ Fixed {YYYY-MM-DD} — root-caused / reproduced / regression-tested / verified

## Symptom
{The real evidence, pasted: the traceback, the log lines, the screenshot path. What was expected instead.}

## Root cause
{The mechanism with `file:line`, and why the fix resolves it without crossing a layer. When the gate was green: which net was silent, and whether a case study follows (`bug-fix-rule.md` §6.5).}

## Fix
{What changed, per file, and why it is the mechanism and not the symptom (`bug-fix-rule.md` §2).}

## Regression test
{`tests/{tier}/{file}::{test}` — failed before the fix for this reason: {…}; passes after. The tier reaches the crash; no `Mock` stands in for it.}

## Suggested next steps
{Only while the status is Open.}
