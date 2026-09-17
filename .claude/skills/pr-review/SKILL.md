---
name: pr-review
description: Review a PR, branch or uncommitted diff for concrete defects, repository-rule violations and verification gaps. Use for requested reviews and pre-merge checks.
---

# PR Review

Find defects introduced by the change and consequential violations of the repository's rules. Confirm evidence rather than repeating the author's claims. Review the diff and affected callers; do not turn a review into a repository-wide cleanup.

## 1. Load the right change

Read `CLAUDE.md`, `.claude/ONBOARDING.md` §7 and `.claude/rules/ci-rule.md` §1. Enumerate `.claude/rules/` recursively, then read the unscoped rules and the scoped rules relevant to the changed paths and behavior. The routing below is a starting point, not a replacement for their `paths:` declarations.

| Review target | Read |
| :--- | :--- |
| PR or branch | Fetch its base and head; record both SHAs. Use `git log BASE..TIP` and `git diff -M BASE...TIP`, with BASE and TIP replaced by the actual refs. |
| Uncommitted work | `git status --short`, `git diff -M HEAD`, and the contents of relevant untracked files from `git ls-files --others --exclude-standard`. If only staged changes were requested, use `git diff --cached`. |
| Branch plus local changes | Read both scopes above and report their boundaries explicitly. |

Read the whole diff, paging when needed, and the surrounding code at the reviewed revision. Follow changed contracts to callers and implementers. Run checks against that revision in an isolated checkout when the current one differs; do not switch or overwrite the user's working tree. Without a checkout, read full files through available repository tools and distinguish inspected evidence from executed checks. Record any unread portion.

## 2. Route by scope

Resolve rule names below under `.claude/rules/`. Use their current clauses, not copied thresholds or remembered section numbers. Confirm machine-enforced checks ran; spend manual review on semantics and gaps they do not cover.

| Change | Review groups and authority |
| :--- | :--- |
| Every change | A, K; `ONBOARDING.md`, `report-rule.md`. L for existing commits; L4/L5 also for uncommitted changes. |
| Anything outside ONBOARDING §7's documentation-only set | B; `ci-rule.md`. C/D for affected source, scripts, tools and tests; `architecture-rule.md`, `code-quality-rule.md`. Build/config/workflow changes also need their applicable rules. |
| Behavior or tests | E; `testing-rule.md`. Bug fixes also read `fix-bug-rule.md`. |
| Domain/application behavior, including module code and displayed trading facts | F; `domain-truth-rule.md`. |
| UI, including `src/modules/*/ui/`, `src/support/ui_kit/` and charting | H and C4/D5; `ui-presentation-rule.md`. Background actions also G and `async-ui-action-rule.md`. |
| Logging or failure paths | I; `logging-rule.md`. |
| Guards, baselines, allowlists, package moves or new packages | J; `ci-rule.md`, the affected guard and its governing rule. |
| Documentation only | A/K and applicable L checks; run ONBOARDING §7's document guards and reference checker. No runtime gate. |

Read relevant `rules/pitfalls/` files with their area. Consult `Docs/CASE_STUDIES/README.md` for a green-gate escape and `Docs/VOCABULARY/README.md` for an unfamiliar term. A changed use case also requires its SPEC; a decision must be checked against the applicable epic and ADR.

## 3. Review prompts

IDs remain stable because rules and tests cite them. Apply only relevant prompts; they route inspection and do not redefine their governing rules. A slash between IDs groups related checks, not alternative obligations.

| IDs | Check |
| :--- | :--- |
| A1/A2 | Does the change satisfy the stated outcome, stay in scope and form one logical change? |
| A3 | For a claimed move, inspect rename similarity and every behavior-changing hunk. |
| A4/A5 | Are decisions within ONBOARDING §7 authority, and new mechanisms justified against existing solutions? |
| A6 | Is deferred work recorded with its reason and plan entry? |
| B1/B2/B3 | Is the required gate mode supported by its actual log, scan results and an explanation of warning/error hits? Apply the documentation exception first. |
| B4/B5 | Are failures investigated and required checks executable? Follow `install-rule.md` for missing tools; distinguish an external blocker from a failed check. |
| B6 | Does verification identify the reviewed revision and required cadence? See §4. |
| C1/C2 | Do dependencies obey layer and module boundaries, including imports back into the legacy tree? |
| C3 | After a port changes, inspect every implementer in `src/`, `scripts/` and `tests/`. |
| C4/C5 | Are boundary contracts explicit, and is Protocol use justified under the architecture rule? |
| C6/C7 | Are abstraction levels separated? Check size thresholds once under D6/D7. |
| C8/C9 | Are events placed correctly, and agreed extension points and trade-offs expressed in code/tests? |
| C10 | Do inheritance and construction preserve the required abstraction and injection boundaries? |
| D1/D2 | Confirm lint/security checks through B; do not repeat lint by eye. |
| D3/D4/D5 | Inspect new suppressions, local imports and erased or missing types; check areas excluded from mypy explicitly. |
| D6/D7 | Measure changed files/classes against the current size thresholds in `architecture-rule.md`. |
| D8/D9 | Does grouping reflect one lifecycle and responsibility, rather than only the same feature? |
| D10/D11 | Check argument mutation, nested loops and low-level I/O placed outside adapters/utilities. |
| E1/E2 | Does existing or new evidence reach the changed behavior at the required tier and assert the business outcome? |
| E3/E5/E6 | Check deterministic waits and the sanity tier's real-boot, shared-scan and configuration-boundary contract. |
| E4/E11 | For removed or rewritten tests, map each prior guarantee to its replacement or documented retirement; reject weakened coverage used to obtain green. |
| E7/E8 | Inspect meaningful assertions, boundary/mutation evidence for consequential calculations and compatibility of frozen-dataclass additions. |
| E9/E10 | For a bug fix, verify red-before/green-after evidence reaches the failure and the fix addresses its mechanism. |
| E12 | For wiring tests, inspect evidence that removing the connection makes the test fail for the intended reason. Use §4's isolation constraints. |
| E13 | Compare each double with the real interface; prefer a cheap real collaborator over an invented interface. |
| E14 | Apply all eligibility conditions in `fix-bug-rule.md` §6.5 before requiring a case study and its same-commit check. |
| E15 | Verify construction, binding and subscription through the production composition graph, not only a test's setup or a name match. |
| F1/F2 | Check real coverage/metadata and distinct signal, intent, fill and position semantics. |
| F3/F4/F5 | Check truthful UI promises, immutable bounded snapshots with provenance, and reproducible performance claims. |
| G1/G2 | Trace action identity through callbacks, stale-result fencing, cancellation and terminal outcomes. |
| G3/G4/G5 | Check single state ownership, Presenter-owned injection and work lost after a throwing UI call. |
| H1/H2 | Confirm the UI guards and shrink-only styling baselines through B/J. |
| H3/H4 | Check standard desktop controls and shortcuts, content sizing and overflow behavior. |
| H5/H6/H7 | Check preview coverage, shared table sizing, cancellation, progress and actionable errors. |
| I1/I2 | Confirm logger namespace coverage; inspect noisy logging in hot paths. |
| I3/I4/I5 | Does logging explain the decision at the right level/tag, and has the diagnostic emitted through the real configuration? |
| J1/J2 | Compare baseline/allowlist entries: no growth; removals must correspond to fixes or justified retirements. |
| J3/J4/J5 | Check scan roots, moved path constants, declarations and registries for additions or moves; an empty scan is not coverage. |
| J6 | If a newer ADR reverses a guard's premise, verify the documented exemption/retirement under `ci-rule.md` §5, never a relaxed ceiling. |
| K1/K2 | Check task/epic/bug state and board consistency against the actual work. |
| K3/K4 | Check design and SPEC changes against behavior, including failure outcomes and proof links. |
| K5/K6 | Check new vocabulary and the repository's language/register requirements. |
| K7/K8/K9 | Check navigation, derived manifest, reference validity and current-state claims under ONBOARDING §13. |
| L1/L2/L3 | Check existing commit messages, reasoning, bug IDs and attribution against `commit-rule.md`; no missing-commit finding on uncommitted work. |
| L4/L5/L6 | Inspect accidental artifacts/secrets, authority for dependency/config changes and each commit's complete contents. |

## 4. Verify the evidence

Use `ci-rule.md` for required commands and cadence. Do not re-run all checks simply because a review started when trustworthy evidence already covers this revision; run the focused checks needed to resolve a finding or an evidence gap. Before calling a PR ready, all required final-tree evidence must exist. During an early working-tree review, state outstanding verification without claiming readiness.

For B6, match CI's recorded head SHA or the local run's recorded revision and working-tree state to the reviewed snapshot. Timestamps alone do not establish identity. An uncommitted snapshot can be tested, but a changed snapshot needs fresh evidence; absent identity is an evidence gap, not proof the code is broken.

For E7/E12, inspect reproducible mutation evidence or perform the focused mutation in a disposable copy of the reviewed snapshot, only if the reviewer role permits writing there. Establish a passing baseline, introduce one fault, and confirm failure for the intended reason. Never mutate the user's checkout. A read-only reviewer reports missing evidence or requests it rather than silently skipping the obligation. Restore any temporary mutation before subsequent checks.

For each proposed finding: inspect the current file and affected path, confirm the source rule when alleging a violation, and check the base revision to distinguish a new defect from an existing one. Account for accepted trade-offs and explicit deferrals. A code defect need not violate a written rule; show the trigger and consequence. State when reproduction was not possible rather than inventing output.

## 5. Grade findings

- **Blocking:** a demonstrated defect, consequential rule violation or unmet verification required for merge.
- **Should fix:** a concrete issue with a stated consequence that does not block this change.
- **Question:** missing information prevents a conclusion; explain what evidence resolves it.

Report preferences only when requested. Keep pre-existing issues separate and mention them only when they affect the change. Combine findings with the same root cause; no concrete consequence means no defect finding.

## 6. Report

Lead with the conclusion and scope/revision. List findings by severity, each with `file:line`, trigger, consequence, supporting evidence and the governing clause when applicable. Then state checks run or evidence inspected, relevant groups covered, and unread or unverified portions. Follow `report-rule.md` for language and reader context. "No findings" is valid; it does not imply verification that did not run.

Return the review in chat unless posting was explicitly authorised by the user or invoking workflow. If posting is authorised, use one grouped review in English. Distinguish the author's subagent pre-check from the independent session required by ONBOARDING §7.

## 7. Boundaries

Reviewing does not authorise fixing files, staging, committing, pushing, approving or merging. Keep the reviewed checkout unchanged; the reviewer role may restrict even disposable mutation work. Any separately delegated merge follows ONBOARDING §7. Do not weaken a rule, test or guard to make the change pass, demand work already scheduled elsewhere, or judge the author instead of the change.
