# Clarify (Epic Charter) — EPIC-047 VPS Bots tab

| Field | Value |
|-------|-------|
| Document type | Epic Charter — Initiation phase (Clarify) |
| Epic | EPIC-047 — A desktop tab that shows and controls the bots on the VPS host |
| Version | 0.4 (Draft) |
| Status | Scope and decisions G1–G9 settled on the owner's delegation (2026-10-24); G1, G6 and G7 are provisional until De-risk |
| Author | Coordinator session (for the owner) |
| Epic owner / approver | Nathan Tran |
| Last updated | 2026-10-24 |
| Related documents | `Docs/OPERATIONS/headless_runbook.md` · EPIC-038 (headless operation) · EPIC-045 (every Bots tab action has a host verb) · EPIC-036F decision record (remote control from Discord, "no inbound port") |

**Revision history**

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 0.1 | 2026-10-24 | Coordinator | Initial draft from the owner's request of 2026-10-24 |
| 0.2 | 2026-10-24 | Coordinator | Owner's review: the solution is not approved, so §2.1 lists candidates only; O6 added (connection configuration and selectable protocols); the SSH client choice, the layer the remote link cuts at, and an Engine IPC port become open questions (G1, G6, G7); next step is Discover |
| 0.3 | 2026-10-24 | Coordinator | Discover's Finding E (the UI reaches the application around the dispatcher and the bus) accepted by the owner: G9 and A7 added |
| 0.4 | 2026-10-24 | Coordinator | G1–G9 decided on the owner's delegation, with the Constitution check; G1, G6, G7 provisional until De-risk R1–R4; next step De-risk |

---

## How to read this document

This document is the **Initiation phase** of one epic. It says *why* the epic exists, *what* it must deliver, its *scope*, its *constraints*, and what *done* means. It does **not** hold the design, the task breakdown or the estimates; those come after approval, in the epic's decision record and its `README.md`. No solution is chosen in this document: §2.1 lists candidates for the Discover and De-risk steps to examine.

**Conventions.** `Open` marks a question the owner answers before the design starts. `Unknown` marks a fact still to be measured.

| Question | What to determine | Section |
|----------|-------------------|---------|
| Why? | Why does this epic exist? What is the current problem? | 1, 2 |
| What? | What is the concrete output to deliver? | 3 |
| Scope? | What is in, what is out? | 4 |
| Constraints? | Security, real money, dependencies, compatibility | 5 |
| Done? | What proves the epic is complete? | 6 |

Also: summary (7), approval (8).

---

## 1. Epic overview

### 1.1 Background
The application runs the same bots in two ways: the **desktop app** (the Bots tab) and the **headless host** on a Linux VPS (`sew-run`). Since EPIC-045, every Bots tab action that changes a bot has a verb on the running host (`M bot add`, `start`, `pause`, `resume`, `stop`, `edit`, `move`, `delete`, `apply`, `confirm-resume`, `arm-strategy`). The owner runs real-money bots on the VPS and test bots on both machines.

### 1.2 Problem statement (current pain)
- The VPS bots can be seen and controlled **only through SSH and text commands** (`M bot list`, `M bot show`, …). The desktop shows the desktop's own bots only.
- The text view lacks what the Bots tab gives: the chart with the ladder, SL, TP and trigger lines; the Checks panel; the Plan rows (loss at stop, result at take profit, liquidation estimate); the order and fill tables.
- A plan designed on the desktop reaches the VPS through **Export plan → `scp` → `M bot add`**: several manual steps, each a chance for a mistake on a real-money host.
- Reading the state of a VPS bot (for example during the BUG-268 investigation) needed `tar`, `scp` and an upload: slow and error-prone.
- The two places use **different exchange accounts** (found on 2026-10-22), which already caused confusion about a position. One screen that names which host and account it shows would prevent that.

### 1.3 Real situations from the last week
- 2026-10-22: "the VPS position is still shown" — the desktop and the VPS read different testnet accounts; finding out took several rounds of screenshots.
- 2026-10-23/24: checking `nhipxx`'s figures needed `bot show` text pasted into chat, then a state archive copied by `scp`.
- Every new VPS bot: design on the desktop, Export plan, `scp`, `M bot add`, `M bot start --confirm-venue …`.
- After every `sew-update`: `M bot resume <id>` for each bot, typed by hand.

---

## 2. Business case and objectives

### 2.1 Requirement vs solution

| | Statement |
|---|-----------|
| Stated solution | "A VPS-BOT tab that connects to the VPS and controls its bots, with the same interface as the Bots tab; both share every module, one local, one through the VPS." |
| Root requirement | "The owner sees and controls the bots running on the VPS with the same information, the same checks and the same safety as the local bots, without typing commands over SSH." |

**Conclusion.** The stated solution matches the root requirement. One condition comes from the safety constraints (§5): the VPS host stays the **only writer** of its bots, and every remote command passes the **same control door and audit** the `M bot …` commands use today. The tab is a remote view and a remote control, never a second copy of the bots.

**Candidate directions, not decided** (to be examined in Discover, then proven in De-risk):
- **Where the remote link cuts in.** (a) A port of the Bots screen only; (b) the application's command dispatcher and event bus, so a command enters the same command mechanism the local tab uses and events come back on the bus (owner's preference, 2026-10-24); (c) a facility of the Engine (an IPC or WebSocket port on the bus), so every application on the Engine gets it.
- **How the host answers.** Through the host's existing control door and audit (`EPIC-038J`), or through a new gate in front of the host's dispatcher with the same checks.
- **Transport and protocol.** SSH (through the operating system's client, or a Python library for portability, the owner's preference), a VPN interface, or a direct TLS endpoint; with a request/response and event protocol on top (for example JSON-RPC or WebSocket messages).

The choice is recorded in the epic's decision record after De-risk, with the Constitution check. Whatever is chosen must meet §5.

### 2.2 Objectives

| ID | Objective | Measurable | Relevant |
|----|-----------|------------|----------|
| O1 | **See** every VPS bot in a desktop tab with the Bots tab's layout | The list, state, earnings, chart lines, Checks, Plan rows, orders and fills of a VPS bot are shown; a change on the VPS appears in the tab within a few seconds | Replaces `bot list` / `bot show` over SSH |
| O2 | **Control** the VPS bots from that tab | Every action the Bots tab offers works on a VPS bot (start, pause, resume, confirm resume, stop, edit, add, delete, move, arm or disarm a strategy), with the host's own answer shown | Replaces typed `M bot …` commands |
| O3 | **Same safety** as on the VPS | A remote command is refused or accepted exactly as the same `M bot …` command would be, and appears in the host's audit; a real-money start or resume asks for the venue confirmation | Real money |
| O4 | **One codebase** for both tabs | The VPS tab adds no second copy of the Bots screen's widgets or presenters; a test proves both tabs are built from the same classes | Owner's requirement: "2 modules share everything" |
| O6 | **Configurable connection** | The owner sets up a VPS connection in the app (a profile: name, host, port, user, credentials reference, the protocol to use, timeouts, reconnect) and can choose among more than one supported protocol without a code change; adding a protocol later does not change the Bots screen | Owner's requirement, 2026-10-24: portable, not tied to one transport |
| O5 | **Honest connection state** | The tab always says which host and which exchange account it shows, whether it is connected, and how old its data is; losing the connection never affects the bots | Prevents the 2026-10-22 confusion |

---

## 3. Deliverables

| ID | Deliverable | Description | Linked objective |
|----|-------------|-------------|------------------|
| D1 | **The seam** | The point where a local and a remote backend can be swapped under the same Bots screen, at the layer the decision record chooses; the current tab keeps working with no visible change | O4, O6 |
| D2 | **The host's remote read side** | The running host answers the Bots screen's queries and sends its updates to a connected desktop, reachable only through a protocol that opens no Internet-facing port by default | O1, O5 |
| D3 | **The host's remote command side** | Remote commands reach the host's own command mechanism behind the same checks as the CLI: a request id, the audit and the mainnet confirmation | O2, O3 |
| D4 | **The VPS Bots tab** | The same screen on the remote adapter: a host picker, the connection line (host, account, connected or not, data age), read-only while disconnected | O1, O2, O5 |
| D5 | **Connection profiles and protocols** | An Options page for VPS connections: one profile per host, the protocol chosen per profile, credentials referenced (a key file or an agent), never stored as plain text by the app; at least one protocol in v1, the others behind the same seam | O5, O6 |
| D6 | **Documentation** | Runbook section (set up the tunnel, troubleshoot), module design update, a `Docs/LEARNING/` page on the design | All |

**Inputs and outputs of the tab**

| Item | Answer |
|------|--------|
| What goes in? | The owner's clicks on the VPS Bots tab, as on the Bots tab |
| What comes out? | The VPS host's bots, their figures and the host's answer to each command |
| Where does it run? | The desktop (Windows), connected to the VPS (Ubuntu, `sew-run`) over SSH |
| What happens when the VPS is unreachable? | The tab shows the last data with its age, refuses commands, and reconnects by itself; the bots on the VPS carry on |

---

## 4. Scope management

**In scope:**
- One VPS host at a time, chosen in the tab
- Everything the Bots tab shows, for a VPS bot (list, detail, chart lines, Checks, Plan rows, orders, fills, ladder, log of the bot's events)
- Every Bots tab action on a VPS bot, through the host's control door
- Adding a bot to the VPS from a plan designed on the desktop, with no file copy by hand
- Connection state, host and account named on screen; reconnection
- A refusal when the desktop and the host run incompatible versions ("run `sew-update`")

**Out of scope:**
- Opening any port on the VPS to the Internet
- Changing the bots' behaviour, or any trading rule
- Running backtests on the VPS (the backtest stays on the desktop, on its own candles)
- Managing the VPS itself from the tab: `sew-update`, `sew-key`, systemd, backups
- Editing exchange keys, alert channels or the loss cap remotely
- Mobile or web access; more than one user; role-based permissions
- The Trade tab (manual orders) on the VPS account

**Decisions** (2026-10-24). The owner delegated them in their own words: *"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"* ("decide them for me, consistent with the whole Constitution"). The coordinator decided each one, checked below against P1–P11. A decision marked *provisional* holds unless the named De-risk experiment disproves it. The owner may veto any row.

| ID | Question | Decision | Status | Why |
|----|----------|----------|--------|-----|
| G1 | System OpenSSH client or a Python library? | **A Python SSH library, `asyncssh` first, `paramiko` as the fallback.** The library is pinned in `requirements.txt` and `requirements.lock` in the first PR that needs it, and the dependency is named in that PR's body | Provisional until R3 | Portability: same behaviour on every OS, owner's preference. Mechanism over memory (P1): errors are typed, not parsed from a child process's stderr. Testable in-process. Pageant and OpenSSH agent support (R3 checks it on the owner's Windows). It runs on the same asyncio model as `websockets` |
| G2 | One host or several? | **One host at a time, chosen from the profiles.** Several hosts become one more profile and a picker, with no change to the seam | Decided | P7: a seam now (profiles), the variant later |
| G3 | Real-money start from the tab? | **Allowed, through the host's own `*ForHost` handlers and the same venue confirmation as `M bot start --confirm-venue`.** No new real-money rule: the tab asks the same question, and the host judges it exactly as for the CLI | Decided | P3: the confirmation stays in one place (the host). Trust is the same as an SSH shell, which can already do it. A remote command never bypasses the host's checks (§5.1) |
| G4 | The host's log lines in the tab? | **Yes, read-only, only the selected bot's own events.** Comes in a later child, not the first | Decided | Owner's pain (§1.3); bounded scope |
| G5 | Two tabs or one with a switch? | **Two tabs (Bots, VPS Bots), built from the same classes**; AC7 proves it | Decided | Owner's request; O4 |
| G6 | Where does the link cut in? | **At the application's doors: the command dispatcher (queries and commands) and bus events, plus an allowlist of UI-only ports**, which G9 standardises first. The screen receives read models from queries and does not compute readiness itself. Commands reach the host through `IHostControl`, whose port already names "a different transport" as its extension case, so the host's gate, audit, replay and expiry checks stay the one door | Provisional until R1 and R4 | P5: reuse the existing gated port, mirror the CQRS-bridge pattern (Discover §6). P6: fix the doors, not one screen. P3: one gate, not two |
| G7 | Which protocols in v1? | **v1: SSH only, with the host listening on no socket.** The desktop runs a bridge command on the host over SSH (the Docker `dial-stdio` pattern) and speaks a versioned message protocol on its stdin and stdout. Later variants behind the same transport seam: a VPN (WireGuard or Tailscale) and an opt-in TLS endpoint | Provisional until R2 | P5: a battle-tested shape (Docker). P8: EPIC-038's "the host listens on no port" decision and its test are kept, not loosened. P7: one variant now, the seam for the others |
| G8 | Engine change in this epic? | **No.** The bridge lives in the app (`support/` for the technical part, `operations` for the host's gate). It moves to the Engine only when a second consumer needs it; the Engine's `TraceServer` envelope is studied as a model, not changed | Decided | P5: repository mechanisms first. P7: no variant without a case. No Engine change needs confirming |
| G9 | Standardise the UI's doors inside EPIC-047, or first, separately? | **A separate epic, done first and numbered at its scaffolding.** It contains: a rule in `architecture-rule.md`; a guard test with a baseline that only shrinks; read models instead of presenter computation; presenters receive a narrow application gateway instead of the container. EPIC-047's code starts after its guard is in place for the Bots screen | Decided | P1: a guard test, not prose. P6: the mechanism, every screen. P8: a ratchet baseline |

**Constitution check (all decisions together)**
| Invariant | Holds? | How |
|-----------|--------|-----|
| P1 Mechanism over memory | Yes | G9's guard test; G7 keeps the "no port" test; typed transport errors (G1) |
| P2 Verify, don't restate | Yes | provisional rows wait for R1–R4 evidence; nothing claimed untested |
| P3 A copy drifts | Yes | one gate (`IHostControl` + `HostCommandProcessor`); the confirmation judged only on the host (G3) |
| P4 Green proves only what was tested | Yes | De-risk proves the risky points on the owner's real machines (R2, R3), not only in tests |
| P5 Apply before you invent | Yes | repository port reused; Docker and CQRS-bridge shapes mirrored; a library, not a hand-written SSH |
| P6 Fix the mechanism | Yes | G9 fixes the doors for every screen, not only Bots |
| P7 Seam now, variant later | Yes | one transport, one host, one tab variant; seams for the rest |
| P8 Ratchets only fall | Yes | no guard loosened; the new guard starts from a baseline that only shrinks |
| P9 Decide alone | Yes | decided under the owner's delegation; escalation kept for vetoes |
| P10 Pyramid and units | Yes | targets in §6 carry units (s, verdicts, sockets) |
| P11 Prompt-grade artifacts | Yes | each decision names its evidence and its condition |

----|-----------------|------------------|----------------|-----|
| G1 | SSH through the system's OpenSSH client, or through a Python library (`asyncssh` or `paramiko`)? | Owner's preference: a Python library, for portability. A new dependency needs the owner's approval | Owner | After Discover |
| G2 | Several VPS hosts in one tab, or one host at a time? | One at a time, with a host picker | Owner | Before design |
| G3 | Is a real-money **start** allowed from the tab, or only pause, resume and stop? | Allowed, with the same venue confirmation as the CLI | Owner | Before design |
| G4 | Show the VPS host's log lines for a bot in the tab? | Yes, the bot's own events only, read-only | Owner | Before design |
| G5 | Two tabs (Bots, VPS Bots), or one tab with a "Local / VPS" switch? | Two tabs, as the owner asked | Owner | Before design |
| G6 | At which layer does the remote link cut in: the Bots screen, the command dispatcher and event bus, or the Engine? | Open; the owner leans to the dispatcher and event bus, possibly an Engine port | Owner | After Discover |
| G7 | Which protocols in v1, which later? | Open; at least one that opens no Internet-facing port | Owner | After Discover |
| G9 | Standardise first that the UI reaches the application only through the command dispatcher and bus events (Discover, Finding E): inside EPIC-047, or as a separate epic done before it? | A separate preparatory epic: it helps every screen, not only this tab, and it is measured first (Discover R7) | Owner | Before design |
| G8 | Is an Engine change (an IPC or WebSocket port) in this epic, or a follow-up? | Open; an Engine change needs the owner's confirmation and its own commits in the Engine repository | Owner | After Discover |

---

## 5. Constraints and assumptions

### 5.1 Constraints
- **Real money.** The VPS runs mainnet bots. A remote command must never bypass the host's checks; a real-money start or resume keeps the venue confirmation.
- **No inbound port by default.** The owner's rule for remote control (EPIC-036F, D3): the trading host opens no port to the Internet. A protocol that needs one may exist only if the owner turns it on explicitly for a profile.
- **Single writer.** The host is the only writer of its bots' state; the desktop sends commands only.
- **Losing the connection is harmless.** No bot on the VPS depends on the desktop being connected.
- **No secret on the wire or on disk in the app.** SSH keys stay in the user's own SSH setup; the app stores host and user names only; no exchange key ever crosses the tunnel.
- **Dependencies.** A new dependency (an SSH library, a WebSocket library pinned directly) needs the owner's approval (`ONBOARDING.md` §7).
- **Engine.** An Engine change is possible (G8) but needs the owner's confirmation and separate commits in the Engine repository (`ONBOARDING.md` §2).
- **Architecture.** Layers and ports as in `architecture-rule.md`; QtWidgets only; background work per `async-ui-action-rule.md`.
- **Compatibility.** The desktop and the host may run different builds; the link must detect a mismatch and say so in words.
- **Right layer.** Each concern sits in its layer (`architecture-rule.md`): transport in a technical package or the Engine, the authorisation of a remote command at the host's application boundary, the Bots screen unaware of local or remote.

### 5.2 Assumptions

| ID | Assumption | Validate with | Status |
|----|------------|---------------|--------|
| A1 | The owner has an SSH key that logs in to the VPS | The owner logs in with the key from the desktop | Open |
| A2 | The host can serve an API beside its bots without slowing them (a small read load, one client) | Measure in the first API PR | Open |
| A3 | The Bots screen's data types (`bots/contracts`) can be serialised to JSON; `grid_ladder_payload.py` already does it for one of them | Inventory in the design step | Open |
| A4 | The host's control door (`DirectoryHostControl`) accepts every command the tab needs (EPIC-045 parity guard) | The parity test that exists today | Likely true |
| A5 | One owner, one or two VPS hosts | Owner | Open |
| A7 | The Bots screen can reach the application only through the dispatcher, the bus and an allowlist of UI-only ports, without a visible change (Discover, Finding E) | Discover R7, then the standardisation's own work | Open |
| A6 | Every query the Bots screen runs can be made asynchronous without changing what it shows (a remote query is slower than a local one) | Inventory in Discover | Open |

---

## 6. Success criteria and acceptance

### 6.1 Acceptance criteria

| ID | Criterion | Metric | Target | How measured |
|----|-----------|--------|--------|--------------|
| AC1 | The VPS tab shows the same facts as `M bot show` | Every field of `bot show` for each VPS bot | Identical values | Side by side on the owner's VPS |
| AC2 | Updates arrive quickly | Time from a fill on the VPS to the tab | ≤ 5 s | Fill timestamp against the tab's update |
| AC3 | Commands behave as the CLI | Each Bots tab action on a VPS bot | Same verdict and an audit line as `M bot …` | Integration test on a fake host, then on the owner's testnet bots |
| AC4 | Real-money confirmation kept | A mainnet start or resume without confirmation | Refused | Test plus a dry run on the owner's VPS |
| AC5 | No port opened by default | Sockets the host listens on with the default profile | None reachable from the Internet | Guard test, plus `ss -ltn` on the VPS |
| AC6 | Connection loss is safe | Cut the tunnel during a command and while idle | Bots unaffected; the tab says "disconnected, data as of …"; no command sent twice | Test plus a manual cut |
| AC7 | One screen, two backends | Classes of the two tabs' widgets and presenters | The same classes | Architecture test |
| AC9 | Connection is configurable | Create, edit and delete a profile; switch a profile's protocol | Works with no code change; credentials never stored as plain text by the app | Test plus the owner's use |
| AC8 | The local tab is unchanged | The Bots tab's existing tests and the owner's daily use | All green, no visible change | The full gate after D1 |

### 6.2 What success looks like

**Scenario 1 — A normal morning**
> The owner opens the desktop app and the VPS Bots tab, picks the profile "nathan-warrior". It says "nathan-warrior · Futures Mainnet account …1a2b · connected · updated 2 s ago". `y3embt` and `nhipxx` show their chart with the ladder, SL and trigger lines, their Checks and their earnings, exactly as `M bot show` would print them. A fill on the VPS appears in the tab a few seconds later.

**Scenario 2 — A new real-money bot**
> The owner designs a plan in the Bots tab and backtests it there. They choose "Add to VPS". The plan lands on the VPS as DRAFT, the VPS's own Checks run against the VPS's account, and Start asks "Type futures_mainnet to confirm". No file was copied by hand, and the host's audit holds the command.

**Scenario 3 — The connection drops**
> The laptop goes to sleep during a pause command. When it wakes up, the tab says "disconnected, data as of 21:04", then reconnects and shows whether the pause was carried out, read from the host's audit. The bots on the VPS ran the whole time. The command was not sent twice.

**Scenario 4 — Versions differ**
> The owner updates the desktop but not the VPS. The tab says "the VPS host runs an older build; run `sudo sew-update`" and offers only reading until then.

---

## 7. Summary

- **Objective:** see and control the VPS bots from a desktop tab that is the Bots tab itself on a remote backend, over a configurable connection, with the host's own checks and audit.
- **Scope:** one host at a time; every Bots tab view and action; no VPS administration, no backtest on the VPS, no open port.
- **Constraints:** real money; no inbound port by default; host is the single writer; new dependencies and any Engine change need the owner's approval; each concern in its layer.
- **Acceptance:** AC1–AC9 (§6.1).
- **Decisions:** §4, G1–G9 (G1, G6 and G7 are provisional until De-risk). Open assumptions: A1, A6, A7.
- **Assumptions:** §5.2.

**Next step:** De-risk (`DERISK.md`): run experiments R1–R7 from Discover §8 to confirm or overturn the provisional decisions; then the decision records, the preparatory epic (G9) and EPIC-047's own scaffolding.

---

## 8. Approval

Approval of the scope (§3, §4) and the constraints (§5), to proceed to Discover and De-risk (not to build, not a choice of solution).

| Name | Role | Decision | Date |
|------|------|----------|------|
| Nathan Tran | Owner | TODO | TODO |
