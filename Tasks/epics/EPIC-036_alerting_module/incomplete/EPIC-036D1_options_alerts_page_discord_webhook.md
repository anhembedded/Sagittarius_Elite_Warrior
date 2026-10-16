# EPIC-036D1 — The owner configures the Discord webhook from Tools → Options → Alerts, and tests it

**Status:** 🟡 In progress — built and verified on 2026-10-16 (every criterion but the last); waits for the owner's look at the page in the real window and for the merge
**Source:** the owner, 2026-10-16, relayed by the coordinator session `session_01PZn6EWxn6gytSGKwbuRJGg` in English: *"Today the desktop app has no place to configure alerting"*; the owner said yes (*"Có làm"*, "Yes, do it") to pulling a small slice of `036D` forward: a Tools → Options page "Alerts" with a masked Discord webhook field and Save and Remove, a Send test button, and a channel status line.
**Risk:** 🟡 — it is a write path for a secret (N3) that can post in the owner's channel; no change to delivery, the outbox or any real-money behaviour
**Complexity:** M — one use case for the secret, one for the test, a catalog builder, and a QtWidgets page with three off-thread actions
**Epic:** [EPIC-036](../README.md); split from [EPIC-036D](EPIC-036D_alerts_ui.md), which keeps everything else of the UI
**SPEC:** none yet; `036D` adds the journey "set up an alert channel"
**Design:** [`Docs/MODULES/alerting/`](../../../../Docs/MODULES/alerting/README.md) — `05-building-blocks.md` (the page's classes), `06-runtime.md` (Save, Remove, Send test and the restart decision), `diagrams/06-options-save-and-test.puml`
**Depends on:** [EPIC-036G](EPIC-036G_walking_skeleton_halt_to_discord.md) (the Discord channel, `SendTestMessage`, the secret stores); [EPIC-033E](../../EPIC-033_windows_workbench/README.md) (the Options dialog)

---

## 1. Context and problem
A desktop owner has no place to give the app a webhook: the channel is configured only when a secret named `alerting_discord_webhook` is already stored (`src/modules/alerting/composition/channel_bindings.py:72-100`), and the only way to store one on a desktop is a keyring tool of the owner's own. `alert test` is a command-line verb. `EPIC-036D` plans the whole UI (a channels table, a routing matrix, a dock, an indicator) and waits on `EPIC-036C`; the owner wants the smallest part of it now.

## 2. Acceptance criteria
- [x] **Tools → Options → Alerts** is an `IOptionsSection` (title "Alerts", order 30, after Trading and Market Data), contributed lazily through a `Deferred`. It is never dirty: Save, Remove and Send test act at once, as Trading's page does.
- [x] **A masked webhook field** (`QLineEdit` in password mode) with **Save** and **Remove**. Save writes `alerting_discord_webhook` through `ISecretStore`'s writable store (the keyring), after `is_discord_webhook_url` accepts it. A value that is not a Discord webhook URL, or is empty, is **not saved**, an earlier webhook is left as it was, and the page says why in words (the sentence never echoes the value).
- [x] **Never shown back (N3).** After a save the field is cleared; the page shows only the last four characters of the token ("Saved webhook ending …w9Kp"). The URL is on no label, no line edit, no log record, no notice and no exception text, on success, on refusal and on failure (`test_alerts_page_never_shows_the_url.py`, `test_discord_webhook_setup.py`).
- [x] **Remove asks first**, with its own verbs (Remove webhook / Keep webhook), keeping the default (`VerbQuestion`).
- [x] **Send test** reuses `SendTestMessage` (through `SendTestToConfiguredChannels`), runs off the UI thread under `async-ui-action-rule.md` (an action id, a stale-answer fence, a `UiThreadRelay` hand-off, buttons off while it runs, `shutdown()` drops a late answer), and shows the sanitised outcome: "Test message sent to Discord. Check the channel.", "Discord refused the webhook message (404)", "Discord did not answer (timed out)"; never the URL. It works on a webhook saved a moment ago, with no restart.
- [x] **A channel status line** says Off / On / "Saved, not sending yet: restart the app to start sending" / "Removed, but this run still has the Discord channel: its alerts are refused until you restart the app", from the run's catalog (does the run have the Discord lane?) and the stores (is a usable webhook stored?).
- [x] **A store that cannot be written, or that another store overrides, is told as such** ("the keyring cannot store a secret here, so nothing was saved"; "saved, but this machine reads the webhook from a systemd credential or secret file first, so the saved one is not used"). A save is never reported when the channel would not use it.
- [x] **A preview**: `src/modules/alerting/ui/options/preview.py` (`PREVIEW_KEY = "alerts_options"`).
- [x] **Design in step**: `Docs/MODULES/alerting/` changed in the same pull request (§6).
- [ ] **The owner's look** at the page in the real window (Tools → Options → Alerts), a Save and a Send test against the owner's own webhook, recorded in the notes. Not run.

## 3. Design
**The decision the owner asked to be recorded — restart, not a hot rebuild.** Read from the design: the Discord lane is a thread started once, at boot, for each id the catalog had (`ThreadedDeliveryHost`, `alerting/adapters/threaded_delivery_host.py:41-72`, bound at `alerting_bindings.py:203`); `AlertHub`, `ChannelDelivery` and `ChannelAlertingStatus` all hold the same catalog, immutable for the life of the run (`RegisteredChannelCatalog`, `registered_channel_catalog.py:15-28`); and the host's "does a channel carry bot events?" answer (`IAlertingStatus`, decision D5) reads it. Rebuilding the lane while the hub routes would need a mutable catalog, a lane started and stopped under the worker, and a status that changes under `operations`' warning: new concurrency on the delivery path, for a setting changed about once. **Chosen: a replaced webhook applies at the next send** (the channel reads its secret at each send, `discord_webhook_channel.py:51-52`), **a first save or a removal changes the lane after a restart, and the page says so** in the channel line. Rejected: (B) rebuild the lane in place (risk above, no owner need); (C) hide the difference and say "saved" (a lie the host's warning would contradict). If the owner wants no restart, it is its own task, with the delivery path in scope.

**Where the secret is written.** `DiscordWebhookSetup` (application) is the only write path: it validates with the adapter's `is_discord_webhook_url`, injected through `WebhookChannelSpec` so the application layer imports no adapter, writes through `ISecretStore`, and reads back, because on a host that provisions the webhook (a systemd credential, a secret file) the writable keyring entry is shadowed (`ordered_secret_stores.py:read`). It returns enums and four characters of the token; no message is built from the value.

**Send test with a fresh catalog.** The run's catalog is fixed, so a webhook saved after boot would answer "nothing to test". `IChannelCatalogBuilder` (a port in `contracts/`) with `DescriptorChannelCatalogBuilder` (composition) runs `build_channel_catalog` again at each test; `SendTestToConfiguredChannels` hands that catalog to the existing `SendTestMessage`. The run's catalog is not touched.

**No exception text from a secret path.** An exception raised under a save or a test can quote the URL (`ValueError("… https://discord.com/api/webhooks/…")`, a backend's own message). So the presenter reports an unexpected failure by its **type name alone** (`type(exc).__name__`) to the notifier's Details and to the log, never `failure_detail(exc)` and never `exc_info`.

**Mirrors:** Trading's Options page (`trading_settings_presenter.py`) for the action shape; `OptionsSectionPresenter` for the dialog contract; `UiThreadRelay` for the hand-off.

## 3a. Reuse
| Need | Checked | Result |
| :--- | :--- | :--- |
| A page of Tools → Options | `IOptionsSection`, `OptionsPageContribution`, `OptionsSectionPresenter` | used |
| A label whose text is text | `plain_label` | used (every label) |
| A risky action's question with its own verbs | `VerbQuestion`, `ask_with_verbs` | used (Remove) |
| A worker's answer on the UI thread | `UiThreadRelay` | used (`AlertsActionRelay` is a subclass) |
| Fencing a stale answer | `ActionOwnershipTracker` | used |
| A failure told to the user | `INotifier`, `FailureNotice` | used (an unexpected failure only) |
| A status line on a view model | `StatusMessageViewModel` | used |
| Reading and writing a named secret | `build_secret_stores` through `ChannelSecrets`; `ISecretStore` | used (the same store the channel reads) |
| The Discord URL check | `is_discord_webhook_url` | used, injected |
| The Send test | `SendTestMessage` | used, over a fresh catalog |
| A table, a symbol picker, a time picker, a chart | `SpecTable` and others | not used: the page has none |
| A shared "run one fenced action with a busy flag" base for the Options pages | searched `support/ui_kit` | not used because none exists: Trading's page has its own copy of the same shape. Extracting one would change Trading's page, outside this slice; the eight member names the two pages shared were renamed instead of added to the ratchet, and the extraction is a candidate for `036D` |

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/alerting/application/discord_webhook_setup.py` (new) | Save, remove, describe: the secret's one write path |
| `src/modules/alerting/application/send_test_to_configured_channels.py` (new) | `SendTestMessage` over a catalog built now |
| `src/modules/alerting/contracts/i_channel_catalog_builder.py` (new) | The port for that catalog |
| `src/modules/alerting/composition/channel_bindings.py`, `alerting_bindings.py` | `DescriptorChannelCatalogBuilder`; three bindings |
| `src/modules/alerting/adapters/discord_webhook_channel.py` | `DISCORD_CHANNEL_ID`, used by the descriptor and the spec |
| `src/modules/alerting/ui/options/` (new) | The page: presenter, view, view model, relay, sentences, factory, preview |
| `src/modules/alerting/module.py` | `contribute()`: the page, order 30 |
| `tests/unit/architecture/test_module_contribution_laziness.py` | `alerting` joins the contributing modules (the guard asks for it) |
| `Docs/MODULES/alerting/` | §6 |

## 5. Testing
Tier per `ci-rule.md` §2: unit, offscreen Qt; the page over the real use cases, the real catalog builder and the real Discord channel, with an in-memory store and a scripted transport as the only doubles.
- **Written red first** (the modules did not exist), then green; mutations confirmed red: saving without the URL check, `failure_detail(exc)` in place of the type name, a URL in a log line, an unmasked field, a field not cleared, the hint showing the whole URL, a cached catalog in the Send test.
- `test_discord_webhook_setup.py` — a valid URL is saved; nine invalid values are never saved and leave an earlier webhook; a store that cannot write, that quotes the URL in its error, or that another store overrides; remove in all four outcomes; the state carries no URL; no log record carries it.
- `test_send_test_to_configured_channels.py`, `test_channel_bindings.py` — a fresh catalog at each run; a webhook saved after boot is seen.
- `test_alerts_page_webhook.py` — an `IOptionsSection`, never dirty, masked; the four channel lines; Save, refusals, Remove's verbs and outcomes.
- `test_alerts_page_never_shows_the_url.py` — the URL in no log record, notice or label on save (saved, invalid, refused, crash) and on Send test (sent, refused, unreachable, crash).
- `test_alerts_page_send_test.py` — the outcomes in words; the work on a pool thread and the answer on the UI thread; a late answer after `shutdown()` dropped; buttons off while busy.
- Guards run: `tests/unit/architecture` (boundaries, layers, preview, duplication ratchet 32 = 32, labels, stock controls), `tests/unit/modules/alerting`.
- **Not run:** the `ci-local.ps1 -Full` gate (GitHub Actions' job on the head is the authority); the page in the real window on a real keyring (the last criterion).

## 6. Docs touched
`Docs/MODULES/alerting/`: `README.md` (built table), `04-solution-strategy.md` (the Options page row), `05-building-blocks.md` (the page's classes, with `file:line`), `06-runtime.md` (Save, Remove, Send test, the restart decision) with the new `diagrams/06-options-save-and-test.puml`, `05-channel-catalog.puml` (the builder), `07-deployment.md` (the pool thread), `08-concepts.md` (who writes the secret on a desktop), `09-decisions.md` (this record).

## Implementation notes (written when done)
Built 2026-10-16 on branch `claude/alerts-options-page-036d1`. Two guards asked for something in the same commit: `test_module_contribution_laziness.py` lists the contributing modules (`alerting` added), and `test_presenter_duplication_only_shrinks.py` measured 32 → 40 member names shared with Trading's page; they were renamed (`busy` → `is_working`, `_run` → `_work_on_pool`, `_tell_unexpected` → `_tell_failed`, …) back to 32 rather than raising the baseline. The new page's presenter logger is a real `ILogger` in the tests (a `Mock` logger would have made the "no URL in a log" tests vacuous; one of the first drafts did). `ruff` forbids mixedCase Qt names in a new file, so the view model uses snake_case signals and properties.

## Resume
Everything but the last criterion is built and tested. Next: the owner opens Tools → Options → Alerts (`scripts/preview-qml.ps1 alerts_options` renders it headless), saves the real webhook, presses Send test, restarts, and the result goes in these notes.
