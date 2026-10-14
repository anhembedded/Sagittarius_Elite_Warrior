Status: Current

# Metrics — what the process numbers say

**Reader:** the owner and the scheduled audits (`process-drift`) judging the process from data, not from
memory. **Question it answers:** *which test layer caught how many defects, how many reached the owner
or live trading, and at which stage?*

Nothing is collected here yet. `EPIC-041F` adds the closed vocabulary on bug reports (decision D9), the
backfill that writes `Unknown` where nothing can be derived and never guesses, the generated quality
report and the data dictionary.

## What belongs here, and what does not

| Belongs | Does not belong |
| :--- | :--- |
| Reports **generated** from the repository's own records, with the command that regenerates each | A hand-typed number: it drifts the day after |
| A data dictionary: every field, its allowed values, its source, who fills it | An interpretation of the numbers: that is a decision record |
| The list of data to collect next, with its source named before it is needed | Per-bug narrative: the bug report and, when the gate missed it, a case study |

## Layout and naming

`DICTIONARY.md` (the fields) and one generated report per question, e.g. `quality_report.md`. A
generated file says so in its first lines and names its generator; a guard compares it with the
generator's output, as for [`../OPERATIONS/exit_codes.md`](../OPERATIONS/exit_codes.md).

## Diagrams

Charts are generated with the report, not drawn by hand. Anything else follows decision D8.

## Linking a metric to its rule and its guard

A number that justifies a rule change cites the report and the rule clause it concerns; the rule clause
links back with a `Why:` (decision D1). The guard of a metric is the one that fails when the report no
longer matches its generator.

Worked example: the exit-code table. Its generator is `scripts/render_exit_codes.py`, its guard is
`tests/unit/support/cli_host/test_exit_code_table.py`, and the document states that it is generated.
Metrics reports follow the same three-way link.
