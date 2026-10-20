# BOT-198 — At a terminal every report prints through `rich`: a wide report wraps its long cells and never falls back to plain text

**Status:** 🟡 In progress
**Priority:** P2
**Board:** At an interactive terminal the report always prints through `rich` (a long Ladder or Recovery cell wraps instead of the whole report falling back to plain text); a missing `rich` at a terminal says so on stderr; a failed command's sentence is red there; every non-terminal byte is unchanged ([BOT-195](completed/BOT-195_rich_tables_and_colour_for_the_human_bot_report.md), [PRO-017](proposal/PRO-017.md)).
**Source:** The owner, 2026-10-20, on the VPS over SSH: *"Tui ki vao la tat ca cac output len cua VPS phai duoc output rich chu"* ("every output of the VPS must come out as rich"). They ran `$M bot show uie03d` at an interactive terminal and got plain text, no colour and no table, although `BOT-195` is meant to render it.
**Risk:** 🟢 — presentation only, at a terminal only; the plain bytes are pinned by the existing golden tests, unchanged.
**Complexity:** S — one renderer rewrite of two column options, one chooser branch, one 20-line error styler, tests and docs.
**Depends on:** [BOT-195](completed/BOT-195_rich_tables_and_colour_for_the_human_bot_report.md) merged (58eca01).

---

## 1. Context and problem
`TerminalAwareTextRenderer.render` (`src/shell/terminal_report_text.py`, at 5477ce6b) fell back to the plain `TextReportRenderer` whenever `RichTextReportRenderer.render` raised `ReportTooWideError`, which it did when the report's natural width exceeded the terminal's columns (`no_wrap=True` cells, nothing shortened). `bot show` has a `Ladder` row of about 200 characters (`bot_status_reports.py::_ladder_rows`, `summary_line`) and `Recovery` rows of about 110, so on a 120 to 160 column terminal it always fell back; the fallback was logged at INFO only, so the owner could not tell why. The owner's other possible causes (rich missing in the VPS venv, `NO_COLOR`, `TERM=dumb`) fall back too, the first silently.

## 2. Acceptance criteria
- [x] On a terminal that wants colour (stdout a tty, `TERM` not `dumb`, `NO_COLOR` unset, `rich` importable) a report always prints through `rich`, at any width: a long cell wraps onto further lines; an id, a state word and a number are never cut, split or elided.
- [x] `ReportTooWideError` is gone as a fallback trigger and removed.
- [x] A pipe, a file, the journal, `ssh host cmd` without a tty, `NO_COLOR`, `TERM=dumb`, `--json` and a venv without `rich` keep today's exact plain bytes (existing golden tests unchanged and green).
- [x] When stdout is a tty and the plain renderer is used because `rich` is not installed, one line goes to stderr (once per run); stdout bytes are untouched. `NO_COLOR`, `TERM=dumb` and a non-terminal stay silent.
- [x] The survey of the outputs that do not go through a renderer is in section 3, and the small ones are built or recommended.
- [x] The one meaning table also colours a side (`BUY`/`LONG` green, `SELL`/`SHORT` red, by the `SIDE`, `POSITION SIDE`, `POSITION` or `DIRECTION` column head or label) and an order or level state (`FILLED` green; `CANCELLED`, `EXPIRED` yellow; `REJECTED` red; `RESTING` and the rest plain), the word always printed (owner, 2026-10-20: *"cac lenh phai co mau chua, it nhat buy sell, long, short"*).
- [x] Runbook §6 and PRO-017's follow-up line say it.

## 3. Design
No design change: `src/shell` and the CLI host have no `Docs/MODULES/` folder; the seam (`IReportRenderer`, `TerminalAwareTextRenderer` over `RichTextReportRenderer`) is the one `BOT-195` made.

**Wrap, not fall back.** A table keeps each column's longest word whole: `_share_of` gives every column its longest word and hands the slack, a column at a time, to the one furthest from its unwrapped width, then fixes those widths (`rich` shrinks columns past any `min_width` and crops them, so `min_width` alone does not hold; found in review). A long free-text cell (Ladder, Recovery, reason) wraps at spaces. When even the longest words do not fit (a 10-column `bot list` at 80 columns), the table is printed as one label/value block per row, so no column is dropped and no word is cut; a table with no header folds. The label column of a block folds too. Measuring (`_natural_width`) and `ReportTooWideError` are deleted.

**The one remaining fallback at a terminal is a missing `rich`**, which is not the operator's choice, so it says so once on stderr (`RICH_MISSING_NOTE`). `NO_COLOR` and `TERM=dumb` are the operator's choice and stay silent.

**Survey: what does not go through a `Report` renderer** (read at 5477ce6b; every `bot` verb, `status`, `preflight`, `alert`, `exchange-status` and `order-preview` already end in `print_report`, so they are rich now, including the one-line answers of `bot start/stop/pause/resume/edit`, which are one-row reports):

| Output | Where | Today | Can be coloured with the same meaning table? | Done here |
| :--- | :--- | :--- | :--- | :--- |
| A failed command's sentence (`CliOutcome.message`: usage, no such bot, refused, preflight failed, host unreachable) | stderr, `src/support/cli_host/exit_status.py::run_command` | plain | Yes: `ERROR` = bold red; only when stderr is a tty, `TERM` not `dumb`, `NO_COLOR` unset; bytes unchanged otherwise | **Built** (`error_message_style.py`, stdlib SGR because the host is stdlib-only; its `wants_colour` is the one colour policy, shared with `TerminalState`) |
| `rich` missing at a terminal | stderr | silent (INFO log) | n/a: a note | **Built** (criterion 4) |
| Tracebacks of an unexpected failure | stderr, same function | plain | No: a traceback is read by a person and grepped by a supervisor | Left plain |
| The application log (the `run` host, `bot` boot lines, journal) | stdout/stderr and the journal | plain | **No**: PRO-017 says `rich` is not used in logging; the journal and log files stay plain | Never |
| The launcher banner (`main.py`) | stdout | plain text | Possible (bold), no meaning attached | Recommend: leave plain |
| `sync`, `stream` handlers (`✅`/`❌` lines) | `src/modules/market_data/cli/*` | free text with emoji | Possible (✅ green, ❌ red) but they are free-text prints in module handlers; each would become a report | Recommend: a separate task converting them to `Report` (then they colour for free) |
| `trade-once`, `order-dry-run` formatters | `src/modules/strategy/cli`, `src/presentation/cli` | free text | Possible | Out of scope: trading / order sending; recommend only |
| Interactive shell help and `Goodbye!` | `interactive_shell.py` | free text | Cosmetic | Recommend: leave |
| `--json`, `--format <name>` | stdout | machine formats | **No** | Never |

**Recommendation to the owner:** the command answers are covered now. The remaining free-text prints are older handlers (`sync`, `stream`, `trade-once`, `order-dry-run`); the right move is one task per module converting each to a `Report`, which gives them `--json` and rich together, not a second colouring path.

**Why `bot show` stayed plain at `COLUMNS=250`:** `bot show` is all two-cell rows, so `_section` draws it as one label/value block (the same path as every other report); it was not falling to `_lines`. `COLUMNS` does not survive `sudo -u sew env ...` (sudo resets the environment and `env` adds only what is named), so `shutil.get_terminal_size` read the real terminal width, and the ~200-character Ladder row exceeded it: the width fallback. `bot order` fits, so it was already rich. `sys.stdout` is replaced only for machine formats (`console_log_stream.py`), so `isatty()` is asked of the real stream. Other causes (rich missing in `/opt/sew/venv`, a checkout older than 58eca01) cannot be told from code: the stderr note covers the first.

## 3a. Reuse
`TerminalAwareTextRenderer`, `RichTextReportRenderer` and the `_STATE_STYLES` meaning table are used as they are. No UI catalogue row applies (`None: no Qt UI need`).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/rich_text_report_renderer.py` | columns wrap (`min_width` of the longest word, `overflow="fold"`); `ReportTooWideError` and the measuring pass removed |
| `src/shell/terminal_report_text.py` | no width fallback; one stderr note when `rich` is missing at a terminal |
| `src/support/cli_host/error_message_style.py`, `exit_status.py` | a failed command's sentence in bold red at a terminal |
| `.claude/rules/capabilities.md` | regenerated capability row |
| `src/shell/rich_text_report_renderer.py` (also) | `_SIDE_STYLES`, the side column heads and labels, order states in `_STATE_STYLES` |
| `tests/unit/shell/test_terminal_report_text.py`, `test_wide_report_on_a_terminal.py`, `tests/unit/support/cli_host/test_error_message_style.py` | section 5 |
| `Docs/OPERATIONS/headless_runbook.md` §6, `Tasks/proposal/PRO-017.md` §6 | the new behaviour |

## 5. Testing
Unit tier. A `bot show` layout like the real one (a 200+ character Ladder, two Recovery rows) at 160, 100, 60 and 40 columns: ANSI present, differs from plain, every word present exactly once (no loss, no duplicate), no line wider than the terminal, no `…`; at 100 and 160 the id, state word and figures are whole and `RECOVERING` yellow, `-4.00` red. A wide table wraps its last column and keeps `a00001 HALTED` whole. Non-terminal cases equal the plain renderer at every width; the golden tests are untouched. The stderr note appears once for a tty with `rich` missing and never for a pipe, `NO_COLOR`, `TERM=dumb` or a working `rich`; stdout stays empty of it. The error sentence is red only at a tty with colour wanted. By hand: `script -qec` (pseudo-terminal) with `COLUMNS=100` shows the wrapped coloured block; `NO_COLOR=1` and a pipe show the plain bytes.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §6; `Tasks/proposal/PRO-017.md` §6. `Docs/MODULES/`: none, because `shell` and the CLI host have no module folder.

## Resume
Pushed for review; waiting for the reviewer comment and a green `ci-local.ps1 -Full` on the head.
