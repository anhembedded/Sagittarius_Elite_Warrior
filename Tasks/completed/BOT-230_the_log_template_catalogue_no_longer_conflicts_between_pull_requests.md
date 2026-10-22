# BOT-230 — The log template catalogue no longer conflicts between pull requests

**Status:** ✅ Done (2026-10-21)
**Board:** The generated `template_catalogue.json` carried the template count and two statistics in its header line, so every pull request that added a log call changed that line and any two conflicted on it; the header now holds the schema only, and the statistics are checked from the source (decision: keep the file committed, remove the line that changes with every pull request, 2026-10-21).
**Source:** Coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-21, after the catalogue conflicted on nearly every parallel pull request that day, each conflict costing a gate cycle.
**Risk:** 🟢 — a generated file's header; the viewer reads the template rows only.
**Complexity:** S.
**Depends on:** None.

---

## 1. Context and problem
`src/support/log_view/template_catalogue.json` is generated from the source's log calls (`scripts/render_log_templates.py --write`) and read by the `logs` viewer at runtime. Its second line held `"templates": N, "variable_template_calls": M, "too_generic_templates": K`. Any pull request that adds or removes a log call changes N, so two such pull requests always conflict there, and GitHub then runs no gate on the conflicting one. Authors had to remember to merge master, regenerate and push, on every round.

## 2. Acceptance criteria
- [x] Two pull requests that each add a log call merge without a conflict in the catalogue unless their new templates sort into the same gap of the file or both sort last (measured by the reviewer: see section 3).
- [x] The viewer loads the same templates; a file written before this change still parses.
- [x] The gate still fails when the committed file differs from what the source generates.
- [x] The two statistics keep their ratchets, computed from the source: the variable-call count (`test_log_calls_with_a_variable_message_only_fall`) and, added here, the too-generic count (`test_templates_left_out_as_too_generic_only_fall`; it had none, its change was only visible in the file's header).

## 3. Design
Options considered:

| Option | Verdict |
| :--- | :--- |
| (a) Stop committing the file; generate at build, gate and app start | Rejected: the viewer needs it at runtime and generating it means a full scan of `src/` at every `logs` start (about 1.8 s measured by the reviewer, a real cost for `journalctl -f` piped into the viewer); the committed file plus the stale test is what keeps it honest. (The hosts do have the source tree: they are installed by cloning the repository, so "no source to scan" was not the reason.) |
| (b) Keep it committed, add a `.gitattributes` merge driver that regenerates on conflict | Rejected: a merge driver is local git configuration; GitHub's mergeability check and the web merge ignore it, so the pull request still shows as conflicting and runs no gate |
| (c) Keep it committed; remove what changes with every pull request from it | Chosen: the only line that conflicted every time was the header's counts |

The statistics were never read back from the file: `test_log_calls_with_a_variable_message_only_fall` and the ambiguous-template ceiling compute them with `extract_catalogue(source)`, so nothing is lost. Rows are sorted globally by their text (`extract_catalogue`), not by source file, so a row's place depends on its text. Measured by the reviewer on two branches each adding one log call: calls whose templates sort far apart merge clean, wherever their code lives (two adjacent calls in one file conflict only in the `.py` file); two new templates that sort into the same gap conflict; and any two that both sort after the last row conflict, because the last row has no trailing comma and each side rewrites it. A conflict is now the exception, and the stale test covers what is left (regenerate and push). On the old format the same pair also merged cleanly in git but left a stale header count; that quiet failure is gone as well.

## 3a. Reuse
`catalogue_text`, `parse_catalogue_text`, `extract_catalogue`: used; no new mechanism.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/log_view/template_catalogue_file.py` | the header is the schema only; the parser does not read the statistics |
| `src/support/log_view/template_catalogue.json` | regenerated |
| `tests/unit/support/log_view/test_the_log_template_catalogue_is_current.py` | the round trip compares templates; a test pins the constant header |

## 5. Testing
`tests/unit/support/log_view` (82 passed): the committed file equals the generated text, the header is constant, the file round-trips, the matcher finds every template's params.

## 6. Docs touched
none, because the format note is the module docstring of `template_catalogue_file.py`.

## 7. Implementation notes (2026-10-21)
- One-time cost: every open pull request that touched the catalogue conflicts once more on the header line after this lands; regenerate with `scripts/render_log_templates.py --write` as before. From then on that line cannot conflict.
- Not done: the generated `.claude/rules/capabilities.md` table is a similar merge hazard and was not part of this request.
