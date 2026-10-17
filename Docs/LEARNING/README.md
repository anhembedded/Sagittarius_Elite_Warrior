Status: Current

# Learning — one engineering idea per page, taught from this project

**Reader:** the owner, and anyone who wants to explain a design of this repository in an
interview. **Question:** what problem did a design decision solve here, what else could have
solved it, and how would I defend the choice?

A page teaches; it does not decide. The decision lives in its record and the rule in
`.claude/rules/`; a page links them and never restates them. The format and when a page is
written are `report-rule.md` §3 ("Teaching the Owner").

## Format of a page

Leave out a section that has nothing to say.

1. **The problem** — the real trigger (an incident, a log line, a request) and why it mattered.
2. **Constraints** — what any answer had to respect.
3. **Solutions considered** — one trade-off table.
4. **The choice and why.**
5. **How it is implemented** — a short sketch or diagram, citing code by path and symbol.
6. **Risks and failure modes.**
7. **Limits** — when this stops being enough.
8. **Names to know** — the standard patterns and terms.
9. **Interview questions** — three to five, each with the gist of an answer.
10. **Read more** — one or two sources.

## Pages

| # | Page | Topic | Decision it teaches |
| :-- | :--- | :--- | :--- |
| 001 | [Layered policy and a lifecycle state for halt recovery](001_layered_policy_and_lifecycle_state.md) | State machines, composition over inheritance, retry budgets | ADR 042 (`EPIC-042`), proposed in [PR #546](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/546) |
