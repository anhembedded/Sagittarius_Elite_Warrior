Status: Current

# SPEC-018 — Add a bot designed on the desktop to the VPS, and read the VPS from the desktop

- **Status:** 🟡 built and proven on a fake host over the real bridge; the owner has not seen it on the real VPS. Not built: showing what is armed on the host (the host publishes no such fact), the masked account tail on the host line (a decision about a secret, left to the owner), a second host at once.
- **Actor:** trader, operator (the owner, at the desktop)
- **Origin:** `EPIC-047` charter, Scenario 2 and objectives O1–O5, and the decision of 2026-10-27 that the VPS tab touches nothing at Binance.
- **Surfaces:** the Bots tab (Bots → Add to VPS host…), the VPS Bots tab (list, detail, chart, every lifecycle command, Arm and Disarm strategy), Tools → Options → VPS Link.

## 1. Trigger
*"I designed and backtested this bot here. I want it on the VPS as a DRAFT, and I want to run it from the desktop without copying a file."*

## 2. Preconditions
- A VPS connection profile is chosen in Tools → Options → VPS Link, and this desktop and the VPS host run the same build.
- The host runs `sew` with its bridge (`Docs/OPERATIONS/`), so the link can connect.
- A bot is selected in the Bots tab.

## 3. Main flow
1. The actor selects the bot in the Bots tab and chooses Bots → Add to VPS host…
2. The app asks "Add <bot> to the VPS host?" with the verbs Add to VPS and Cancel, Cancel the default, and says that nothing starts and no order is placed.
3. The app sends the bot's name, kind, venue, symbol and parameters to the host as the `add` verb, once, connecting the link first if the VPS tab was never opened.
4. The host's own gate creates the bot as a DRAFT and the app tells the host's words in the status line and a toast.
5. The actor opens the VPS Bots tab: the bot is in its list with the host's own Checks, run against the host's account.
6. The actor presses Start there; for a mainnet venue the tab asks the actor to type the venue's word, and the host judges it.

## 4. What must be true afterwards
- The host holds one new bot in DRAFT with the same definition; nothing ran and no order was placed.
- The host's audit holds the `add` command with its request id.
- The VPS tab made no connection to Binance, signed or public, at any step.

## 5. When it goes wrong
| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| The link is not up yet (first use, or a cut) | "Not connected to the host: nothing was sent." as a failure notice | the control door answers `NOT_RUNNING` before anything is written |
| The host refuses (a name already taken, an unknown kind, a venue it does not trade) | The host's own sentence | the host judges the entry again after the wire and the app adds no rule |
| The host took the command and no reply came in time | "…may or may not have been created there. Read the VPS Bots tab before sending it again." | the host may have created it, so it is never told as a failure to create, and nothing is sent again |
| The bot was deleted while the question was open | "That bot no longer exists here, so nothing was sent." | the bot is read after the question, by id |
| A build difference | The VPS tab's line reads "the VPS host runs build X, this desktop runs Y: run `sudo sew-update`" and nothing is read or sent | the handshake refuses a link of another build for good |
| Add to VPS host… in the VPS tab | Off, with "Add to VPS is done from the Bots tab: this tab already shows the host's bots." | the VPS tab reads no symbol list from the exchange (decision D6) |

## 6. What this use case does NOT promise
- That the bot starts, or that it passes the host's Checks: they run on the host and are read in the VPS tab.
- That the same bot is not added twice under another name: the host refuses only a name already taken.
- That a command lost with the link ran: the app asks the host what it recorded and never re-sends (`Docs/MODULES/bots/06-runtime.md`, "After a cut").
- That the VPS tab shows what strategy is armed on the host.

## 7. Ports and modules it exercises
`bots`: `AddBotToVpsCommand`, `IVpsDelivery`, `IVpsTab`, `IHostWorld`; `core`: `HostControlRequest`, `IHostControl`; the shell's `VpsTabSession`.

## 8. Proven by
| Evidence | Where | Tier |
| :--- | :--- | :--- |
| The question, one request, the host's words, a cancel, a refusal, no link, a reply that never came, a second press, off in the VPS tab | `tests/unit/modules/bots/ui/bots_screen/test_bots_add_to_vps.py` | unit |
| The host's door receives the entry as an `add` over the real bridge; a vanished bot and a link not up send nothing; one shared session | `tests/unit/shell/vps_link/test_add_to_vps_reaches_the_host_as_a_draft.py` | unit |
| A host of another build is refused and the line says what to run | `tests/unit/shell/vps_link/test_a_host_of_another_build_is_told_on_the_line.py` | unit |
| The VPS tab is the Bots screen's classes on the host | `tests/unit/shell/vps_link/test_the_vps_screen_is_the_bots_screen_on_the_host.py` | unit |
| A lost command is settled from the host's record, never re-run | `tests/unit/shell/vps_link/test_a_lost_command_is_settled_from_the_hosts_record.py` | unit |
| The VPS tab opens no connection to the exchange | `tests/unit/shell/vps_link/test_the_vps_tab_opens_no_connection_to_the_exchange.py` | unit |
| **The user runs it:** with a real host, add a bot from the Bots tab, open the VPS tab and see it in DRAFT with the host's Checks, then Start it on a testnet | — | manual |
