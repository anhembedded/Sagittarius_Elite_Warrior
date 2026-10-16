# EPIC-041 — Every document answers a reader's question in one place, is linked to the rule that holds it, and the process is measured

- **Status:** 🔵 Planned. Scaffolded on 2026-10-14 at the owner's request: *"tạo EPIC-041 ngay"* ("create EPIC-041 now").
- **Repositories:** Elite
- **Origin:** The owner, 2026-10-14:
  - *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs; give me a doc philosophy, what to keep and what to drop"), on an arc42 / C4 / ADR / SBOM suggestion;
  - *"doc phải liên kết với rule"* ("docs must be linked to the rules");
  - *"phải có phần doc để thống kê data, dự đoán những data tương lai cần cho các phân tích kiểu system thinking, ví dụ như là layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data, and anticipate the data future system-thinking analyses need: which test layer found how many bugs, how many the user found, at which stage").
- **North star:** [`DECISION_2026-10-14_documentation_philosophy.md`](DECISION_2026-10-14_documentation_philosophy.md). The epic delivers it; the record holds the reasons.
- **Decisions:** `DECISION_2026-10-14_documentation_philosophy.md` (D1–D10); `DECISION_2026-10-16_module_docs_one_folder_arc42.md` (D1–D5, supersedes the first's D3 and D4 in part for module documents); `DECISION_2026-10-16_cite_code_by_symbol.md` (D1–D5, supersedes the second's `file:line` citations in designs).
- **Dependencies:** none blocking. `041E` turns the coordinator's bots explanatory page of 2026-10-14 into a repository document; `041F` feeds the `process-drift` audit.

---

## 1. Decisions already made
1. **Doc ↔ rule ↔ guard.** A doc says why and what shape; a rule says what must be done; a guard holds the rule. Each links the others, and the checker verifies both directions (D1, the owner's requirement).
2. **One fact, one place.** App docs summarise and link; module docs hold module detail; rules are cited, never restated (D2, D3).
3. **New homes:** `Docs/ARCHITECTURE`, `Docs/MODULES`, `Docs/DECISIONS` and `Docs/METRICS`, inside the existing `Docs/` tree (owner decision).
4. **PlantUML** for architecture diagrams (owner decision); mermaid stays for short diagrams in tasks.
5. **SBOM deferred** (owner decision). Vulnerability and licence checks take its place, in `041H`, which waits for the owner's approval because it changes the workflow.
6. **Process data** with a closed vocabulary on every new bug report, a backfill that never guesses, and a generated report (D9).

## 2. Goals — measurable
| Metric | Today (measured 2026-10-14 at `850aef4`) | When the epic is done |
| :--- | :-: | :-: |
| Rules that cite `Docs/HLD`, `Docs/SDD` or `Docs/ARCHITECTURE` | 0 | every architectural `[gate]`/`[guard]` clause has a checked `Why:` link |
| Doc→rule citations checked by a machine | 0 of the citations in 19 files | all |
| Places module contracts are defined | 2 (HLD 03, SDD 05) | 1 |
| Decisions with a central index | 0 of 24 + 9 + 5 | all, generated and guarded |
| Modules with a module doc | 0 of 7 | 1 (bots), with the pattern for the rest (2 on 2026-10-16: `alerting`, `bots`) |
| Bug reports with a structured "detected by" field | 0 of 213 | every new report; old ones backfilled or `Unknown` |
| `Docs/**/*.md` with a status line | few | all |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-041A](completed/EPIC-041A_docs_skeleton.md) | **First.** The skeleton: map, status lines, four homes with templates, the `bots` module-doc skeleton for EPIC-040 to fill, and the "Docs touched" rule | Elite | None | 🟢 | ✅ Done (2026-10-14) |
| [EPIC-041J](completed/EPIC-041J_module_folder_layout_and_design_in_step.md) | One arc42 folder per module ([decision of 2026-10-16](DECISION_2026-10-16_module_docs_one_folder_arc42.md)); `alerting` migrated as the pilot; every change to a documented module answers for its design, checked in CI | Elite | 041A | 🟡 | ✅ Done (2026-10-16) |
| [EPIC-041K](completed/EPIC-041K_cite_code_by_symbol.md) | A design cites code by path and symbol, never by line ([decision of 2026-10-16](DECISION_2026-10-16_cite_code_by_symbol.md)); a guard keeps every cited symbol real; a point-in-time record names its commit | Elite | 041J | 🟡 | ✅ Done (2026-10-16) |
| [EPIC-041C](incomplete/EPIC-041C_decisions_index.md) | `Docs/DECISIONS` index of every decision, generated and guarded | Elite | 041A | 🟢 | Planned |
| [EPIC-041B](incomplete/EPIC-041B_doc_rule_links_checked_both_ways.md) | Doc ↔ rule links checked in both directions by `rule_integrity` | Elite | 041A | 🟡 | Planned |
| [EPIC-041F](incomplete/EPIC-041F_quality_metrics_data.md) | Bug fields, backfill, quality report and data dictionary | Elite | 041C | 🟡 | Planned |
| [EPIC-041D](incomplete/EPIC-041D_app_context_and_module_map.md) | App context, container and module map in PlantUML; contracts written once | Elite | 041B | 🟡 | Planned |
| [EPIC-041E](completed/EPIC-041E_bots_module_doc.md) | `Docs/MODULES/bots/` in the folder layout of 041J, cited by symbol (041K); transition and timing tables generated, design diagrams by hand; a Planned hook for `EPIC-039L` | Elite | 041J, 041K (041D for the module-map link only) | 🟡 | ✅ Done (2026-10-16) |
| [EPIC-041G](incomplete/EPIC-041G_runtime_crosscutting_security_quality.md) | Runtime, crosscutting rule table, threat model, quality risks, deployment | Elite | 041D | 🟡 | Planned |
| [EPIC-041H](incomplete/EPIC-041H_dependency_register_audit_licences.md) | Generated dependency register, `pip-audit` and licence check in CI (waits for the owner) | Elite | 041A | 🟡 | Planned |
| [EPIC-041I](incomplete/EPIC-041I_retire_hld_sdd_and_guard_vocabulary.md) | HLD/SDD/Diagrams reduced to what is unique; vocabulary guarded | Elite | 041D, 041E, 041G | 🟢 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1. Map and links (041A–041C) | Every doc has a status; the map exists; the checker verifies doc↔rule links; decisions are indexed | Checker probes red on planted breaks, clean on the tree; index guard green. Not run |
| 2. Data (041F) | New bugs carry structured fields; the report answers "which layer catches what" | Guard probe; deterministic report; unknown counts recorded. Not run |
| 3. App and module docs (041D, 041E, 041G) | Context, container, module map, runtime, crosscutting, security, quality and the bots module doc exist and pass the checker | Checker green; FSM drift test green; contracts defined once. Not run |
| 4. Clean-up and supply chain (041H, 041I) | Old trees reduced; vocabulary guarded; dependencies audited in CI | Owner's approval for 041H recorded; CI shows the audit steps. Not run |

## 5. Out of scope
- An SBOM in SPDX or CycloneDX (owner decision; revisit if the app is ever distributed).
- Module docs for the other six modules. `041E` sets the pattern; each further module doc is its own task.
- Moving or renumbering existing `DECISION_*` files; they are indexed where they live.
- A documentation site generator.

## Notes (newest first)
- **2026-10-16** — `041E` done: `bots.md` became `Docs/MODULES/bots/` (nine documents, fourteen hand-drawn diagrams, none over seven boxes); the two transition tables and the timing table are generated by `scripts/render_bots_design_tables.py` and drift-tested; `06-runtime.md` and `state-machines.md` hold a Planned hook for `EPIC-039L`. Started before `041D` on the coordinator's request; the up-link goes to `Docs/ARCHITECTURE/README.md` until `041D` writes the module map.
- **2026-10-16** — `041K` done, on the owner's *"ok chốt hết theo đề xuất"*: designs cite code by path and symbol (`` `x.py` → `Symbol` ``), never by line; point-in-time records keep `file:line` at a named sha; `test_module_docs_cite_code_by_symbol.py` fails on a line citation or a symbol that no longer exists. All 220 design citations converted. `041E` follows it.
- **2026-10-16** — `041J` done, on the owner's answers (*"1. co / 2. dung / 3. ve tay theo high level"*, and the rules must make a code change or a bug fix consider the design): one arc42 folder per module, `alerting` migrated with its 11 wrong citations corrected, `scripts/check_design_in_step.py` in `commit-lint`, rubric K10. `041E` uses the folder layout.
- **2026-10-14** — `041A` done: `Docs/README.md`, a `Status:` line on all 51 documents under `Docs/`, the four home READMEs, the `bots` skeleton, and the "Docs touched" rule. The HLD/SDD files are `Historical` except HLD §11, which a rule cites.
- **2026-10-14** — `041A` widened into the skeleton, aimed at `EPIC-040`: the owner will do only it now and the rest when credit allows (*"epic đó vẫn để như vậy, sau này dư dã AI credit tui sẽ làm"*).
- **2026-10-14** — Epic scaffolded from the owner's requests; nine children written; philosophy recorded as a decision.
