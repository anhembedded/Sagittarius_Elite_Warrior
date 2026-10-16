Status: Current

# `alerting` — 10. Quality: the timing that decides delivery

*Which constants decide when an alert is merged, retried, failed over, expired or purged, and what
are their values?* The scenarios the walking skeleton must hold, and the tests that prove them, are in
[`04-solution-strategy.md`](04-solution-strategy.md).

## Built

| What | Value | Where |
| :--- | :--- | :--- |
| A repeat is the same alert for: CRITICAL; WARNING and INFO | 1 min; 15 min | `alerting/domain/alert_policies.py` → `NoisePolicy.critical_dedup_window`, `NoisePolicy.other_dedup_window` |
| Same kind and venue are grouped within | 10 s | `alerting/domain/alert_policies.py` → `NoisePolicy.coalesce_window` |
| A venue-down alert stops hiding its bots' alerts after | 1 h | `alerting/domain/alert_policies.py` → `NoisePolicy.inhibition_ttl` |
| Attempts before a delivery fails; back-off from, doubling, capped at | 5; 5 s; 5 min | `alerting/domain/alert_policies.py` → `DeliveryPolicy.max_attempts`, `DeliveryPolicy.backoff_cap`, `DeliveryPolicy.backoff_after` |
| A CRITICAL fails over when the channel asks to wait longer than | 5 min | `alerting/domain/alert_policies.py` → `DeliveryPolicy.failover_after` |
| An alert older than this expires instead of being sent | 24 h | `alerting/domain/alert_policies.py` → `DeliveryPolicy.expiry` |
| Queue per channel (CRITICAL is admitted beyond it) | 200 | `alerting/domain/alert_policies.py` → `DeliveryPolicy.capacity` |
| Finished alerts are kept for; purged every | 30 days; 1 h | `alerting/domain/alert_policies.py` → `DeliveryPolicy.retention` · `alerting/application/alert_hub.py` → `PURGE_EVERY` |
| A lane looks at the outbox unprompted every; housekeeping runs every | 5 s; 1 s | `alerting/composition/alerting_bindings.py` → `LANE_POLL_SECONDS`, `HOUSEKEEPING_SECONDS` |
| One webhook POST counts as no answer after | 10 s | `alerting/adapters/urllib_webhook_transport.py` → `REQUEST_TIMEOUT_S` |
| A 429 that names no wait waits | 5 s | `alerting/adapters/discord_answer.py` → `DEFAULT_RETRY_AFTER` |
| `stop()` waits for a lane stuck inside a channel | 5 s | `alerting/adapters/threaded_delivery_host.py` → `JOIN_TIMEOUT_S` |
| The health section reports `degraded` when the oldest undelivered alert has waited | 15 min | `alerting/application/alerting_health_contributor.py` → `STUCK_AFTER` |
| A CRITICAL asks for this many channels when the owner has them (N8) | 2 | `alerting/application/alert_router.py` → `CRITICAL_CHANNELS` |
| Bots listed in a grouped alert, alerts listed in a summary, held alerts kept | 20; 20; 500 | `alert_coalescer.py` → `MAX_LISTED` · `quiet_hours_hold.py` → `MAX_LISTED`, `MAX_HELD` |
| Open conditions remembered; fail-overs remembered; criticals scanned behind a wait | 1000; 1000; 20 | `condition_book.py` → `MAX_OPEN` · `channel_delivery.py` → `MAX_REMEMBERED`, `WAITING_SCAN` |

## Planned

`EPIC-036C` adds the channel's own pacing under Discord's limit (research 036 §1: about 5 messages
per 2 s per webhook, to be measured). `EPIC-036E` adds the heartbeat (6 h, N4) and the dead man's
switch ping (5 min, N7). By decision D4 of `EPIC-041` this table becomes generated from the
constants, in the task that fills this view.
