# BOT-137 — Make PR review concise and correctly scoped

**Status:** ✅ Done (2026-09-17)
**Source:** User, 2026-09-17: "đánh giá xem rule này có thừa thải không, tôi muốn nó tối giải và hiểu quả hơn" ("Assess whether this rule is redundant; I want it simpler and more effective").
**Risk:** 🟢 — Review instructions and navigation only; existing rule obligations remain authoritative.
**Complexity:** S — Rewrite the workflow and compact the review prompts.
**Depends on:** None.

## 1. Context and problem
The PR review skill contains 284 lines and 3,939 whitespace-delimited words, including repeated rule text, incident histories and shell recipes. Its working-diff commands omit uncommitted changes; routing misses module domain and UI paths; mutation instructions conflict with the read-only reviewer role. Timestamp comparison does not identify the verified tree.

## 2. Acceptance criteria
- [x] Reduce the skill's word count by at least 40% while keeping the existing checklist IDs available to their callers.
- [x] Distinguish branch, working-tree and documentation-only reviews; include module and support code in routing.
- [x] Preserve final-tree verification, actionable findings and mutation evidence without editing the reviewed checkout.
- [x] Pass the skill validator, reference checker and required documentation guards.

## 3. Design
Keep one skill file with a short workflow, scope routing and compact review prompts. Authoritative rules remain in their existing files; preserve A1–L6 identifiers rather than rewriting their callers. Read only the relevant rule groups. Report evidence gaps separately from confirmed defects and avoid demanding future merge evidence during an early working-tree review.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/skills/pr-review/SKILL.md` | Simplify instructions and correct scope and evidence handling. |
| `.claude/agents/reviewer.md` | Align the reader's entry instruction with the simplified skill. |
| `.claude/README.md` | Regenerate the manifest if skill metadata changes. |
| `Tasks/ROADMAP.md` | Record completion and regenerate task counts. |

## 5. Testing
Validate skill metadata with skill-creator's quick validator. Run the reference checker and the five documentation guards from ONBOARDING §7. Compare checklist identifiers with the original and manually walk the routing for working-tree, documentation, module UI and guard changes.

## Implementation notes

The skill now has 117 lines and 1,837 whitespace-delimited words, down from 284 lines and 3,939 words (53.4% fewer words; target at least 40%). All 91 original checklist IDs remain available. Repeated incident histories and shell recipes were removed; authoritative rule files still own the obligations. The reviewer entry now follows the scope router and does not mutate files to obtain mutation evidence.

Manual routing checks: uncommitted reviews include tracked and untracked content; documentation-only reviews select document verification; module UI selects UI/contracts and async checks when relevant; guard changes select ratchet/registry checks. Early working-tree reviews report outstanding merge evidence without pretending the change is ready. Final verification is tied to a revision/snapshot rather than timestamps alone. These are instruction inspections, not a measured improvement in real review accuracy.

Validation: the skill-creator quick validator passed; all 91 IDs were compared with the original; all 112 documentation guard tests passed. Pytest reports one environment warning for the unrecognised `timeout` option. During this task, an external edit renamed the bug workflow rule to `fix-bug-rule.md`; this skill follows that name. The normal reference checker failed because that new file was untracked. It passed for all 29 documents using a temporary copy of the Git index containing the rename, without staging or changing that external work. The real index still needs the rename recorded before the normal checker can pass. No runtime code or tests were changed by this task.
