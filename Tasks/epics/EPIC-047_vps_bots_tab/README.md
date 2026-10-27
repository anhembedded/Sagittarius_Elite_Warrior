# EPIC-047 — A desktop tab shows and controls the bots on the VPS host

- **Status:** 🟡 In progress (3/7) — 047A done 2026-10-26 (the wire codec and the handshake), 047B done 2026-10-27 (the host's facts file, #738), 047C done 2026-10-27 (the bridge, #739; the VPS run is the owner's); 047D in review (the desktop transport, profiles and the Options page; the dependency approval, the Windows agent login and the real-link reconnect time wait on a person); resumed by the owner on 2026-10-26 (*"làm tiếp epic EPIC-047"*); EPIC-048B's second pull request is queued for when 047E needs it
- **Repositories:** Elite
- **Origin:** the owner's request of 2026-10-24: a VPS Bots tab that connects to the VPS and controls its bots, with the same interface as the Bots tab, both sharing every module (charter §2.1). The owner delegated the design decisions on 2026-10-24: *"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"* ("decide them for me, consistent with the whole Constitution"). The charter, Discover and De-risk steps are in this folder.
- **North star:** [`CHARTER.md`](CHARTER.md) v0.5 (scope, constraints, AC1–AC9), [`DISCOVER.md`](DISCOVER.md) v0.2, [`DERISK.md`](DERISK.md) v0.3. The headless operation it extends: [`Docs/OPERATIONS/headless_runbook.md`](../../../Docs/OPERATIONS/headless_runbook.md).
- **Decisions:**
  - [`DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md`](DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) — G6, G7, G7a, G10: the doors, the bridge, the identity, the facts file, the protocol, the version rule.
  - [`DECISION_2026-10-26_the_bridge_revision_and_the_unbuilt_venue.md`](DECISION_2026-10-26_the_bridge_revision_and_the_unbuilt_venue.md) — the bridge's own per-bot revision, an unbuilt venue's key state in the facts file, exchange facts as fresh as the last read (D1–D3, defaults by the coordinator, owner may veto).
  - [`DECISION_2026-10-24_the_ssh_client_is_asyncssh.md`](DECISION_2026-10-24_the_ssh_client_is_asyncssh.md) — G1: `asyncssh`, the dependency as a change, the acceptance items.
  - The UI's doors (G9) are [EPIC-048](../EPIC-048_ui_reaches_the_application_through_its_doors/DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md)'s record.
- **Dependencies:** **[EPIC-048](../EPIC-048_ui_reaches_the_application_through_its_doors/README.md) children A and B must be done first** ([EPIC-048A](../EPIC-048_ui_reaches_the_application_through_its_doors/completed/EPIC-048A_the_doors_rule_and_its_guard.md), the rule and the guard; [EPIC-048B](../EPIC-048_ui_reaches_the_application_through_its_doors/incomplete/EPIC-048B_the_bots_screen_through_the_doors.md), the Bots screen through the doors). No EPIC-047 code starts until the guard holds for the Bots screen (G9). Every child below carries this prerequisite. EPIC-048C and 048D may finish after EPIC-047.

---

## 1. Decisions already made
1. The link cuts in at the application's doors; the pure assessment runs on the desktop; commands go through `IHostControl` (G6, remote link record D1).
2. v1 is SSH only. The bridge is a second process on the host, started by `sshd` behind a forced-command key for the `sew` account; the host listens on no socket (G7, record D2–D3).
3. The host writes the facts only it holds to a file when they change; the bridge never calls the exchange (G7a, record D4).
4. Per-bot revision, heartbeat and idle watchdog, handshake on wire names, one reflective codec with a contract test per root; any version difference refuses the link (G10, record D5–D6).
5. The SSH library is `asyncssh`, `paramiko` the fallback; the dependency enters with the transport child (G1, SSH record).
6. One host at a time (G2), a real-money start through the host's own handlers and venue confirmation (G3), the bot's own log lines in a later child (G4), two tabs from the same classes (G5), no Engine change (G8).

## 2. Goals — measurable
| Metric | Today (measured 2026-10-24) | When the epic is done |
| :--- | :-: | :-: |
| VPS bots visible in a desktop tab | 0; the VPS is read through SSH text (`M bot list`, `M bot show`) | every VPS bot with the Bots tab's list, chart lines, Checks, Plan rows, orders and fills (AC1) |
| Time from a fill on the VPS to the tab | no tab | ≤ 5 s (AC2); De-risk measured about 0.17 s of transport against it |
| Actions of the Bots tab available on a VPS bot | 0 | every one, with the host's verdict and an audit line (AC3); a mainnet start without confirmation refused (AC4) |
| Sockets the host listens on with the default profile | 0 (EPIC-038) | 0 (AC5) |
| Reconnect after an abrupt cut, on the real link | 1909 ms (De-risk, asyncssh) | under 2 s, with the slim bridge entry point |
| Manual steps to put a designed plan on the VPS | export, `scp`, `M bot add` | 0 file copies by hand |
| Classes shared by the two tabs' widgets and presenters | n/a | the same classes (AC7) |
| Existing Bots tab behaviour | — | unchanged (AC8) |

## 3. Sub-tasks, ordered by risk
<!-- Dependency order within risk: A and B have no EPIC-047 prerequisite; every child waits for EPIC-048A and 048B. -->
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-047A](completed/EPIC-047A_the_wire_codec_and_the_version_handshake.md) | The reflective wire codec, a contract test per root type, and the version handshake on wire names | Elite | EPIC-048A and the first pull request of EPIC-048B | 🟡 | ✅ Done (2026-10-26) |
| [EPIC-047B](completed/EPIC-047B_the_host_writes_its_in_memory_facts_to_a_file.md) | The host writes the facts it holds in memory to a file when they change (G7a) | Elite | EPIC-048A and the first pull request of 048B (#731) | 🔴 | ✅ Done (2026-10-27) |
| [EPIC-047C](completed/EPIC-047C_the_bridge_behind_a_forced_command.md) | The bridge: a second process behind a forced-command key for the `sew` account, commands through `DirectoryHostControl` | Elite | 047A, 047B | 🔴 | ✅ Done (2026-10-27) (VPS run pending, the owner's) |
| [EPIC-047D](incomplete/EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) | The desktop transport on `asyncssh`, connection profiles and the Options page (O6, D5), with Windows agent login and a reconnect under 2 s | Elite | 047A, 047C | 🟡 | 🟡 In review |
| [EPIC-047E](incomplete/EPIC-047E_the_vps_bots_tab.md) | The VPS Bots tab: two tabs, the same classes (AC7) | Elite | 047D | 🔴 | Planned |
| [EPIC-047F](incomplete/EPIC-047F_the_bots_log_lines_in_the_tab.md) | The selected bot's own log lines in the tab (G4) | Elite | 047E | 🟢 | Planned |
| [EPIC-047G](incomplete/EPIC-047G_the_runbook_for_the_vps_link.md) | The runbook: key setup for `sew`, `PasswordAuthentication no`, troubleshooting | Elite | 047C (steps), 047D (profile) | 🟢 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 0 — prerequisite | EPIC-048A and 048B done: the guard holds for the Bots screen | EPIC-048's phase 2 evidence. Not run |
| 1 — wire and host (A, B) | A record crosses a JSON wire and back equal for every root type; the host publishes its facts file | The contract tests; the facts file's test on a running host. Not run |
| 2 — the link (C, D) | The desktop logs in as `sew` with the restricted key, runs the bridge, reconnects in under 2 s; no listener on the host | The AC2, AC5, AC6 checks on a fake host, then on the owner's VPS. Not run |
| 3 — the tab (E, F) | AC1, AC3, AC4, AC7, AC8 | Side-by-side with `M bot show`; the architecture test for AC7; a dry run on the owner's VPS. Not run |
| 4 — operation (G) | The owner sets up a new desktop from the runbook alone | The runbook walked through once on a clean profile. Not run |

## 5. Out of scope
As the charter §4: any inbound port; a change to a bot's behaviour or a trading rule; backtests on the VPS; managing the VPS itself from the tab (`sew-update`, `sew-key`, systemd, backups); editing exchange keys, alert channels or the loss cap remotely; mobile or web access, more than one user, role-based permissions; the Trade tab on the VPS account. Also: several hosts at once (G2), a read-only mode across versions (record D6), a Unix socket, a VPN or a TLS endpoint (record O1), an Engine change (G8). Cleaning up the stray table fragment in the charter §4 (after the Constitution check) is left to the next charter revision.

## Notes (newest first)
- **2026-10-27** — 047C marked Done (merged #739). 047D built on `claude/epic-047d-desktop-transport`: the desktop's protocol, link, supervisor and `asyncssh` adapter in `support/wire/desk/`, the connection profile in `core/contracts/`, the profiles' memory and the Options page "VPS Link"; proved against a real `asyncssh` server with the real bridge behind it on loopback. Waits on a person: the `asyncssh` approval (ONBOARDING §7), the Windows agent login and the real-link reconnect time (047D's "Owner step").
- **2026-10-27** — 047B marked Done (merged #738). 047C built on `claude/epic-047c-bridge`: the bridge process, its protocol, the revision rule, the unbuilt venue's key state; one rule widened (`shell/` may import a module's `link.py`); the restricted-key check and the VPS import time wait for the owner (047C's "Owner step").
- **2026-10-24** — Epic scaffolded: the charter, Discover and De-risk documents moved from `Tasks/proposal/EPIC-047_vps_bots_tab/` with `git mv`; two decision records (the remote link; the SSH client) and seven children; the UI's-doors epic is [EPIC-048](../EPIC-048_ui_reaches_the_application_through_its_doors/README.md).

---

## Resume (done: the owner resumed this epic on 2026-10-26)
The owner paused this epic on 2026-10-25 (*"tạm thời dừng epic đó ... sau này làm tiếp"*, "stop that epic for now ... continue later"). Nothing was built; every document stays valid.
- **Ready:** the charter v0.5, Discover, De-risk (v0.3, with the owner's own run against the VPS on 2026-10-24), the two decision records, and the seven children.
- **Owner's run still on record:** key-based SSH works from the owner's Windows desktop to the VPS root account; the epic's runbook (child G) must have the `sew` account's forced-command key setup and `PasswordAuthentication no`.
- **To resume:** first finish EPIC-048 children A and B (the guard and the Bots screen through the doors); then start with child A (the wire codec and the version handshake) and B (the host's facts file), which do not depend on each other.
- **Re-check before resuming:** the De-risk numbers were measured at `5ddbd68`; re-run the R7 count against the then-current guard baseline and say what changed.
