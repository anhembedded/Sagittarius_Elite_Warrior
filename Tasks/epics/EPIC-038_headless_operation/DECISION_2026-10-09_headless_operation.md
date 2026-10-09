# ADR — No TUI in EPIC-038; headless operation is a `run` host, a status read model and machine-readable output

**Epic:** [EPIC-038](README.md)
**Date:** 2026-10-09
**Status:** Accepted for D1–D3 (the owner's instruction); Proposed for D4–D6; O1–O8 are open and pending the owner
**Decided by:** D1–D3 the owner, 2026-10-09, relayed by the coordinator session's brief: the owner wants the app to run bots with no GUI, from the command line on a VPS (Linux or a Windows server), and said *"nhớ chú ý design dễ dàng mở rộng SOLID"* (translated: mind a design that is easy to extend, SOLID); the brief also says *"No TUI in this epic. Record the decision and its reasons"*. D4–D6 are this epic's proposals; they become decisions when the owner answers. O1–O8: Pending.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted, then translated |
| ❓ Open | blocks the named phase until answered |

## 1. Context
The app already has a headless path (`main.py` commands and an interactive REPL, ✅ `src/main.py`), but it does not boot without PySide6 (✅ [DESIGN §1.1](DESIGN_2026-10-09_headless_operation.md)), cannot run until told to stop, handles no signal, reports no exit code and has no status a script can read. The owner wants to run bots from a VPS command line. Real operators' experience is in [`RESEARCH_2026-10-09_headless_operation.md`](RESEARCH_2026-10-09_headless_operation.md). `EPIC-037`'s analysis names "sibling paths that do one job and drift" as bug class A; the epic's design is arranged so the CLI and the GUI share one path.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **No TUI in this epic.** Headless operation is `run` (a service), `status [--watch] [--json]`, `bot …` verbs and alerts. | Accepted | 🟢 the owner (brief) | Reasons in §2.1. Reconsideration conditions in §2.2. |
| D2 | **Reuse the existing CLI machinery.** New commands are `declare_cli` entries plus rows in `cli_commands.json`; no second parser. Bot verbs dispatch the same commands the UI does through `ICommandDispatcher`. | Accepted | 🟢 the owner (brief: "Reuse before inventing") | The CLI and the GUI run one handler per action; a parity test per verb. |
| D3 | **Open/closed by registration.** A command, secret backend, output format, preflight check, health contributor, stop policy or supervisor integration is one new class registered; no edit to existing code. | Accepted | 🟢 the owner (brief: "easy to extend, SOLID") | [DESIGN §9](DESIGN_2026-10-09_headless_operation.md) lists the cases; each child task names the port it adds. |
| D4 | A new bounded context `src/modules/operations` holds the host, preflight and status; `bots` owns the `bot` verbs; a small shared-kernel addition (`ExitCode`, `Report`, `IOperationsRegistry`) goes in `core/contracts`. | 🔵 Proposed | Pending | The alternative (everything in `shell/` and `bots/cli`) is smaller and puts a run loop in the composition layer; rejected because it makes `shell/` a god package, but the owner may prefer fewer modules. |
| D5 | `status` reads a snapshot file the host writes (`state/health.json`) plus the held lock; **no port is opened**. | 🔵 Proposed | Pending | No new attack surface (R11). A live control channel is O4. |
| D6 | The headless wiring is separated from the GUI wiring in the composition root: UI-only subscribers and validators (UI failure handler, asset validator, the Qt packages in the dependency list) are added by the GUI entry point, not by `create_app`. | 🔵 Proposed | Pending | Qt-free boot without touching the Engine; the CI guard enforces it. `EPIC-036B` later replaces `notification_event_handler.py`, so 038A moves only what 036B would otherwise have to untangle. |

### 2.1 Why not a TUI (D1)
1. **It would be a third presentation layer.** The app has a QtWidgets GUI and a `cmd.Cmd` shell; a curses/Textual UI would be a third place that reads bot state and a third place that must dispatch commands. "Sibling paths that do one job drift" is bug class A in `EPIC-037`'s analysis (the bot built its own symbol picker instead of reusing one). The CLI-over-`ICommandDispatcher` design makes two paths share one handler; a TUI adds a path with its own widgets, its own refresh model and its own concurrency (a terminal UI loop beside a host's signal loop and bot worker threads).
2. **The need is covered by cheaper parts.** `status --watch` (a refresh of one `Report` through the same renderer) plus alerts (`EPIC-036`) answers "is it alive and what is it holding" over SSH; the sources show operators use `/status`, `/health` and notifications, not a dashboard in a terminal (R12).
3. **A TUI is attack and maintenance surface for no new capability.** Each of the sources that warns about exposed UIs and APIs (R11) is about adding an interface; this epic opens no port and no new input path.
4. **A TUI cannot be a service.** A supervised service has no terminal. The decisive path is the one with no human attached (`run`), so building a human-attached interface first optimises the wrong end.
5. **Cost.** A TUI library is a new dependency (`ONBOARDING.md` §7, owner approval) and a new test tier.

### 2.2 When a TUI would be reconsidered (D1)
Reconsider only if **all** of the following hold: (a) `status --watch` and the alerts have shipped and been used for at least a month; (b) the owner names an interactive action that `bot …` verbs plus a re-run cannot express (for example live editing of a running bot's range while watching fills); (c) that need survives the control-channel decision O4, i.e. it is still wanted after a live control path exists; (d) the TUI would be a *view over the same `Report` and `ICommandDispatcher`* — a renderer and an action source, not a new state model — and its dependency is approved. Until then, the answer to "I want a dashboard" is the GUI on the desktop and `status --watch` on the server.

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| Make the interactive REPL the production host (run it under `tmux`) | Needs a terminal; a systemd unit has none; the REPL waits on `input()`. It stays the developer's tool. |
| A local HTTP/REST API like Freqtrade's | Opens a port and an auth problem for no capability the snapshot + exit codes lack; the sources are a catalogue of mistakes with it (R11). |
| Ship the desktop app under a virtual display (Xvfb) | Hides the Qt dependency instead of removing it, costs RAM, and a GUI hang looks like a healthy process. |
| Fix only `create_app` for headless and skip the guard | The coordinator's claim of "already headless" was wrong for exactly this reason; without a CI guard it will be wrong again. |
| One big `bot` CLI that edits the bots' files directly | Bypasses the lifecycle table and the read-only rule; the sibling path the epic exists to avoid. |

## 4. Open questions (pending the owner; each with a recommendation)
| # | Question | Options | Recommendation | Blocks |
| :-- | :--- | :--- | :--- | :--- |
| O1 | What does shutdown do to resting orders? | A leave resting · B stop bots first · C per bot kind | **A by default; B as `--on-stop stop-bots`; C deferred.** Same behaviour as closing the GUI and as a crash, one path tested. | 038D |
| O2 | After a restart, RECOVERING bots: who resumes them? | (a) a person, by `bot resume` · (b) `--resume-recovering` opt-in · (c) always | **(a) default; (b) offered only after 036B + 036C have shipped.** Nothing trades unattended while a crash is silent. | 038D |
| O3 | Which secret backend is supported on a server? | env only · systemd credentials · permission-checked file · keyring+D-Bus · third-party encrypted file | **Linux: systemd credentials (env fallback). Windows: Credential Manager via keyring under the service account if 038E proves it works for a service, else the permission-checked file.** A backend holding secrets is the owner's security decision. | 038E |
| O4 | Control of a *running* host: in v1? | none (restart to change) · spool directory · local socket/named pipe · Discord only (036F) | **None in v1; control is restart + `bot apply`, and remote control is `EPIC-036F`.** Revisit only with a stated need. | 038J |
| O5 | Windows supervisor | NSSM · Task Scheduler · WinSW · a native Windows service in Python | **NSSM documented as an external tool, Task Scheduler as the stated fallback;** neither becomes a dependency. | 038H |
| O6 | A headless dependency set | add `requirements-headless.txt` (no PySide6, pyqtgraph, pytest-qt) · keep one file | **Add it** — a server should not install Qt's system libraries (run C needed `libEGL`). Dependency change: approval. | 038A |
| O7 | Engine changes | (i) a Qt-free home for `UiActionFailedEvent` · (ii) `RotatingFileHandler` in `StdLogger` | **Neither in this epic.** (i) is avoided by D6; (ii) is covered by journald/NSSM, and logged as a separate Engine proposal if the owner wants a rotating file. Engine edits need a separate confirmation (`ONBOARDING.md` §2). | 038A, 038G |
| O8 | May `run` start mainnet venues on its first release? | same rules as the GUI · testnet-only for the first release | **Same rules as the GUI,** with the startup warning (§11 of the design) while alerts are not carrying bot events; the venue confirmation the screen shows must have a CLI equivalent (to verify in 038D). | 038D |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | none (a boundary) | Accepted; nothing to deliver | this record; [`EPIC-038` README](README.md) §5 |
| D2 | 038B, 038C, 038I | Not started | Not yet verified |
| D3 | 038B, 038D, 038E, 038F | Not started | Not yet verified |
| D4 | 038D, 038F | Not started | Not yet verified |
| D5 | 038C | Not started | Not yet verified |
| D6 | 038A | Not started | the probe in DESIGN §1.1 is the evidence for the problem, not for the fix |
