# BOT-140 — Separate bug reporting from bug fixing

**Status:** ✅ Done (2026-09-17)
**Source:** User, 2026-09-17: "tach fix bug rule với creating bug report thành 2 rule riêng" ("Separate the bug-fixing rule and bug-report creation into two rules").
**Risk:** 🟢 — Documentation and workflow routing only.
**Complexity:** S — Extract the report lifecycle without changing fix requirements.
**Depends on:** None.

## 1. Context and problem
The fix rule owns both engineering verification and report creation/closure. Filing a report should be possible before the cause or fix is known, without implying a request to implement a fix.

## 2. Acceptance criteria
- [x] A dedicated report rule owns ID allocation, evidence, open reports and report/board closure.
- [x] The fix rule keeps diagnosis, mechanism repair, regression proof and eligible case studies, with a handoff to the report rule.
- [x] Navigation, templates and execution/review skills point to the appropriate authority.
- [x] Required documentation guards and reference checks pass.

## 3. Design
Create a path-scoped `create-bug-report-rule.md`; retain the always-loaded fix rule as the routing entry when fixing a defect. Preserve §6.5 for existing case-study references. Reporting alone does not require an established root cause, a passing test or implementation changes.

## 4. Changes, per file
The two bug rules, bug-report template, CLAUDE/ONBOARDING navigation, generated manifest, execution and review routing, and this task's board entry.

## 5. Testing
Run the reference checker, the five documentation guard modules required by ONBOARDING §7 and validators for the changed skills. Inspect reporting-only and fix-completion routing for contradictory requirements.

## Implementation notes

Created the dedicated report rule with evidence capture, unique IDs, honest unknowns, board visibility and closure after verified repair. The fix rule retains its engineering requirements and hands report lifecycle to the new authority. Existing case-study section references remain valid. Navigation, the template and execution/review routing now distinguish report-only work from repair.

Validation: both changed skill validators passed; the reference checker resolved 34 documents; all 119 documentation guard tests passed. The existing pytest environment warning for unrecognised `timeout` remains. Manual inspection confirmed that an Open report can be filed without a known cause or fix, and closing a report still requires the fix's verification. Existing unrelated working-tree changes were preserved. Delivery is local and uncommitted.
