# ADR — The history of a rule lives in this ledger, not in the rule

**Epic:** [EPIC-030](README.md)
**Date:** 2026-10-04
**Status:** Accepted
**Decided by:** the user, approving `EPIC-030` Tier A ("oki làm đi bạn" — go ahead), which applies the 2026-09-16 strategic review's S1 (`Tasks/reports/ai_process_strategic_review_2026-09-16.md`).

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🟢 User decision | decided by the user; quoted verbatim, then translated |

## 1. Context
Rules loaded into every session had grown dated amendments ("user decision 2026-10-03", "PR #230") inside their clauses: twelve in `.claude/ONBOARDING.md`, `ci-rule.md`, `architecture-rule.md`, `install-rule.md` and `ui-presentation-rule.md`. A norm mixed with its changelog costs context on every session and drifts. `EPIC-030C`'s checker now refuses a date or a pull request number in a rule; this ledger keeps the provenance it removed.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | Rule text states the norm; its date and origin are recorded here | Accepted | 🟢 user, via S1 | Rules shrink; provenance stays one link away |

## 3. Provenance removed from the rules
| Rule and clause | Provenance |
| :--- | :--- |
| `ci-rule.md` §1, "Pre-PR / Done" row: GitHub Actions' `-Full` run is the full-gate authority | 🟢 user decisions 2026-09-18 (no local full gate before a PR) and 2026-10-03 (the reviewer reads that run, does not re-run it) |
| `ONBOARDING.md` §5, the full gate is GitHub Actions' run | 🟢 same two user decisions |
| `ONBOARDING.md` §7, the reviewer's gate evidence | 🟢 user decision 2026-10-03 |
| `ONBOARDING.md` §7, "Self-verifying spawn prompt" | 2026-09-17, learned in PR #230 |
| `ONBOARDING.md` §7, "Write the spawn prompt in your own words" | 2026-09-18, learned in PR #231 |
| `ONBOARDING.md` §7, "One reviewer session per pull request" | 🟢 user decision 2026-10-02, PR #310 |
| `ONBOARDING.md` §7, "The pull request is the channel between author and reviewer"; `pr-review/SKILL.md` §9 | 🟢 user decision 2026-10-04 (PR #325): asked "có cách nào để section reviewer vs dev tự trao đổi với nhau ko nhỉ?" (can the reviewer and dev sessions talk to each other by themselves?), then approved the proposal with "ok làm đi" (go ahead). Before it, every re-review was relayed by the user, because the author session has no tool that messages an existing session |
| `architecture-rule.md` §7.2.1, Seam now, variant later | 🟢 user decision 2026-09-13 |
| `install-rule.md` §2b, the Linux recipe | measured in a fresh container on 2026-09-16 |
| `install-rule.md` §2b, the checkout directory name | found by PR #256's reviewer on 2026-09-22 |
| `install-rule.md` §3, setup is the agent's job | 🟢 user decision 2026-08-31 |
| `ui-presentation-rule.md` §1, QtWidgets only, OS theme | ADR D20–D22, 2026-09-13 |
| `ui-presentation-rule.md` §2, the seven desktop UX principles | 🟢 user decision 2026-09-13 |
| `ONBOARDING.md` §7, no direct push to `master-warrior`; the documentation-only set | 🟢 user decision 2026-10-04 (B1: the ruleset requires a pull request and the `gate` check) |
