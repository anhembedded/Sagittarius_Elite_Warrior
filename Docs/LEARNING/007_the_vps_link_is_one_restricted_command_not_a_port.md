Status: Current

# 007 — The VPS link is one restricted command, not a port

**Teaches:** how a desktop can watch and control a real-money host without the host listening on anything — forced commands, least privilege, and a protocol over standard input and output. **Decision:** [`DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md`](../../Tasks/epics/EPIC-047_vps_bots_tab/DECISION_2026-10-24_the_remote_link_is_a_bridge_behind_a_forced_command.md) (`EPIC-047`). This page teaches; the record decides; the steps are [`headless_runbook.md`](../OPERATIONS/headless_runbook.md) §14.

## 1. The problem
The owner's bots run on a VPS with real money. Reading one bot meant SSH, `M bot show`, `tar` and `scp`. A desktop tab should show them all, but every way to reach the host from a desktop seems to open a door: a port, a token, a second login.

## 2. Constraints
- The host listens on no socket (`EPIC-038`), and nothing may add one.
- The desktop's credential must not be able to do more than the tab needs: no shell, no forwarding.
- A command must pass the host's own gate and audit, exactly as `M bot …` does.
- A slow or frozen desktop must never slow the bots.

## 3. Solutions considered
| Option | Why it lost or won |
| :--- | :--- |
| Host opens a TCP or HTTP port | A new attack surface on a money host |
| A full SSH login and `M bot …` over a terminal | The key can do anything; text is parsed back into data |
| A VPN or TLS endpoint | More to run and secure than SSH already gives |
| **A key restricted to one command, the bridge, speaking JSON lines over SSH** | **Chosen:** SSH is already there and audited; `restrict,command=` is OpenSSH's own mechanism; no port |

## 4. The choice and why
`sshd` starts the bridge for the key, as `sew`, and the key can run nothing else whatever the client asks. The bridge is a second process that reads the host's files and hands commands to the host's control directory, so the host's gate decides. The bridge calls no exchange: the host fetches, the bridge reads.

## 5. How it is implemented
`deploy/linux/sew-bridge` execs `shell/link_bridge_main.py` → `main`; `support/wire/bridge/bridge_session.py` → `BridgeSession` speaks the protocol; the desktop side is `support/wire/desk/` with an `asyncssh` adapter. A version difference is refused at the handshake before any read.

## 6. Risks and failure modes
A wrong `authorized_keys` or `sshd_config` can lock the owner out, so the runbook orders the steps and keeps a session open. The `sew` account has the `nologin` shell by default and `sshd` runs the forced command through the shell, which the runbook handles and says is unproven until its owner run.

## 7. Limits
One host at a time, SSH only, same build on both sides. A host-side listener would be needed for a mobile client; that is another decision.

## 8. Names to know
Forced command, least privilege, capability restriction, stdio transport, handshake with a version check, read-only replica, idempotency key.

## 9. Interview questions
1. *Why not a REST API on the host?* A new listener on a money host, to authenticate and patch; SSH is already the audited door.
2. *What does `restrict` switch off?* Port, agent and X11 forwarding, and the pty; `command=` fixes what runs.
3. *Why a second process, not a thread in the host?* It cannot slow the bots and ends with its session.
4. *Why refuse on a version difference instead of degrading?* A silent mismatch on a money field is worse than a clear refusal.

## 10. Read more
`sshd(8)`, "AUTHORIZED_KEYS FILE FORMAT"; the Docker `dial-stdio` pattern for stdio transports.
