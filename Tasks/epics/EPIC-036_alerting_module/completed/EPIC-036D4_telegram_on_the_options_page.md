# EPIC-036D4 — The owner sets up, replaces and removes the Telegram bot on the Options page

**Status:** ✅ Done (2026-10-21)
**Source:** the coordinator, 2026-10-21: *"Take the rest of 036D first, in slices with frames: channels table (Telegram fields + Rotate) first"*; the decision of 2026-10-20 that the Options page's Telegram fields move into 036D (`EPIC-036C2` §3).
**Risk:** 🟡 — it writes a secret (a bot token) to the keyring; the token must never reach a screen, a log or an exception text
**Complexity:** M — one use case, one page group, a Send test that stops being Discord-only
**Epic:** [EPIC-036](../README.md); the third slice of [EPIC-036D](../incomplete/EPIC-036D_alerts_ui.md)
**SPEC:** [SPEC-017](../../../../Docs/SPEC/SPEC-017_set_up_an_alert_channel.md)
**Depends on:** [EPIC-036D1](EPIC-036D1_options_alerts_page_discord_webhook.md) (the page), [EPIC-036C1](EPIC-036C1_telegram_alert_channel_and_token_migration.md) (the channel and its secrets)

---

## 1. Context and problem
Telegram works once its two credentials are provisioned (the headless runbook) or migrated from the old config, but an owner at the desktop had no place to type them: the Options page knew only Discord's webhook.

## 2. Acceptance criteria
- [x] **A Telegram group** on the Alerts page: a masked bot-token field, a chat-id field, Save and Remove, a line saying whether the channel is on, and a line saying what is saved (the last four characters of the token and the chat id). (`test_alerts_page_telegram.py`)
- [x] **Save validates both against the shapes Telegram issues**, writes both, reads both back, and says what happened: saved, a missing or wrong value (named), no usable store, or another store answering first. Nothing is stored on a refusal and an earlier pair is kept. (`test_telegram_credentials_setup.py`, `test_an_invalid_value_is_not_saved_and_the_page_says_why`)
- [x] **Saving over a stored pair is the rotation**: the new pair replaces the old one, the page shows only the new four characters, and nothing else changes. (`test_saving_again_over_a_saved_pair_replaces_it`)
- [x] **Remove asks first, with its own verbs, keeping is the default**, and says when the channel stops. (`test_remove_asks_with_its_own_verbs_and_keeping_is_the_default`, `test_confirmed_remove_forgets_the_pair_and_says_when_it_stops`)
- [x] **One Send test for every channel set up**: it works with only Telegram saved, names the channels it reached, and a refused Telegram test says what to check; it is off when neither channel is saved. (`test_send_test_works_with_only_telegram_saved_and_posts_to_it`, `test_a_refused_telegram_test_tells_what_to_check_not_the_token`, `test_send_test_is_off_when_neither_channel_is_saved`)
- [x] **The token is nowhere**: no log record, notice or label holds it after a save, a test and a removal. (`test_no_log_record_notice_or_label_holds_the_token`, `test_no_outcome_state_or_log_line_holds_the_token`)
- [x] **Frames**: the page with a Discord webhook saved and a Telegram bot saved, light and dark at three sizes (`test_alerts_options_page_frames.py`; the CI artifact `ui-screenshots`, `alerts_options@WxH.png`).
- [ ] **A real Telegram message from the page**: not run.

## 3. Design
- **The pattern of `DiscordWebhookSetup`, for two values.** One use case owns the write path: validate, write, read back, return an enum and a state that carries no secret. A shared base would have made two channels with different arity and different words look alike; the two classes are siblings and a third channel is a third sibling (`architecture-rule.md` §7.2.1).
- **A group and a view model of its own**, so the page's view and view model do not grow with every channel; the presenter's answer carries both channels' state (`ChannelStates`) read together on the pool.
- **The *channels table* the 036D plan named is not built.** Two channels fit two groups with a state line each; a table would add a second place to say the same thing. When a third channel exists, the table is one view over `ChannelStates`.
- **Send test is not per channel.** It already tests every channel in the catalog, so it moved out of Discord's group and says so; a per-channel test would need the catalog to be built for one channel only.
- **A pair, not two writes the owner could half do.** Both values are required to save; a half-stored pair (only possible by hand) is reported as "stored, not a complete bot".

## 3a. Reuse
`used DiscordWebhookSetup`'s pattern, `ActionOwnershipTracker`, `UiThreadRelay` (through `AlertsActionRelay`), `ask_with_verbs` / `VerbQuestion`, `plain_label`, `is_bot_token` / `is_chat_id` of the Telegram adapter (injected). `not used`: `StatusMessageViewModel` beyond the page's own (the Telegram view model has no status of its own; the page's one status line answers).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `alerting/application/telegram_credentials_setup.py` | the use case, its spec, outcomes and state |
| `alerting/composition/alerting_bindings.py` | binds it over the channels' secret stores |
| `alerting/ui/options/telegram_settings_group.py`, `telegram_settings_view_model.py`, `channel_states.py` | the group, its view model, the pooled state |
| `alerting/ui/options/alerts_settings_view.py`, `…_view_model.py`, `…_presenter.py`, `alerts_words.py` | the group on the page, two more actions, words (the Send test's sentences name the channel) |
| `Docs/…` | SPEC-017, the module design |

## 5. Testing
Unit: `test_telegram_credentials_setup.py`, `test_alerts_page_telegram.py`, the existing Options page tests (updated for the Send test's new sentences); integration: `test_alerts_options_page_frames.py`. Mutations: `can_test` ignoring Telegram and the fields not being cleared after a save each turn a test red. Not run: a real Telegram bot and the keyring of the owner's desktop.

## 6. Docs touched
`Docs/MODULES/alerting/` README, 05, 06; `Docs/SPEC/SPEC-017` and the SPEC index.

## Implementation notes (written when done)
The presenter was at 398 lines (the ceiling is 400): the failure phrases moved into `alerts_words.DOING_WORDS`, the pooled state into `channel_states.py`, and the answer dispatch became one function per kind (complexity under the ratchet). Two outcome names tripped S105 ("token" in an enum member's name) and carry a reasoned `noqa`.
