# PR Review Inspection Rubric (A1–M6)

Stable inspection checklist for `.claude/skills/pr-review/SKILL.md`. Every item defines a concrete, non-overlapping inspection directive.

| ID | Inspection Directive |
| :--- | :--- |
| **A1** | Verify change satisfies the requested outcome and acceptance criteria stated in the task or PR. |
| **A2** | Verify bounded scope: change represents one logical change without opportunistic side edits. |
| **A3** | Inspect rename similarity and verify no unintended behavioral hunks exist in claimed file moves. |
| **A4** | Ensure architectural decisions remain within `.claude/ONBOARDING.md` §7 authority levels. |
| **A5** | Enforce P5 Technical Choice Hierarchy: reject duplicating brittle repo patterns; reject bespoke inventions when stdlib or vetted standards exist. |
| **A6** | Verify deferred work is recorded in task plans with explicit technical rationale. |
| **B1** | Confirm machine gate execution log exists and is cited with an exact file path. |
| **B2** | Inspect full log output directly; explain all warning and error occurrences. |
| **B3** | Verify documentation-only exception applies only when no runtime code or tests were modified. |
| **B4** | Verify failures are diagnosed at the mechanism layer per P6 (redesign hard designs; cost is never an excuse for a local hotfix). |
| **B5** | Confirm missing tools or dependencies are installed automatically per `.claude/rules/install-rule.md`. |
| **B6** | Ensure verification evidence matches the reviewed revision commit SHA. |
| **C1** | Verify strict layer boundaries (Domain → Application → Adapters → Infrastructure); dependencies point inward. |
| **C2** | Prohibit illegal inward imports into legacy trees or between bounded contexts without contracts. |
| **C3** | After port modification, inspect all implementers across `src/`, `scripts/`, and `tests/` (`BUG-026`). |
| **C4** | Verify boundary contracts are explicit named types; reject unannotated objects or dynamic attribute probing. |
| **C5** | Enforce ABC as default; Protocol only for Shiboken/QObject or third-party constraints with documented reason (`.claude/rules/architecture-rule.md`). |
| **C6** | Enforce abstraction-level separation: two abstraction levels never share a file or directory. |
| **C7** | Enforce architectural size thresholds: >400 lines per file or >15 public methods per class triggers a split. |
| **C8** | Verify event placement: thread hop uses queued Qt signal/bridge; system-wide truth uses the event bus with one Feed. |
| **C9** | Verify agreed extension points (seams) contain clean base/ABC landing spots with zero speculative variants (P7). |
| **C10** | Verify composition, injection, and inheritance maintain loose coupling; no multiple inheritance. |
| **D1** | Confirm machine lint passes cleanly (`ruff check`); reject manual eye-balling of format/lint. |
| **D2** | Confirm security checks pass (`ruff` ruleset `S` / Bandit); no hardcoded secrets or unsafe deserialization. |
| **D3** | Verify no bare `# noqa` suppressions; per-file ignores must be declared in `pyproject.toml` with inline rationale. |
| **D4** | Prohibit function-local imports: all imports at top of file, except top-level `if TYPE_CHECKING:`. |
| **D5** | Prohibit `Any` type annotations where specific types/generics fit (`CS-001`); inspect presentation types. |
| **D6** | Measure classes against architectural size limits (max 15 public methods). |
| **D7** | Measure files against architectural size limits (max 400 lines). |
| **D8** | Enforce Single-Scope Cohesion: definitions of one lifecycle (FSM enum, events, matrix) must live in one `*_fsm_matrix.py` file. |
| **D9** | Prohibit God objects: split any class or module with more than one reason to change. |
| **D10** | Verify immutability: pure functions, frozen dataclasses, no argument mutation, no mutable default arguments (`ruff B006`). |
| **D11** | Prohibit low-level OS/file/byte operations inline in application or composition-root code; extract to utility adapters. |
| **E1** | Ensure test coverage exercises changed behavior at required tier and asserts business outcomes. |
| **E2** | Verify test asserts meaningful domain/application invariants, not trivial mock echoes. |
| **E3** | Check deterministic waits: reject arbitrary sleeps (`time.sleep`) in all test tiers. |
| **E4** | Prohibit deleting, skipping, or weakening tests to pass CI (`.claude/CONSTITUTION.md` P8). |
| **E5** | Verify sanity tier boots real composition root and cleans up without warnings or resource leaks. |
| **E6** | Verify test execution cleans up Qt objects and OS resources without gate stall (`BUG-118`). |
| **E7** | Verify boundary and mutation evidence for mathematical calculations and exchange filters. |
| **E8** | Verify dataclass and value object immutability under concurrent or sequential operations. |
| **E9** | For bug fixes, verify regression test was confirmed failing (red) before the fix was applied. |
| **E10** | For bug fixes, verify the repair resolves the defect mechanism (green) without local symptomatic band-aids. |
| **E11** | Verify documented retirement conditions before retiring or replacing any existing test. |
| **E12** | Verify wiring tests fail for the intended structural reason when the connection is broken. |
| **E13** | Compare doubles to real interfaces; prefer lightweight real collaborators over invented mocks. |
| **E14** | Enforce case-study criteria in `.claude/rules/fix-bug-rule.md` §6.5 when a green gate missed a defect. |
| **E15** | Assert composition graph wiring and event subscriptions against production graph. |
| **F1** | Verify real market data coverage and absence of synthetic gaps or unrecorded bars. |
| **F2** | Enforce distinct order fill, execution, and position semantics; no synthetic fills. |
| **F3** | Enforce truthful UI state promises: UI shows only states the engine can guarantee. |
| **F4** | Require immutable domain snapshots with full provenance tracking. |
| **F5** | Ensure reproducible trading metrics, PnL calculations, and deterministic financial calculations. |
| **G1** | Trace async action identity: ensure background jobs have unique traceable identifiers. |
| **G2** | Enforce stale-callback fencing and cooperative cancellation for background tasks. |
| **G3** | Check single state ownership: Presenter owns UI state; View and Coordinator do not duplicate it. |
| **G4** | Ensure Presenter-owned injection: dependencies injected at construction, not dynamically discovered. |
| **G5** | Verify exception resilience in UI callbacks: background failures do not crash the Qt event loop. |
| **H1** | Verify UI styling guards: no hardcoded color hexes; use design system tokens/palette. |
| **H2** | Enforce shrink-only styling baselines. |
| **H3** | Verify standard desktop navigation and keyboard shortcut bindings. |
| **H4** | Check content overflow behavior and responsive widget layouts under resize. |
| **H5** | Verify `preview.py` coverage for new or modified UI components. |
| **H6** | Check table column autosizing, header formatting, and visual alignment. |
| **H7** | Verify actionable user feedback: progress bars, spinners, and clear error notifications. |
| **I1** | Confirm structured logger namespace coverage: namespaces follow `"App.<module>.<class>"`. |
| **I2** | Flag noisy or high-frequency logging in hot paths (move to `TRACE`). |
| **I3** | Check log levels: `ERROR` only for actual errors; `DEBUG` for diagnostic context; no `print()`. |
| **I4** | Ensure diagnostic output routes through real logging configuration, not stdout. |
| **I5** | Verify log promotion: temporary diagnostic logs are either promoted to permanent structured logs or deleted. |
| **J1** | Verify baselines and allowlists only shrink; reject any baseline growth. |
| **J2** | Verify complete coverage of allowlists: every entry must correspond to an existing file/exception. |
| **J3** | Verify test scan roots and path constants; reject vacuous empty scans. |
| **J4** | Prohibit silent skips or unverified fallback branches in test suites. |
| **J5** | Verify guard failure produces clear, actionable error messages with remediation steps. |
| **J6** | Confirm ADR documentation for any guard retirement or exception granting. |
| **K1** | Verify task and epic status consistency against actual code state. |
| **K2** | Verify bug report lifecycle state in `Tasks/bug_report/` matches fix and board entries. |
| **K3** | Verify specifications (`Docs/SPEC/`) update atomically with user-visible behavior changes. |
| **K4** | Verify High-Level Design documents (`Docs/HLD/`) update atomically with structural changes. |
| **K5** | Enforce vocabulary updates in `Docs/VOCABULARY/` when coining or altering domain terms. |
| **K6** | Enforce English technical register across all code, identifiers, docstrings, commits, and docs. |
| **K7** | Verify all navigation links and clickable markdown links resolve to valid targets. |
| **K8** | Verify manifest table synchronization in `.claude/README.md`. |
| **K9** | Verify path validity under `.claude/ONBOARDING.md` §13 via `check_skill_prompt_references.py`. |
| **L1** | Verify Conventional Commit format: `<type>(<scope>): <subject>`. |
| **L2** | Verify commit body explains architectural reasoning and systemic impact (cites root cause for `fix:`). |
| **L3** | Verify required trailers: `Co-Authored-By:` and session metadata where applicable. |
| **L4** | Verify no scratch files, debug `print()` statements, or temporary test code in diff. |
| **L5** | Verify no credentials, secrets, API keys, or `.env` entries in git-tracked files. |
| **L6** | Prohibit unapproved dependency or configuration edits (`pyproject.toml`, `requirements.txt`). |
| **M1** | Verify section and citation references resolve (`§N` markers, rule citations resolve to live files). |
| **M2** | Verify all review tags (`[review: <ID>]`) cited in rules and templates map to defined rubric IDs. |
| **M3** | Verify manifest table (`.claude/README.md`) synchronizes with tree via `scripts/render_claude_manifest.py`. |
| **M4** | Constitutional alignment: prompt/rule edits do not contradict, waive, or weaken any Constitutional invariant. |
| **M5** | Verify always-loaded line budget: always-loaded text stays strictly under ceiling (≤380 lines). |
| **M6** | Verify frontmatter schema: every skill/rule/agent declares valid `description`, `name`, and `paths` if scoped. |
