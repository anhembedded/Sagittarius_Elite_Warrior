# EPIC-041K — A module's design cites code by path and symbol, a guard keeps every cited symbol real, and a point-in-time record names the commit its lines were read at

**Status:** ✅ Done (2026-10-16)
**Source:** The owner, 2026-10-16, relayed by the coordinator session: *"\"alerting/composition/channel_bindings.py:91-93\" với doc đâu cần link kiểu này nhỉ? link kiểu này code change thì update doc nhiều quá"* ("a doc does not need links like this, does it? With links like this, every code change means many doc updates"); then, on the proposed policy, *"ok chốt hết theo đề xuất"* ("ok, settle all of it as proposed")
**Risk:** 🟡 — a new guard in the commit tier over every design; rules every session loads change
**Complexity:** S — one guard with its probes, one rule clause, about 220 citations converted
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041J](EPIC-041J_module_folder_layout_and_design_in_step.md) (done)

---

## 1. Context and problem
- On `30a75f9` the designs under `Docs/MODULES/` held 220 line citations (163 in `alerting/`, 57 in `bots.md`); several had drifted again within two pull requests of `EPIC-041J` re-verifying them. The reasons and the owner's decision: [`DECISION_2026-10-16_cite_code_by_symbol.md`](../DECISION_2026-10-16_cite_code_by_symbol.md).

## 2. Acceptance criteria
- [x] A decision record supersedes the `file:line` parts of `DECISION_2026-10-16_module_docs_one_folder_arc42.md`, with its Constitution check; the old record marks them.
- [x] `commit-rule.md` §1 states the rule once ("Citing code"); "Design in step" no longer lists a `file:line` citation; the template, the decision, bug-report and task templates, the PR template, `fix-bug-rule.md`, `Docs/README.md`, rubric K10 and N8 and `EPIC-041E` follow it.
- [x] A guard fails on a line citation anywhere under `Docs/MODULES/`, and on a cited symbol its file does not define; probes plant each form.
- [x] Every citation in `Docs/MODULES/alerting/` and `Docs/MODULES/bots.md` is in the symbol form, each checked against the code.

## 3. Design
The citation form is `` `<path>.py` → `<symbol>` ``, the owner's own example. The guard is a pytest document guard under `tests/unit/architecture/`, beside `test_spec_index_is_consistent.py` and `test_case_study_index_is_consistent.py`, so it runs in the commit tier; it is stdlib only. A path resolves as a path suffix to exactly one file under `src/`, `scripts/` or `tests/`; each dotted part of the symbol must be a class, a function or an assigned name somewhere in that file's AST (the owner's "keep it simple").

## 3a. Reuse
- The document-guard shape and the scanned-roots registry (`tests/unit/architecture/scanned_roots_registry.py`).
- `None: no UI or application need` otherwise; no `src/` behaviour changes.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `DECISION_2026-10-16_cite_code_by_symbol.md`, `DECISION_2026-10-16_module_docs_one_folder_arc42.md` | New record; superseded parts marked |
| `tests/unit/architecture/test_module_docs_cite_code_by_symbol.py`, `scanned_roots_registry.py` | The guard and its probes; its registry row |
| `commit-rule.md`, `fix-bug-rule.md`, rubric, `.claude/templates/` (decision, bug report, task), `.github/PULL_REQUEST_TEMPLATE.md` | The clause and its citations |
| `Docs/MODULES/README.md`, `Docs/README.md`, `Docs/MODULES/alerting/`, `Docs/MODULES/bots.md` | The template line; the converted citations |
| `EPIC-041E`, the epic `README.md` and `TRACKING.md` | Citations by symbol; the new row |

## 5. Testing
Unit tier: `tests/unit/architecture/test_module_docs_cite_code_by_symbol.py` (red on `30a75f9`'s designs, 10 files; green after the conversion; a planted wrong symbol and a planted line citation on the real tree each turn it red), `test_scanned_roots_are_not_empty.py`, `test_guard_scans_its_registered_root.py`; the commit tier; `python3 scripts/check_skill_prompt_references.py`. Kind of pull request: code (a test, rules).

## 6. Docs touched
`Docs/MODULES/README.md` (citations), `Docs/MODULES/alerting/` and `Docs/MODULES/bots.md` (converted), `Docs/README.md` ("Writing a document").

## Implementation notes (written when done)
- Citations whose line had drifted on `30a75f9` and now name what the sentence meant: `alerting/module.py:83` → `AlertingModule.dependencies`; `:90-96`, `:98-109`, `:111-125`, `:111-133`, `:113-115` → `declare_cli`, `declare_operations`, `boot`, `shutdown`; `alerting_bindings.py:88, :91` → `LANE_POLL_SECONDS`, `HOUSEKEEPING_SECONDS`; `alerting_bindings.py:94-95` → `outbox_path`; `discord_webhook_channel.py:46` → `DiscordWebhookChannel`; `channel_bindings.py:91-93` → `CHANNEL_DESCRIPTORS`; `channel_bindings.py:58-62` → `ChannelSecrets`; `alerts_settings_presenter.py:93` → `AlertsSettingsPresenter`. In `bots.md`: `bot_run_state.py:54` → `BotRunState`, `grid_facts.py:136` → `GridFacts`, `grid_facts.py:190-232` → `GridFacts.on_fill`, `GridFacts._apply_fill`, `grid_facts.py:276` → `GridFacts.reconcile_recovering`, `i_bot_store.py:32` → `IBotStore`, `StoredBot`, `grid_runtime.py:130-194` → `GridRuntime`, `RuntimeLevel`, `LevelOrder`, `grid_stop_sequence.py:94` → `GridStopSequence`, the lifecycle matrix ranges → `BotLifecycleState`, `BotLifecycleEvent`, `BOT_LIFECYCLE_TRANSITIONS`, `shell/modules.py:43` → `MODULES`, `resume_recovering_for_host/handler.py:81` → `ResumeRecoveringForHostCommandHandler._open`.
- A cited docstring or whole file is cited by its path alone (`the docstring of sqlite_outbox.py`); a `deploy/` line is named by its content (`LoadCredential=alerting_discord_webhook`).
- One sentence of `bots.md` §1 was no longer true: it said `alerting` does not consume bot events; since `EPIC-036G` it reads them through `bots/contracts`. Reworded with a link to `alerting/03-context.md`.
- The guard resolves a path by its file name first; without that the suffix scan over three trees took 71 s, with it under a second.
- Verification evidence (commands and the CI run) is recorded on the pull request.
