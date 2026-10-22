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
| 002 | [Lazy composition: a command builds only what it needs](002_lazy_composition_a_command_builds_only_what_it_needs.md) | Import cost, lazy loading, dependency closure | [`PRO-014`](../../Tasks/proposal/PRO-014.md), task `BOT-188` |
| 003 | [Authorising a remote command](003_authorising_a_remote_command.md) | Authorisation, idempotency, least privilege, a gated door | [`DECISION_2026-10-21_remote_control_from_discord.md`](../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-21_remote_control_from_discord.md) (`EPIC-036F`) |
| 004 | [Waiting is a state: a bot that has started but may not trade yet](004_waiting_is_a_state_a_bot_that_starts_but_does_not_trade_yet.md) | State machines, state versus flag, level-triggered entry, restart safety | ADR 044 (`EPIC-044`), [`DECISION_2026-10-21_a_grid_waits_for_the_range.md`](../../Tasks/epics/EPIC-044_grid_waits_for_the_range/DECISION_2026-10-21_a_grid_waits_for_the_range.md) |
| 005 | [A trigger price is a limit order on the entry](005_a_trigger_price_is_a_limit_order_on_the_entry.md) | Guard conditions, a latch from the state machine, one rule for live and backtest | ADR 046 (`EPIC-046`), [`DECISION_2026-10-22_a_grid_trigger_price.md`](../../Tasks/epics/EPIC-046_grid_trigger_price/DECISION_2026-10-22_a_grid_trigger_price.md) |
