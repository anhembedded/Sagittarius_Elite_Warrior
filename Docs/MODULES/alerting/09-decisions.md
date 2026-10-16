Status: Current

# `alerting` — 9. Decisions

*Which decisions shaped the module?* An index: each record is read where it lives, never copied here.

| Record | What it decided |
| :--- | :--- |
| [ADR 036 of 2026-10-08](../../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-08_alerting_module.md) | N1 a bounded context that listens to contracts; N2 the persistent outbox with a 24 h expiry; N3 secrets in the keyring (superseded on a headless host by the record below); N4 the defaults; N5 per-bot modes; N6 remote control as Phase 4; N7 the dead man's switch; N8 a CRITICAL on two channels |
| [ADR 036 of 2026-10-15](../../../Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-15_walking_skeleton_and_headless_secrets.md) | Discord first, the walking skeleton first, where a channel's secret comes from on a headless host |
| [Design 036 of 2026-10-08](../../../Tasks/epics/EPIC-036_alerting_module/DESIGN_2026-10-08_alerting_module.md) | The design the owner approved; superseded as the current design by this folder and kept as the record |
| [Research 036](../../../Tasks/epics/EPIC-036_alerting_module/RESEARCH_2026-10-08_alerting_lessons.md) | The lessons the design was built from |
| [EPIC-041, 2026-10-16](../../../Tasks/epics/EPIC-041_documentation_standard/DECISION_2026-10-16_module_docs_one_folder_arc42.md) | This folder's layout; `alerting` is its pilot |
| [EPIC-036D1, 2026-10-16](../../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036D1_options_alerts_page_discord_webhook.md) | The Options page writes the keyring only; a first save or a removal takes effect after a restart, not by rebuilding the lanes (task §3) |
