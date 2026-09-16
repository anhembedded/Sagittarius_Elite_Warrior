# Case studies — why the gate was green while it was broken

A bug report answers *what broke and what fixed it*. A case study answers **why nothing caught
it**: the nets that were in place, and the reason each looked away.

| Document | Question |
| :--- | :--- |
| [`Tasks/bug_report/`](../../Tasks/bug_report/README.md) | what broke, root cause, fix |
| **`Docs/CASE_STUDIES/`** (this) | which check was silent, and what checks it now |
| [`.agents/ONBOARDING.md`](../../.agents/ONBOARDING.md) §8 | the one-line form, for skimming before you code |

## Write one only when all three hold

1. The defect reached the user through a **green gate**.
2. An existing net — type checker, test, guard, review row — covered the area and missed it.
3. The reason it missed **generalises**: the same blind spot is open elsewhere right now.

Point 3 is the filter. `BUG-122` needs no case study — nothing was watching that line and nothing
pretended to. `BUG-124` needs one: three nets each had a specific reason to be silent, and every
reason is still true elsewhere.

## Form

**A short list, not an analysis.** One table — net · why silent · still open? — then bullets, one
line each. Required sections: `## Why nothing caught it`, `## The fix`, `## Where else this is
still open`. The guard fails a file over **35 lines**. Explaining at length is what the
bug report is for.

The check the case study installs ships in the **same commit**. A "What checks it now" that says
"be careful" has not finished being written.

## Read it when

**Diagnosing a bug** — scan the index; if the symptom rhymes, start from that study's "still open"
column. **Writing a test double** — read `CS-001` first.

## Index

| Id | Title | Class | Check that exists now |
| :--- | :--- | :--- | :--- |
| [CS-001](CS-001_a_double_that_could_not_disagree.md) | A double that could not disagree | A double shaped like the union of two interfaces, over an `Any` | `tests/unit/architecture/test_engine_port_calls_are_real.py` + the annotation in `welcome_presenter.py` |
| [CS-002](CS-002_the_subscriber_nobody_built.md) | The subscriber nobody built | A class that subscribes at construction, that nothing constructs | `tests/unit/architecture/test_a_bus_subscriber_is_constructed.py` |
| [CS-003](CS-003_the_port_nobody_bound.md) | The port nobody bound | A port something resolves and nothing binds, behind an `except` that hides it | `tests/unit/architecture/test_every_resolved_type_is_bound.py` |
| [CS-004](CS-004_the_tests_the_gate_never_ran.md) | The tests the gate never ran | A suite under `src/`, cited as coverage, collected by nobody | `tests/unit/architecture/test_no_test_file_lives_under_src.py` |

Ids are sequential, never reused. `tests/unit/architecture/test_case_study_index_is_consistent.py`
fails on an unlisted file, a missing file, a duplicate id, a dead path citation, a missing section
or an over-long file.
