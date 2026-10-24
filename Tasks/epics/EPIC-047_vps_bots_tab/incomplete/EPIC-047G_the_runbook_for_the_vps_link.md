# EPIC-047G — The runbook sets up the VPS link from a clean desktop: a key for `sew`, password login off, and what to do when it fails

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24; charter D6; De-risk §3.4 and §9 item 8: A1 was false (the owner had a password and no key until 2026-10-24), and the key was installed for root, not for `sew`.
**Risk:** 🟢 — documentation; a wrong step in `authorized_keys` or `sshd_config` can lock the owner out of the VPS, so the order of steps and the open session matter.
**Complexity:** S — one runbook section, one page of troubleshooting, one Learning page.
**Epic:** [EPIC-047](../README.md)
**Depends on:** [EPIC-047C](EPIC-047C_the_bridge_behind_a_forced_command.md) (the exact forced command and the bridge launcher), [EPIC-047D](EPIC-047D_the_desktop_transport_profiles_and_the_options_page.md) (the profile fields); the steps can be drafted earlier

---

## 1. Context and problem
`Docs/OPERATIONS/headless_runbook.md` covers the host. Nothing covers the desktop's link: the key, the account, the restriction, the profile. De-risk §3.4 holds the key setup that worked on the owner's Windows (`ssh-keygen -t ed25519`, installing the public half, the Windows `ssh-agent` service) and the hardening (`PasswordAuthentication no` in `/etc/ssh/sshd_config.d/50-sew-keys-only.conf`, `sshd -t` before the reload). §2.3 and §2.5 give the forced command and its checks.

## 2. Acceptance criteria
- [ ] The runbook section starts with the key setup for the **`sew`** account, never root: generate an ed25519 key with a passphrase asked by `ssh-keygen`, install only the public half in `sew`'s `authorized_keys` with `restrict,command="…"` naming the bridge (the line from 047C), and load the key into the agent (Windows: the `ssh-agent` service and `ssh-add`; Pageant).
- [ ] It then turns **`PasswordAuthentication no`** on: write the drop-in, run `sshd -t`, reload `ssh`, and keep the current session open until `ssh -o BatchMode=yes <login>@<vps> true` succeeds from the desktop with the key; the order is stated so a mistake cannot lock the owner out.
- [ ] It tells the owner to log in once and accept the host key so `known_hosts` holds it, and what the app does with a wrong key (047D).
- [ ] The three checks of De-risk R2 are in it as a verification the owner can run: the restricted key gets the bridge's `hello` for a shell request, "administratively prohibited" for a port forward, and a refusal for a terminal.
- [ ] A troubleshooting table maps each error the app shows (refused key, unknown or changed host key, host unreachable, version difference, bridge not started, data age growing) to its cause and its fix; the version difference says `sudo sew-update`.
- [ ] It names the facts file of 047B, the bridge's idle watchdog, and that `root`'s key stays the owner's administration key outside the app's profiles.
- [ ] It records the open items: the untested Windows agent path until 047D's run, the Unix socket variant as not built.
- [ ] A `Docs/LEARNING/` page explains the design (the doors, the bridge, the forced command, why no port), indexed in `Docs/LEARNING/README.md` (charter D6).
- [ ] A walk-through of the runbook on a clean desktop profile is recorded; the document guards pass.

## 3. Design
Documentation in the repository's register (`ONBOARDING.md` §10), in the existing runbook rather than a new copy of its host sections (P3). Commands are copied from De-risk §3.4 and the final 047C line, then run once before the task closes (P2: verify, don't restate).

## 3a. Reuse
`Docs/OPERATIONS/headless_runbook.md` and `deploy/linux/sew-profile.sh` (`_sew_as_service`): `used` for the host-side conventions. No UI or application need otherwise.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/OPERATIONS/headless_runbook.md` | the desktop-link section |
| `Docs/LEARNING/00x_….md` and `Docs/LEARNING/README.md` | the design page and its index row |
| `Docs/MODULES/…` | the wire protocol page, if 047A's notes call for one |

## 5. Testing
Documentation-only: the guards `python3 scripts/check_skill_prompt_references.py`, `tests/unit/test_task_board_is_consistent.py`, `tests/unit/architecture/test_claude_tree_is_wired.py` and any guard that reads `Docs/`. The walk-through is a manual check with its date. Not run.

## 6. Docs touched
Those listed in §4.

## Implementation notes (written when done)
Not written: not started.
