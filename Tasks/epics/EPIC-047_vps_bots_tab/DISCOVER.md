# Discover — EPIC-047 VPS Bots tab

| Field | Value |
|-------|-------|
| Document type | Discover (step 2): system survey before any technical decision |
| Epic | EPIC-047 — a desktop tab that shows and controls the bots on the VPS host |
| Version | 0.2 (Draft) |
| Status | For the owner's review; **no solution is chosen here** |
| Inputs | `CHARTER.md` v0.3 · code read at `origin/master-warrior` d58e705 (cited by path → symbol) · the Engine at the `engine.ref` pin f4ef582 (read-only) · public documentation of six comparable systems (§6) |
| Next step | De-risk (step 3): prove the riskiest unknowns in §8 before the decision record |

**The question this survey answers:** *which parts of the system must be understood to choose correctly where the remote link cuts in (G6), how it is carried (G1, G7), and whether the Engine changes (G8)?*

---

## 1. Layer 1 — Context: where does the problem live?

```
 Owner's desktop (Windows, PySide6)                 VPS (Ubuntu, systemd)
 ┌──────────────────────────────────┐                ┌──────────────────────────────────────┐
 │ main.py (desktop)                │                │ sew-run.service: main.py run          │
 │  Bots tab ── its own bots         │                │  bots of the VPS (mainnet + testnet)  │
 │  own data root, own exchange keys │                │  own data root /var/lib/sew, own keys │
 └──────────────────────────────────┘                │  state/control/  (command inbox)       │
                                                     │  M bot …  (CLI, a second process)      │
                                                     └──────────────────────────────────────┘
                  today's only bridge: SSH login + text commands, scp of plan files
```

| Fact | Evidence |
| :--- | :--- |
| The two machines are separate installations, each with its own data root, its own keys and, in practice, **different exchange accounts** | the 2026-10-22 investigation (desktop key on another testnet account) |
| The host runs as the `sew` account, `Type=notify`, and **opens no port**; an existing test names it | `deploy/linux/sew-run.service`; EPIC-038J acceptance test `test_a_second_process_stops_a_bot_on_the_running_host_and_the_host_listens_on_no_port` |
| Control of the host today: a **command directory** (owner-only, 0700), files renamed atomically, polled every 1 s, answered through an append-only audit | `src/modules/operations/adapters/directory_host_control.py` → `DirectoryHostControl`; `hosted_control_poller.py` → `HostedControlPoller`; `jsonl_host_control_audit.py` → `JsonlHostControlAudit` |
| Read-only CLI (`bot list`, `bot show`) does **not** ask the host: a second, read-only copy of the app reads the bot files itself | `src/modules/bots/cli/bot_verbs.py` → `ListBotsVerb`, `ShowBotVerb`; `bots/composition/state_bindings.py` (`ReadOnlyBotStore`) |
| Earlier owner decisions on this boundary: a local socket was **not chosen** for host control (EPIC-038 O4 → §4b, channel C); remote control from Discord must be **outbound only**, behind one gate with an allowlist, request ids and audit (EPIC-036F D1–D7, not built) | `Tasks/epics/EPIC-038_headless_operation/DECISION_2026-10-09_headless_operation.md`; `Tasks/epics/EPIC-036_alerting_module/DECISION_2026-10-21_remote_control_from_discord.md` |

**Impact analysis at this layer.** Anything that makes the host *listen* (even on 127.0.0.1) reverses part of EPIC-038's decision and breaks the existing "listens on no port" test; it needs the owner's explicit decision, not a side effect.

---

## 2. Layer 2 — Architecture: how is the Bots tab organised?

### 2.1 How the screen is built
- `src/modules/bots/ui/bots_screen/bots_screen.py` → `bots_screen()` contributes the route; `src/presentation/ui/main_window.py` → `MainWindow._add_modes` builds `presenter_class(view, container)`.
- The presenter receives **only the DI container**; it resolves its ports once in `bots_dependencies.py` → `bots_dependencies_for` (`BotsDependencies`).

### 2.2 The ports the Bots tab really uses (the size of the seam)

| Port (`BotsDependencies`) | What the tab does with it | Remote implication |
| :--- | :--- | :--- |
| `commands: ICommandDispatcher` | **all queries and commands** (`ListBotsQuery`, `GetExchangeFactsQuery`, `PauseBotCommand`, …) | the natural cut point — but not the only port |
| `venues: IVenueTradingPorts`, `contexts: IVenueContexts` | venue choices, **key lookup on the UI thread** (`venue_choice.py` → `_connection_of`) | must answer about the *VPS's* venues and keys, never the desktop's |
| `run_facts: BotRunFactsReader` | in-process facts (trading session leases, enabled venues, budget caps), **synchronous on the UI thread** (`selected_bot.py` → `SelectedBot.detail`) | cannot stay in-process: it describes the host |
| `feeds`, `ticks` (`BotTickFeed`) | chart candles and live ticks | candles could come from the desktop's own store; live ticks are public market data |
| `filters`, `symbols` | precision filters, symbol picker | public exchange metadata; can stay local |
| `workbench_ports` | backtest workbench | stays local (charter: backtest on the desktop) |
| `consent: IRealMoneyConsent`, `instance: IInstanceAccess`, `notifier`, `threads`, `display_timezone` | UI concerns | stay local |
| event bus (`BotChangesFeed`, `ArmedStrategyChangedEvent`) | `BotChangedEvent` → re-read the list | needs an event stream from the host |
| `BotLogFeed` | a log handler on the `App.Bots` logger | needs the host's log lines (G4) |

**Finding A.** The tab does not consume a single query for its detail: **readiness, the ladder and the earnings are computed in the presenter** from six reads (`BotSnapshot`, `PlannerMarket`, `VenueSnapshot`, `ConnectionRead`, `RunFacts`, `PlanRiskRead`) through pure functions (`bot_detail.py` → `detail_for`). `GetBotReadinessQuery` and `GetBotStatusReportQuery` exist but the tab does not use them.

**Finding B.** "Swap the dispatcher and the bus" covers the commands and most reads, but **at least four dependencies are not behind the dispatcher** and describe the host: `run_facts`, `contexts` (key lookup), `venues` (venue choices) and the log feed.

**Finding E — the root cause of A and B: no rule says through which doors the UI reaches the application.**
1. **The presenter receives the whole DI container.** `src/support/ui_kit/registry/models/screen_descriptor.py` fixes the presenter's signature as `(BaseView, IContainer)`, so a presenter can resolve any port (the *Service Locator* anti-pattern), and `bots_dependencies.py` → `bots_dependencies_for` does.
2. **The layer rules only forbid outward imports.** `tests/unit/architecture/test_module_layers_point_inward.py` allows `ui → application`, because it points inward. So `bots_dependencies.py` imports an application service directly (`application/services/readiness/bot_run_facts.py` → `BotRunFactsReader`) and behavioural ports of another module (`trading/contracts` → `IVenueContexts`, `IVenueTradingPorts`). No rule is broken; none forbids it either.
3. **Business computation sits in the presenter.** Readiness, the ladder and the earnings are computed in `bot_detail.py` → `detail_for` from six reads, instead of the UI receiving a read model built by the application layer.
4. **The Engine does not encode it.** `BasePresenter` (`extensions/pyside_mvc`) has no notion of "only the dispatcher and the bus", so nothing reminds whoever writes a screen.

Consequence: a remote backend cannot be plugged in by swapping the dispatcher and the bus alone, and the same gap can exist on every screen, not only Bots. Owner's reading (2026-10-24): this needs to be standardised, because code written without the rule does not know that data must go through the dispatcher or an event.

### 2.3 How the host is organised for control
- Port: `src/core/contracts/i_host_control.py` → `IHostControl.send(request, wait_s) -> HostControlReply`. Its docstring already names the extension case: *"a different transport (a socket, a chat bot) – another `IHostControl`"*.
- Gate on the host: `operations/application/host_command_processor.py` → `HostCommandProcessor` (unauthorised → malformed → replayed → expired → RECEIVED → execute → verdict), then `bot_host_command_executor.py` → `BotHostCommandExecutor` maps each action to a `*ForHost` command of the bots module (`bots/contracts/host_bot_requests.py`).
- Verb allowlist: the closed `HostControlAction` set (14 actions) and `host_command_rules.py` → `action_problem`.
- **Real-money confirmation is not at the gate**: it is judged inside the bots `*ForHost` handlers (for example `start_bot_for_host/handler.py` → `StartBotForHostCommandHandler`, refusal `REAL_MONEY_NOT_CONFIRMED`).
- Parity: `tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py` already proves every Bots tab command has a host verb.

### 2.4 What the Engine offers (pin f4ef582, read-only)
| Facility | Relevance |
| :--- | :--- |
| `IEventBus` (in-process), `IDispatcher`, `IThreadManager`, `ITaskManager` (asyncio task pool), `Scheduler`, `IHostedService` | in-process only; no remote dispatcher, no bus bridge |
| `extensions/audit/infra/trace_server.py` → a threaded asyncio **WebSocket server** (`websockets`): refuses an off-loopback bind without a token, token check with close code 4401, backlog then live frames | **a precedent inside the Engine** for a loopback WebSocket with a token and a version handshake — but it streams trace records only, no commands |
| `extensions/audit/contracts.py` → "Trace protocol" `Envelope`, `MessageType`, `PROTOCOL_VERSION = 2`, secret redaction | a precedent for a versioned, stdlib-only JSON envelope |
| `tools/state_console` (`sagittarius-console`) → a **PySide6 client** attaching to a running `TraceServer` | a precedent for a Qt desktop client attached to a running process |
| `BaseEvent.to_dict()` | shallow, **not JSON-safe** (Decimal, enums stay objects), no `from_dict` |

---

## 3. Layer 3 — Implementation: trace one flow end to end

**Flow chosen:** *Pause a bot.* It is the smallest command that crosses every layer, and it exists on both paths today.

### 3.1 Pause in the Bots tab (in-process)
1. Action `Pause` (`bots_commands.py` → `_LIFECYCLE`) → `BotsPresenter._on_action` → `command_for(PAUSE)` = `PauseBotCommand(bot_id)`; FSM → `ACTION_IN_FLIGHT`.
2. `BotActionsCoordinator.send` → thread pool → `ICommandDispatcher.dispatch` → `EngineCommandDispatcher` → engine `IDispatcher`.
3. `PauseBotCommandHandler` → `BotCommandGate.run` (lookup, declared transition, read-only refusal) → `BotRunner.pause` → `GridExecutor.pause` → **posted to the bot's own worker; the command returns "accepted" before the bot is PAUSED.**
4. On the worker: `BotRunState.transition` → `IBotStore.save` → `NotifyingBotStore` publishes `BotChangedEvent` (from the worker thread).
5. Back to the screen by **two paths**: (a) the command's answer → `_on_finished` → status line and re-reads; (b) `BotChangedEvent` → `QtEventBridge` → 150 ms coalescing → `ListBotsQuery` → model refresh.
6. Errors: a refusal is a value (`BotCommandResult`), an exception becomes text at the worker boundary (`failure_detail`), reads fail into the message bar (`BotsFailures`).

### 3.2 Pause on the VPS (`M bot pause <id>`)
1. `sudo -u sew` (`deploy/linux/sew-profile.sh`) → `PauseBotVerb` builds `HostControlRequest(PAUSE, bot_id)` → `IHostControl.send`.
2. `DirectoryHostControl`: host running? → write `cmd-<id>.json` (0600, atomic rename) → poll the audit every 0.1 s → withdraw on timeout if the host has not claimed it.
3. Host: `HostedControlPoller` (every 1 s) → `HostCommandProcessor` gate → `BotHostCommandExecutor` → `PauseBotForHostCommand` → **the same `PauseBotCommand`** → from here identical to 3.1 step 3–4.
4. Verdict appended to `audit.jsonl` → the CLI maps it to an exit code.

### 3.3 What the trace shows
| Question | Answer |
| :--- | :--- |
| Where does the command come from? | a presenter action (tab) or a CLI verb (host) |
| Who validates it? | the bots `BotCommandGate` in both; the host adds the control gate (authorisation by file ownership, allowlist, replay, expiry, audit) |
| Where is the business logic? | the same handler and executor in both paths |
| Who owns the data? | the process that holds the data root's lock; **one writer** |
| How do errors travel? | values for refusals, text at the thread boundary; the host adds verdicts in the audit |
| Where does the result go? | tab: its own bus and re-reads; host: the audit file only — **the host has no channel that pushes changes to another process today** |

**Finding C.** Commands already have a remote-ready path with a gate and an audit (`IHostControl` + `HostCommandProcessor`); only the *transport* (a local directory) is local. **Reads and events have no remote path at all**: the CLI cheats by being a read-only copy on the same disk.

---

## 4. Layer 4 — Build and verification: how would we know it works?

| What exists | Evidence |
| :--- | :--- |
| Parity guard: tab commands ↔ host verbs | `tests/unit/architecture/test_the_bots_tab_and_the_host_stay_in_step.py` |
| Host control tests on a pumped poller (no real sleeps) | `DirectoryHostControl` injects `sleep` and `monotonic` |
| "Host listens on no port" test | EPIC-038J |
| Desktop end-to-end tests are opt-in, never offscreen | `ci-rule.md` §2 |
| Integration tests run the real composition with a fake exchange | `tests/integration/…` |

**Gaps for this epic:** no test harness for two processes over a network link; no contract test for wire forms (most types have none, §5); no way today to prove "the remote tab shows the same facts as `bot show`" except by hand.

---

## 5. Serialisation inventory (what can cross a wire today)

| Has a wire form (both ways) | One-way only | None |
| :--- | :--- | :--- |
| `HostCommand` (`host_command_codec.py`, schema `sew.host-command/1`, ≤ 4096 bytes); `ControlAuditEntry`; `HealthSnapshot`; the stored bot record (`bot_record_codec.py` + `grid_runtime_codec.py`); `BotPlanDocument` | `BotStatusReport.payload` (+ `RunEarnings` inside), `ladder_payload` (keys pinned by a test), `LossCapStatus.payload`, `BaseEvent.to_dict` (not JSON-safe) | `BotSnapshot`, `BotProgress`, `BotReadiness`, `VenueSnapshot`/`ExchangeFacts`, `BotCommandResult`, `BotList`, `BotFills`, `PlannerMarket`, `PlanRiskRead`, `VenueAccountSnapshot`, `ConnectFailure`, `RunFacts`, `HostControlRequest`/`Reply` |

**Finding D.** A cut at the dispatcher and bus needs **wire forms for about fifteen types**, and they must stay in step with the Python types (a contract test per type). A cut at a *report* level (what `bot show --json` already emits) needs far fewer, but the tab would then render reports instead of computing its detail.

---

## 6. How others solve it (external survey)

| System | Shape | Transport and security | What it teaches us |
| :--- | :--- | :--- | :--- |
| **Freqtrade** (crypto trading bot) | REST API + a message WebSocket (`/api/v1/message/ws`, client sends `{"type":"subscribe","data":[…]}`) + a web UI (FreqUI) | listens on **127.0.0.1 by default**; docs: *"We strongly recommend to not expose this API to the internet"*; on a VPS use **an SSH tunnel or a VPN (OpenVPN, WireGuard)**; JWT with 15-min access tokens, a separate `ws_token` | the closest peer: a *server inside the bot*, loopback only, reached by tunnel; commands by request/response, updates by a subscribed stream |
| **Hummingbot** | bots are **MQTT clients** of a broker (EMQX/RabbitMQ); commands (start, stop, import, config, balance) and status, heartbeat, PnL over topics; newer "Hummingbot API" = FastAPI + broker | outbound connections from the bot to the broker; the broker is the single meeting point | the *outbound-only* shape: the bot never listens; at the cost of running a broker |
| **Docker CLI ↔ daemon** | the daemon's HTTP API on a local Unix socket; `DOCKER_HOST=ssh://user@host` makes the CLI run `ssh … docker system dial-stdio`, which bridges stdio to the socket | SSH key auth; the daemon never listens on TCP; docker-py offers **both** a paramiko transport and `use_ssh_client=True` (shell out to the system `ssh`), and users hit key-handling gaps in the paramiko path | proof that "local socket + SSH stdio bridge" works at scale; the system-ssh vs library trade-off is real in both directions |
| **VS Code Remote-SSH** | installs a **VS Code Server** on the remote host; the local window is "just a UI" | over SSH | a full desktop UI driven by a remote server: the UI stays local, the logic runs remotely |
| **Home Assistant WebSocket API** | auth handshake (`auth_required` → token → `auth_ok`), then every command carries an **`id` echoed in its result**; `subscribe_events` streams events tagged with the subscription's id | token auth; usually behind a VPN or a reverse proxy | a clean, documented protocol shape: handshake, correlation ids, results with `success`/`error`, subscriptions |
| **Qt Remote Objects** (in PySide6) | a *source* object in one process, *replicas* in others; properties, signals and slots cross automatically; `local:` (QLocalSocket) or `tcp://` URLs; types declared in `.rep` files | no built-in auth or TLS (must be tunnelled) | a Qt-native "remote presenter"; ties the host to Qt types, while the host is headless and Qt-free today |
| Cross-process **CQRS bridges** (NestJS + KubeMQ bridge, Mocha for .NET, abxbus bridges) | the in-process command/query/event buses keep their API; a bridge swaps in a transport and routes by message type | broker or transport of choice | the pattern the owner described ("send the command into the bus"): **keep the bus API, plug a transport** |
| Protocols: **WAMP** vs **JSON-RPC 2.0** | WAMP = RPC + Pub/Sub in one routed protocol over WebSocket; JSON-RPC = request/response format only, pub/sub left to the application | — | if commands *and* events must cross, either a WAMP-like protocol or JSON-RPC + an explicit subscribe message (as Home Assistant and Freqtrade do) |
| **Tailscale/WireGuard** for admin endpoints | bind the service to loopback and publish it to the tailnet only (Serve), never to the Internet (Funnel) | network-level identity, ACLs | a "VPN" protocol option keeps the no-Internet-port rule |
| **Cautionary case: OctoBot** | a web interface on the bot; **CVE-2021-36711**, remote code execution, CVSS 9.8, no privileges needed | exposed web UIs | why "no Internet-facing port by default" is the right default for a trading host |

**Common pattern across the peers:** *a small server or bridge next to the bot, reachable only locally, carried to the operator by SSH or a VPN; request/response for commands with a correlation id; a subscribed stream for changes; a version or auth handshake first.* The peers that differ (Hummingbot) do so to make the bot **outbound-only**, paying with a broker.

---

## 7. Must understand / Need to know / Out of scope

| Topic | Category | Why |
| :--- | :--- | :--- |
| `BotsDependencies` and which reads are synchronous (Finding A, B) | 🔴 Must | decides where the seam is and how big |
| `IHostControl` → `HostCommandProcessor` → `BotHostCommandExecutor` gate and audit | 🔴 Must | remote commands must keep exactly these checks |
| Where real-money confirmation is judged (`*ForHost` handlers) | 🔴 Must | must hold for every remote start/resume |
| The "no port" decisions (EPIC-038 D5/O4, EPIC-036F D3) and the existing test | 🔴 Must | a design that listens reverses them |
| Serialisation of the ~15 contract types (Finding D) | 🔴 Must | cost and drift risk of the cut |
| The UI's doors into the application (Finding E): container injection, the layer guard, where readiness is computed | 🔴 Must | the root cause; decides whether a preparatory standardisation comes first |
| Event flow (`NotifyingBotStore` → `BotChangedEvent` → coalesced re-read) | 🔴 Must | the remote tab needs the same freshness |
| SSH port forwarding / stdio bridging, and one SSH library's API (`asyncssh` or `paramiko`) | 🔴 Must | the transport the owner leans to |
| WebSocket basics, correlation ids, subscribe/resubscribe on reconnect | 🔴 Must | the protocol shape every peer uses |
| Engine `TraceServer`, `Envelope`, `PROTOCOL_VERSION`, `sagittarius-console` | 🟡 Need to know | precedent and possible reuse if G8 moves work into the Engine |
| Qt Remote Objects | 🟡 Need to know | an alternative for a Qt-to-Qt link; the host is Qt-free |
| WAMP, JSON-RPC 2.0, MQTT | 🟡 Need to know | protocol options to compare in De-risk |
| Tailscale/WireGuard setup | 🟡 Need to know | a second transport option (G7) |
| docker-py's paramiko vs system-ssh history | 🟡 Need to know | evidence for G1 |
| gRPC/protobuf, Kafka, cloud brokers | ⚪ Out of scope | heavier than one owner and one or two hosts need |
| Multi-user auth, roles, web or mobile UI | ⚪ Out of scope | charter §4 |
| Backtest on the VPS, VPS administration | ⚪ Out of scope | charter §4 |

---

## 8. What Discover changes, and the unknowns for De-risk

**Facts that reshape the open questions (no decision taken):**
1. **G6 (layer).** "Swap the dispatcher and the bus" is necessary but **not sufficient**: four host-describing dependencies sit outside the dispatcher (Finding B), and the tab computes its detail locally (Finding A). Whatever the cut, those must move behind it.
2. **Commands vs reads are asymmetric.** Commands already have a gated, audited, remote-ready port (`IHostControl`, Finding C); reads and events have none.
3. **The Engine already has a precedent** (`TraceServer` + `Envelope` + a PySide6 client) for a loopback WebSocket with a token and a version handshake (G8).
4. **Any listener reverses a recorded decision** (EPIC-038) and an existing test; an outbound-only or stdio-bridged design does not (Layer 1).
5. **Wire forms are the hidden cost**: about fifteen types today have none (Finding D).
6. **The root cause is a missing rule, not one screen** (Finding E). The owner agreed (2026-10-24) to standardise it: the UI reaches the application only through the command dispatcher (queries and commands) and bus events (through Feeds), plus an allowlist of UI-only ports (notifier, real-money consent, thread pool, display preferences); contract *data* types may be imported, behavioural ports of the application or of another module may not. Proposed order, to be decided in that standardisation's own record: (B) a rule and a guard test with a baseline that only shrinks; (D) read models built by queries instead of computation in presenters; (C) presenters receive a narrow application gateway instead of the container; (E) the same rule in the Engine later. Charter G9 asks whether it is part of EPIC-047 or a separate epic done first.

**Unknowns to prove in De-risk (riskiest first):**
| ID | Unknown | Smallest experiment |
| :-- | :--- | :--- |
| R1 | Can the Bots tab run with **every** host-describing read behind one seam without changing what it shows? | list the seam's methods from `BotsDependencies`; build a fake remote backend in a test and render one bot |
| R2 | Can a link reach the host **without the host listening** on any socket (stdio bridge like Docker's, or an outbound connection)? | an `ssh … main.py <bridge>` stdio round trip on the owner's VPS with a dummy message |
| R3 | `asyncssh` vs `paramiko` vs system `ssh` on the owner's Windows: key from file and from agent (Pageant / OpenSSH agent), host-key pinning, reconnect | a 50-line spike per option, run on the owner's desktop |
| R4 | Wire forms: generate or hand-write for ~15 types, and keep them in step | one type end to end with a round-trip contract test; measure the effort |
| R5 | Freshness: can the host push `BotChangedEvent` to a remote client with ≤ 5 s latency (AC2), and recover after a reconnect without missing a change? | subscribe → change → reconnect → snapshot-then-subscribe |
| R6 | Version mismatch handling | handshake with app version and a contract hash |
| R7 | How large is the "UI bypasses the dispatcher and the bus" debt on **every** screen (Finding E)? | a read-only scan of `src/modules/*/ui/**` imports: application services, adapters, behavioural `I*` ports outside an allowlist of UI-only ports; one count per screen |

**Next step:** De-risk (step 3) runs R1–R7 as throwaway spikes and measurements, then the decision records choose G1, G6, G7, G8 and G9 with the evidence.

---

## Sources
- Martin Fowler, *Inversion of Control Containers and the Dependency Injection pattern* (Service Locator vs Dependency Injection): <https://martinfowler.com/articles/injection.html>
- Ford, Parsons, Kua, *Building Evolutionary Architectures* (architecture fitness functions)
- Freqtrade REST API and message WebSocket: <https://github.com/freqtrade/freqtrade/blob/develop/docs/rest-api.md>
- Hummingbot remote control broker: <https://hummingbot.org/installation/broker/> · <https://hummingbot.org/hummingbot-api/> · <https://github.com/hummingbot/hbot-remote-client-py>
- Docker over SSH: <https://www.tigera.io/?p=8312> · docker-py `DockerClient(use_ssh_client=…)`: <https://docker-py.readthedocs.io/en/7.1.0/client.html> · paramiko key handling issue: <https://github.com/docker/docker-py/issues/2416>
- VS Code Remote-SSH and VS Code Server: <https://code.visualstudio.com/docs/remote/ssh> · <https://code.visualstudio.com/docs/remote/vscode-server.md>
- Home Assistant WebSocket API: <https://developers.home-assistant.io/docs/api/websocket>
- Qt Remote Objects nodes: <https://doc.qt.io/qt-6/qtremoteobjects-node.html> · PySide6 example: <https://doc.qt.io/qtforpython-6/overviews/remoteobjects-example-static-source.html>
- CQRS bridges: <https://docs.kubemq.io/integrations/nestjs/concepts/cqrs-bridge> · <https://chillicream.com/docs/mocha> · <https://abxbus.archivebox.io/integrations/bridges.md>
- WAMP compared: <https://wamp-proto.org/comparison.html>
- AsyncSSH (port forwarding, agents incl. Pageant): <https://pypi.org/project/asyncssh/> · Airflow's sync and async SSH tunnels: <https://airflow.apache.org/docs/apache-airflow-providers-ssh/stable/_api/airflow/providers/ssh/tunnel/index.html>
- Tailscale Serve vs Funnel pattern: <https://dashy.to/docs/authentication/tailscale> · <https://gardener.cloud/docs/guides/administer-shoots/tailscale/>
- OctoBot CVE-2021-36711: <https://cveawg.mitre.org/api/cve/CVE-2021-36711>
