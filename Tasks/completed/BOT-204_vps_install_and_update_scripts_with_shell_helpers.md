# BOT-204 — A fresh VPS is set up by one script, upgraded by another, and the daily variables live in a shell profile

**Status:** ✅ Done (2026-10-20)
**Board:** `sudo deploy/linux/sew-install` sets a fresh Ubuntu VPS up (account, directories, venv, engine, unit, `sew-key`, `sew-backup`, the shell helpers) and stops before the first key; `sudo sew-update [ref]` is the runbook's upgrade in the order BOT-203 needs; `/etc/profile.d/sew.sh` gives the shell `M`, `sewlog`, `sewstatus`, `sewbots` ([decision](epics/EPIC-038_headless_operation/DECISION_2026-10-20_vps_install_and_update_scripts.md)).
**Source:** the owner, 2026-10-20, relayed by the coordinating session: *"a VPS install script: clone this repo, run the script, and the VPS is set up; also put the commonly used variables into bashrc"*. The coordinator's design (install, update, a profile in `/etc/profile.d`) was accepted by the owner.
**Risk:** 🟡 — root scripts that change `/etc` and stop a trading host. They never touch a key value, a credential file's content, `sew.env` or `user_config.json`; the real systemd is not provable in CI.
**Complexity:** M — three root-run shell scripts and a shared library, a profile, the backup moved out of the runbook, their tests and the runbook.
**Epic (optional):** [EPIC-038](epics/EPIC-038_headless_operation/README.md)
**SPEC (optional):** [SPEC-015](../Docs/SPEC/SPEC-015_run_the_bots_headless.md)
**Depends on:** None (builds on `BOT-200` `sew-key` and `BOT-203`, PR 611, the one-line `LoadCredential=` unit).

---

## 1. Context and problem
Setting a VPS up is runbook §2: a dozen `sudo` commands typed from a page, then §3, §3b and §8b's pasted `sew-backup` heredoc. Upgrading is §8's six steps, and the order is load-bearing since BOT-203: the new unit with the old code finds no key, so the unit may only be installed after the code. Every command to the host is typed as `sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python …/main.py`, held in a `$M` variable the runbook asks the reader to define in each shell, and `BOT-198` found the terminal width (`COLUMNS`) lost through that `sudo -u sew env` hop.

## 2. Acceptance criteria
- [x] `deploy/linux/sew-install` refuses (exit 2, every failed check listed) on a host that is not Ubuntu, has systemd older than 251, is not root, has less than 2 GiB free, or whose clock is not synchronised; `--skip-preflight` skips only those system checks.
- [x] On a fresh host it creates the `sew` account, `/opt/sew`, `/var/lib/sew`, `/etc/sew`, `/etc/sew/credentials` (root, 0700), the checkout (cloned when the script runs from another clone), the venv, installs `requirements-headless.txt` under `requirements.lock`, the pinned engine, compiles the checkout, creates an **empty** `/etc/sew/sew.env` (0640 root:sew), installs the unit and `daemon-reload`s, links `sew-key`, `sew-backup`, `sew-update`, `sew-install` into `/usr/local/sbin`, installs the backup service and timer and `/etc/profile.d/sew.sh`, enables `sew-run` and proves the app starts (`main.py status` exits 0, 10 or 11 as `sew`).
- [x] A second run is safe: nothing that exists is recreated; **a credential file, `sew.env` and `user_config.json` are never written when they exist**; a hand-written `/usr/local/sbin/sew-backup` is moved aside, not deleted.
- [x] It starts the service only with `--start`; without it, it prints the start command and says why (no key yet, so the start would end in exit 5, a code the unit never restarts).
- [x] It prints the next steps: `sudo sew-key add`, the Discord webhook (§3) and the dead man's switch (§3b), the loss cap (§6), the pre-flight (§4), the start, the resume of RECOVERING bots.
- [x] `--dry-run` changes nothing and prints each action; every script is `set -euo pipefail`, uses the exit-code vocabulary of `exit_codes.md` (0 done, 1 a command failed, 2 a refusal it designed) and is shellcheck-clean.
- [x] `sew-update [ref]` does §8 in this order: stop (only if running; refuses to go on if the host did not drain), copy `state/` aside and take `sew-backup`, fetch and check out the ref (default `origin/master-warrior`), `pip install`, the engine pin, `compileall`, **then** the regenerated unit and `daemon-reload`, then the check that `systemctl cat sew-run` shows exactly one active `LoadCredential=sew:/etc/sew/credentials`, then the start (only if the host was running before) and the `[preflight]` lines. A failed check leaves the host stopped and says so. It never resumes a bot.
- [x] A ref that would overwrite a hand-edited tracked file (`src/config/user_config.json`) is refused **before** the host is stopped.
- [x] `/etc/profile.d/sew.sh` is written by both scripts, byte-identical to `deploy/linux/sew-profile.sh`, and defines (POSIX sh) `M`, `sewlog`, `sewstatus`, `sewbots`, `sewproblems`, `sewhelp`; `M` works from a login user, from root and from `sew`, and carries `COLUMNS`, `TERM` and `NO_COLOR` through `sudo -u sew env`.
- [x] `sew-backup` and its timer units are real files in `deploy/linux/`; runbook §2 and §8 lead with the scripts and keep the manual commands as the fallback; §8b points at the file.

## 3. Design
**Agent decisions, delegated by the owner (he may veto):** [`DECISION_2026-10-20_vps_install_and_update_scripts.md`](epics/EPIC-038_headless_operation/DECISION_2026-10-20_vps_install_and_update_scripts.md).

- One shared library, `deploy/linux/sew-lib.sh`, sourced by `sew-install` and `sew-update`, holds what both do (the unit, the profile, the links, the pip/engine/compileall triple, the `LoadCredential` check), so the order BOT-203 requires is written once. `sew-key` is untouched.
- The pattern is the runbook's own commands wrapped in checks: `install -d`, `ln -sfn`, `cmp` before copying, `git fetch` + `checkout --detach`. Nothing is invented (CONSTITUTION P5).
- The `LoadCredential` check is anchored (`^LoadCredential=`): the runbook's `grep LoadCredential` also prints the unit's comment that mentions the word.
- Every script runs under `umask 022` (a pip install under root's `077` leaves a venv `sew` cannot read); secrets are written only by explicit `install -m`.
- Tests run the real scripts under bash against a temporary root (`SEW_DEPLOY_ROOT`) with stand-ins for `systemctl`, `useradd`, `apt-get`, the venv's python and `sudo`, a real local git origin, and `shellcheck`. The `SEW_DEPLOY_*` overrides are refused when the script is really root, as `sew-key` does for `SEW_KEY_*`.

## 3a. Reuse
`None: no UI or application need.` Reused: `sew-key`'s override/refusal pattern and its `World` test fixture ideas; `scripts/render_service_files.py`'s unit (copied, never edited); the runbook's commands for each step.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `deploy/linux/sew-lib.sh` | shared functions |
| `deploy/linux/sew-install` | the fresh-host script |
| `deploy/linux/sew-update` | the upgrade script |
| `deploy/linux/sew-profile.sh` | the content of `/etc/profile.d/sew.sh` |
| `deploy/linux/sew-backup`, `sew-backup.service`, `sew-backup.timer` | the runbook §8b heredocs as files |
| `Docs/OPERATIONS/headless_runbook.md` | §2, §3 (links), §6, §8, §8b lead with the scripts |
| `tests/unit/scripts/` | the proofs |
| `Tasks/…`, `Docs/…/DECISION_…` | this record |

## 5. Testing
Unit tier, no network (`ci-rule.md` §2): the real scripts under bash against a temporary root, `deploy_world.py` for the stand-ins.
- Host checks, refusals, usage, real-root refusal of the test overrides, shellcheck, strictness: `test_sew_install_refusals.py`.
- The fresh layout and modes, the unit / profile / links, the pip-under-lock call with `umask 0022`, no start without `--start`, the next steps text, the smoke check (`status` 0, 10, 11 pass, anything else exits 1), the second run (snapshot equal, a credential file, `sew.env` and `user_config.json` untouched), the tightened credentials directory, the hand-pasted `sew-backup` kept aside, `--dry-run` (snapshot equal, no mutating call), the running host (no pip, `--ref` refused), a drop-in resetting `LoadCredential=`, the unit's comment not counting as a second line, `--ref`, a release without the scripts, the apt venv package, running from inside the checkout, a directory in the way: `test_sew_install.py`.
- The order (stop, then the state copy and the archive, then checkout, pip, engine pin, compileall, **then** `daemon-reload` with the new unit, the check, the start), read from a log that stamps the checkout sha and the installed unit's hash at each step; the host not started when it was not running or with `--no-start`; refs (default `origin/master-warrior`, a tag, a sha, a bare branch meaning the remote); an unknown ref and a conflicting hand edit refused before the stop; a compatible hand edit kept; a host that did not drain; a failing start; a release without the scripts; dry run; not installed, not root; an older install adopted: `test_sew_update.py`.
- `M` (bash and dash), the width / `TERM` / `NO_COLOR` / `COLORTERM` passed through `sudo -u sew env`, no global `PYTHONPATH`, the exit status kept, no scratch variable left, no `sudo` as `sew`, `sewlog`, `sewproblems`, `sewbots`, `sewstatus`: `test_sew_profile.py`.
- `sew-backup`: the archive's members, modes and exclusions, the secrets absent, retention, root and layout refusals, the hot-copy warning, the timer units: `test_sew_backup.py`.
- Mutation checks done by hand, each turned a test red: dropping `COLUMNS` from `M`; `umask 077`; installing the system files before the checkout; recreating `sew.env` on a second run; the unanchored `grep LoadCredential` (the unit's own comment then counts); neutralising the hand-edit conflict check; stopping after the state copy instead of before.
- Not proven here: a real systemd (the order of `daemon-reload` and a `Type=notify` start), a real `useradd` and `chown` to `sew`, a real pip install and the apt packages, the exchange, a VPS. Stated in runbook §12 and the decision's D-table.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §2, §6, §8, §8b; `Docs/MODULES/`: none (no module code).

## Implementation notes (written when done)
- The `SEW_DEPLOY_*` overrides are refused when the script is really root, the `sew-key` pattern; a profile that exports `SEW_*` (it exports `SEW_HOME`, `SEW_DATA`, `SEW_CHECKOUT`) never trips it because the guard looks at `SEW_DEPLOY_` only.
- Found while writing the check: the runbook's `systemctl cat sew-run | grep LoadCredential` also matches the unit's own comment ("whose LoadCredential= names a file"), so it never printed exactly one line. The scripts anchor it (`^LoadCredential=`), the runbook's two manual commands and `test_headless_runbook.py` follow.
- A re-run on a running host must not touch the code: `sew-install` skips pip / engine / compile and refuses `--ref` there; `sew-update` is the way. Without that, a convenience re-run would have changed packages under a trading process.
- `src/config/user_config.json` is tracked and hand-edited on the server: the first design (a plain `git checkout`) would have failed after the stop when a release touched it. The updater now fetches, resolves and checks the overlap before it stops anything.
- A hand-pasted `/usr/local/sbin/sew-backup` (the runbook's old heredoc) is a regular file: `ln -sf` over it would have replaced it silently; it is moved aside with a timestamp instead.
- `sew-lib.sh` is `0644`, sourced, never run; the scripts are `0755`; the profile is `0644` and POSIX sh, shellchecked as `sh` and sourced under bash and dash in the tests.
- Verification: commit tier `ci-local.ps1 -SkipTests` PASS; `tests/unit/scripts` and `tests/unit/architecture` green locally; the full gate is the PR's `ci-local.ps1 -Full` run on its head (see the PR). Delivery state: PR open, not merged.
