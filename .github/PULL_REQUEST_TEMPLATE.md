<!-- The body of every pull request. GitHub fills this in; keep the four headings, delete this comment. -->

## What

<!-- One bullet per logical change, in the order of the commits. Task or bug id in the first bullet. -->

## Why

<!-- The problem, with evidence (file:line, a measured number, the user's words quoted once). A design choice names the pattern it applies. -->

## Root cause

<!-- Required for `fix:`; delete otherwise. The mechanism, with `file:line`. -->

## Corrective action

<!-- Required for `fix:`; delete otherwise. What changed and why it fixes the mechanism. -->

## Sequence: before

<!-- Required for `fix:`; delete otherwise. One ```mermaid sequenceDiagram block over the real participants, marking the step where the defect happened; or `Not applicable: <reason>` when the defect is local to one function or one piece of text. -->

## Sequence: after

<!-- Required for `fix:`; delete otherwise. The same diagram, marking where the fix acts; or `Not applicable: <reason>`. -->

## Verification

<!-- A bug fix: its regression test, red before the fix and green after, and the commit tier (ci-rule.md §1, "Bug fix"). Otherwise: the GitHub Actions `ci-local.ps1 -Full` run on this PR's head sha, and what the grep of its job log found. Guards touched and why. Documentation-only (ONBOARDING §7): say so and name the doc guards run. -->

## Design

<!-- Required when this changes src/modules/<m>/ for a module with a Docs/MODULES/<m>/ folder (commit-rule.md §1, "Design in step"; checked on every pull request). List the folder's files this updates, or write the one line `No design change: <reason>`. -->

## Docs touched

<!-- Each other document under Docs/ this change updates, or "none, because …". -->
