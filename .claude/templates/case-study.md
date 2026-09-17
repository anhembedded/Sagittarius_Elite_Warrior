---
description: The format of a case study under Docs/CASE_STUDIES/ — why the gate was green while it was broken. Three required sections, 35 lines at most, the check ships in the same commit. Copy it, fill every brace, delete this front matter, add the index row.
---

# CS-{nnn} — {the mechanism as a phrase: "the port nobody bound"}

{Two to four sentences: the bug id, what reached the user, and that the gate was green. Numbers measured from the runs, not inherited.}

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| {the test, guard, type check or review row that covered the area} | {the specific reason it looked away} | {no — what closes it · **yes**: where} |

## The fix
- {the check that exists now, by path — it ships in this same commit}
- {the code change, one line}

## Where else this is still open
- {the same blind spot elsewhere, with a path and a linked task or bug tracking its closure}
