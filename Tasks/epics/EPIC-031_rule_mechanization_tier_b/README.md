# EPIC-031 — The rulebook is enforced by mechanism (Tier B)

- **Status:** ✅ Done (2026-10-04)
- **Repositories:** Elite
- **Origin:** the user, 2026-10-04 — "làm tiếp Tier B đi" (go on with Tier B), with the scope chosen from the audit's Tier B list.
- **North star:** `.claude/CONSTITUTION.md` P1, after [EPIC-030](../EPIC-030_rule_mechanization_tier_a/README.md) made the rule tags honest
- **Dependencies:** EPIC-030; the `master-warrior` ruleset (user action) to require the new checks

---

## 1. Decisions already made
1. In scope: commit lint and the independent-review status, the engine pin and lockfile, Claude Code hooks.
2. Out of scope by the user's choice: mypy override and exclude fixes, new ruff rules, shrink-only ratchets.
3. Independence is shown by self-reported `Claude-Session:` URLs, because every session posts from one GitHub account: it separates sessions that follow the process, not a deliberate bypass. Only owner, member or collaborator comments count, the newest verdict line decides, and every commit must carry its session.

## 2. Goals — measurable
| Metric | Today (measured 2026-10-04) | When the epic is done |
| :--- | :-: | :-: |
| Commit-format rules checked by a machine | 0 | subject, type, body, trailer, fix id |
| Independent review checked by a machine | no | `independent-review` status |
| Engine and dependency versions pinned in CI | 3 of 16 direct, engine floating | all, engine by sha |
| Agent rules enforced by a tool hook | 0 | 2 |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-031A](completed/EPIC-031A_process_gates.md) | Commit format and independent review are checked by CI | Elite | EPIC-030 | 🟡 | Done |
| [EPIC-031B](completed/EPIC-031B_pinned_builds.md) | Two runs of one commit build the same thing | Elite | EPIC-030 | 🟡 | Done |
| [EPIC-031C](completed/EPIC-031C_claude_code_hooks.md) | Two agent rules are barriers in the tool itself | Elite | EPIC-030 | 🟡 | Done |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| One pull request | The three mechanisms run and refuse a planted breach | Unit tests; the pull request's gate run and independent review |

## 5. Out of scope
The audit's other Tier B items (mypy, ruff, ratchets), and making `commit-lint` and `independent-review` required in the ruleset, which is the user's action in GitHub.

## Notes (newest first)
- **2026-10-04** — Epic delivered in one pull request.
