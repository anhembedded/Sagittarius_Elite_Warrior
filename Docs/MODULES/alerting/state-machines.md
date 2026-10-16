Status: Current

# `alerting` — state machines

*Which states exist, which events move between them, and which moves are refused?*

## Built: a delivery

There is no `*_fsm_matrix.py` in the module yet; the one state that is stored is a delivery's,
`DeliveryState` (`alerting/domain/delivery_state.py:8-19`). Until the task that generates this table
(decision D4 of `EPIC-041`) adds a transition table beside the enum, this is the summary, with the
code that moves each edge:

| From | To | When | Where |
| :--- | :--- | :--- | :--- |
| (new) | `PENDING` | routed and admitted | `sqlite_outbox.py:161-178` |
| (new) | `DROPPED` | the channel's queue is full and nothing below this severity can be shed (never a CRITICAL) | `delivery_admission.py:38-45` |
| `PENDING`, `RETRYING` | `SENT` | the channel answered `ok` | `channel_delivery.py:101-107` |
| `PENDING`, `RETRYING` | `RETRYING` | the platform asked to wait (no attempt used), or a failure with attempts left | `channel_delivery.py:116-131` |
| `PENDING`, `RETRYING` | `FAILED` | a permanent refusal, or the last attempt failed; `CHANNEL_FAILING` is raised once | `channel_delivery.py:108-115`, `:121-134` |
| `PENDING`, `RETRYING` | `EXPIRED` | the alert is older than the expiry, at the start of every pass | `channel_delivery.py:77`, `sqlite_outbox.py:224-233` |
| `PENDING`, `RETRYING` | `DROPPED` | shed to make room for a more severe newcomer | `sqlite_outbox.py:253-270` |

`SENT`, `FAILED`, `EXPIRED` and `DROPPED` are final (`DeliveryState.is_open`, `delivery_state.py:16-19`).
A fail-over is not a transition: it adds a new `PENDING` delivery on another channel
(`alert_hub.py:176-201`).

## Built: the bots lifecycle, as the bot source reads it

`BotAlertSource` (`EPIC-036G`) keeps each bot's last seen state in memory and acts on the *entry*
into a state only (`bot_alert_source.py:122-138`), so a rewrite of a halted bot's file is not a
second alert. The lifecycle it reads is `bots`' own table
(`src/modules/bots/domain/bot_lifecycle_fsm_matrix.py:44-55`), never a copy: the states it names are
contract text, and `test_every_state_the_source_names_is_a_lifecycle_state` fails if one is renamed.
