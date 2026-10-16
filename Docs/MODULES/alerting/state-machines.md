Status: Current

# `alerting` — state machines

*Which states exist, which events move between them, and which moves are refused?*

## Built: a delivery

There is no `*_fsm_matrix.py` in the module yet; the one state that is stored is a delivery's,
`DeliveryState` (`alerting/domain/delivery_state.py` → `DeliveryState`). Until the task that
generates this table (decision D4 of `EPIC-041`) adds a transition table beside the enum, this is
the summary, with the code that moves each edge:

| From | To | When | Where |
| :--- | :--- | :--- | :--- |
| (new) | `PENDING` | routed and admitted | `sqlite_outbox.py` → `SqliteOutbox._insert_delivery` |
| (new) | `DROPPED` | the channel's queue is full and nothing below this severity can be shed (never a CRITICAL) | `delivery_admission.py` → `DeliveryAdmission._admit_one` |
| `PENDING`, `RETRYING` | `SENT` | the channel answered `ok` | `channel_delivery.py` → `ChannelDelivery._attempt` |
| `PENDING`, `RETRYING` | `RETRYING` | the platform asked to wait (no attempt used), or a failure with attempts left | `channel_delivery.py` → `ChannelDelivery._attempt` |
| `PENDING`, `RETRYING` | `FAILED` | a permanent refusal, or the last attempt failed; `CHANNEL_FAILING` is raised once | `channel_delivery.py` → `ChannelDelivery._attempt` |
| `PENDING`, `RETRYING` | `EXPIRED` | the alert is older than the expiry, at the start of every pass | `channel_delivery.py` → `ChannelDelivery.run_due`; `sqlite_outbox.py` → `SqliteOutbox.expire_before` |
| `PENDING`, `RETRYING` | `DROPPED` | shed to make room for a more severe newcomer | `sqlite_outbox.py` → `SqliteOutbox.shed_lowest` |

`SENT`, `FAILED`, `EXPIRED` and `DROPPED` are final (`delivery_state.py` → `DeliveryState.is_open`).
A fail-over is not a transition: it adds a new `PENDING` delivery on another channel
(`alert_hub.py` → `AlertHub.fail_over`).

## Built: the bots lifecycle, as the bot source reads it

`BotAlertSource` (`EPIC-036G`) keeps each bot's last seen state in memory and acts on the *entry*
into a state only (`bot_alert_source.py` → `BotAlertSource.on_bot_changed`), so a rewrite of a
halted bot's file is not a second alert. The lifecycle it reads is `bots`' own table
(`src/modules/bots/domain/bot_lifecycle_fsm_matrix.py` → `BotLifecycleState`), never a copy: the
states it names are contract text, and `test_every_state_the_source_names_is_a_lifecycle_state`
fails if one is renamed.
