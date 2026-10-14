# Headless runbook: install, run, stop, upgrade and diagnose on a server

`EPIC-038H`. For a person who has a fresh Linux VPS (systemd) or a Windows server and wants the app to run the bots there with no window, as a service. Journey: [`SPEC-015`](../SPEC/SPEC-015_run_the_bots_headless.md) · exit codes: [`exit_codes.md`](exit_codes.md) · logs and the health line: [`LOGGING.md`](LOGGING.md).

## 0. Read this first: what is not supported yet

**This host is not supported for unattended money.** Until all three of these have merged, a bot that halts at 3 a.m. reaches nobody, and a host that dies reaches nobody either:

| Missing | What it leaves you without | Task |
| :--- | :--- | :--- |
| Alert sources | no bot event (halt, stop loss, fill) is sent to any channel | [`EPIC-036B`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036B_alert_sources.md) |
| Alert channel | no channel carries a bot event to you | [`EPIC-036C`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036C_discord_channel_and_telegram_migration.md) |
| Dead man's switch | nothing tells you the host stopped on its own | [`EPIC-036E`](../../Tasks/epics/EPIC-036_alerting_module/incomplete/EPIC-036E_heartbeat_dead_mans_switch_and_summary.md) |

Until then, use the host on a **testnet** venue. The host says so itself: every start writes the WARNING `no alert channel is configured for bot events; nothing will tell you if a bot halts`, and `--resume-recovering` refuses without `--i-accept-silent-failures`.

Also true today, whatever the alerts:

- **Stopping leaves resting orders on the exchange** (decision O1) and nothing watches a stop loss or take profit while the host is down, for a stop, a crash or an upgrade.
- **A bot a restart left RECOVERING stays so until a person resumes it** (decision O2), and a running host cannot be controlled (decision O4): resuming by hand means stopping the host and using the Bots tab of the desktop app on the same data root.
- The Windows steps and the checklist in §11 have **not been run on a machine** by their author. The Linux unit is checked mechanically (§12) but not yet run under a real systemd.

## 1. Layout this runbook assumes

| Thing | Linux | Windows |
| :--- | :--- | :--- |
| Checkout (the directory must be named `Sagittarius_Elite_Warrior`) | `/opt/sew/Sagittarius_Elite_Warrior` | `C:\sew\Sagittarius_Elite_Warrior` |
| Virtual environment | `/opt/sew/venv` | `C:\sew\venv` |
| Data root (`SEW_DATA_ROOT`: `state/`, `logs/`, the bots' files) | `/var/lib/sew` | `C:\ProgramData\sew` |
| Service account | `sew` (no login) | `NT SERVICE\sew-run` |
| Service | `sew-run.service` | `sew-run` |
| Secrets | `/etc/sew/` | the data root's `secrets\` |

The data root is outside the checkout so an update of the code never touches the bots, and the checkout can be read-only to the service.

## 2. Install on Linux

Needs systemd 247 or newer (`LoadCredential=` arrived in 247), Python 3.12 or newer (the floor; `preflight` checks it), `git`, and outbound HTTPS to the exchange. **No Qt and no display are needed**: the headless requirements install none of Qt's system libraries.

```bash
sudo useradd --system --home-dir /var/lib/sew --shell /usr/sbin/nologin --user-group sew
sudo install -d -o root -g root -m 0755 /opt/sew
sudo install -d -o sew -g sew -m 0700 /var/lib/sew
sudo install -d -o root -g sew -m 0750 /etc/sew /etc/sew/credentials

sudo git clone https://github.com/anhembedded/Sagittarius_Elite_Warrior.git /opt/sew/Sagittarius_Elite_Warrior
sudo python3.12 -m venv /opt/sew/venv
sudo /opt/sew/venv/bin/pip install -r /opt/sew/Sagittarius_Elite_Warrior/requirements-headless.txt \
    -c /opt/sew/Sagittarius_Elite_Warrior/requirements.lock
sudo /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/scripts/engine_pin.py install

sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/
sudo systemctl daemon-reload
```

The unit is [`deploy/linux/sew-run.service`](../../deploy/linux/sew-run.service). It is **generated** from the host's own constants by `python3 scripts/render_service_files.py --write`; do not edit the copy in the repository, a guard compares it with the generator. To change a setting on one server use a drop-in (`sudo systemctl edit sew-run`), not an edit of the file. What it does:

- `Restart=on-failure`, `RestartSec=10`, `StartLimitIntervalSec=0`: restart after any failure, ten seconds apart, forever.
- `RestartPreventExitStatus=2 3 4 5`: **never** restart on a usage refusal (2), a held lock (3), a failed pre-flight (4) or a fault only the operator can fix (5: no key, a rejected key, a key that can withdraw). A restart would only repeat it, and repeating a rejected key is how an IP gets banned. The numbers come from the exit-code table; see [`exit_codes.md`](exit_codes.md). Exit `1` (a crash) and `6` (the exchange is out of reach) are restarted.
- `TimeoutStopSec=62`: above the longest stop. The formula is written in the unit: `ceil(--stop-timeout + 30 s + 2 s) + 5 s = ceil(25 + 30 + 2) + 5`. The host leaves by itself after 57 s at the latest, so systemd's `SIGKILL` never has to.
- `Type=notify` with `--host-signal sdnotify`: the unit is "active" only once the pre-flight passed and the bots were restored, so a start that dies in the pre-flight is a failed start. (The notify socket does not exist in a container: §13.)
- `MemoryMax=1G`, a dedicated no-login account, `ProtectSystem=strict` with the data root opened by `StateDirectory=`, `NoNewPrivileges` and the other lines you can read in the file. The host writes its data root and nothing else.
- No `log.file`, no `--dev`, no `--debug`: the log is standard output, which the journal captures and bounds ([`LOGGING.md`](LOGGING.md) §1).

## 3. Provision the keys

A key must be **bound to the server's address** at the exchange, must **not** be allowed to withdraw (the pre-flight refuses a key that can), and must never appear in a unit file, a plan file, a log or a shell history.

**Testnet** (the first run): the environment is the source. Put the four names in a file only root and the service can read:

```bash
sudo install -m 0640 -o root -g sew /dev/null /etc/sew/sew.env
sudoedit /etc/sew/sew.env
```

```text
BINANCE_FUTURES_TESTNET_API_KEY=<your futures testnet key>
BINANCE_FUTURES_TESTNET_API_SECRET=<your futures testnet secret>
BINANCE_SPOT_TESTNET_API_KEY=<your spot testnet key>
BINANCE_SPOT_TESTNET_API_SECRET=<your spot testnet secret>
```

A venue you do not use can be left out. The unit reads this file if it exists (`EnvironmentFile=-`).

**The unit loads the four mainnet credential files even on a testnet-only server.** Its `LoadCredential=` lines name them, and systemd refuses to start the service when one is missing, with `status=243/CREDENTIALS` ("Failed to set up credentials"). This was observed on the first VPS install, on 2026-10-14 (systemd 255). A testnet-only server does one of two things:

- **Create the four files empty**, the same command as for mainnet below. An empty credential reads as "no key". Use this when the server will later go to mainnet, because nothing changes then except filling the files in.
- **Clear the list with a drop-in.** A `LoadCredential=` line with no value resets the unit's list, so the service starts without the files. Put it in the same drop-in as `--start-planned` (§8), and remove it before any mainnet venue.

**Mainnet**: systemd credentials (decision O3). Each secret is a file only root can read; the unit hands it to the service through `LoadCredential=`, so it is not in the service's environment and not inherited by a child process. The unit names four files; create all four, **empty for a venue you do not use** (an empty credential reads as "no key"; a missing file would stop the unit from starting):

```bash
for name in futures_mainnet_api_key futures_mainnet_api_secret spot_mainnet_api_key spot_mainnet_api_secret; do
  sudo install -m 0600 -o root -g root /dev/null "/etc/sew/credentials/$name"
done
# For a venue you use, type the value without echoing it. `read -s` is bash (the shell you
# are logged in to; dash, which is `sh` on Debian and Ubuntu, has no `read -s`), and `printf` is
# a builtin, so the value is in no process's argument list and not in your history:
read -rsp "futures mainnet key: " v; echo
printf '%s' "$v" | sudo tee /etc/sew/credentials/futures_mainnet_api_key > /dev/null; unset v
```

Mainnet bots are never started by the host without you typing the venue (`--confirm-venue`, decision O8); the unit passes none.

## 4. Run the pre-flight

For **testnet**, as the service account with the keys in the environment (the service is not running, so the data root is free):

```bash
sudo -u sew bash -c 'set -a; . /etc/sew/sew.env; set +a; \
  PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py preflight --venue futures_testnet'
echo "exit $?"
```

For **mainnet** the credentials exist only inside the unit, so the pre-flight is the one `run` itself performs before it restores any bot: `sudo systemctl start sew-run`, then read its lines (`journalctl -u sew-run -o cat | grep '\[preflight\]'`). A failed check stops the start with exit 4, 5 or 6 and an ERROR line per finding with its remedy.

Exit codes of `preflight`: `0` nothing failed (a WARN passes), `4` a check failed, `5` credentials absent or refused, `6` the exchange is unreachable. What to do on each check:

| Check | A FAIL or WARN means | Do |
| :--- | :--- | :--- |
| `python-floor` | the interpreter is below 3.12 | install Python 3.12+ and rebuild `/opt/sew/venv` |
| `data-root-writable` | the service account cannot write the data root | `sudo chown -R sew:sew /var/lib/sew`; check it is not a read-only mount |
| `disk-space` | WARN below 1 GiB or 10 % free, FAIL below 100 MiB | free space; a full disk stops the database write, not the network call, so the symptoms are strange |
| `clock-skew` | WARN above 500 ms, FAIL at 1000 ms against the exchange's time | `timedatectl status`; enable `systemd-timesyncd` or `chrony`; the exchange refuses a request stamped 1000 ms ahead (`-1021`) |
| `credentials-present` | no key for a venue in use (exit 5) | §3; the line names which source answered, never the value |
| `key-permissions` | the exchange rejected the key (`-2015`: key, address or permission) or the signature (`-1022`) | check the key's IP binding includes this server, and that its secret is the right one |
| `no-withdraw-permission` | the key can withdraw | create a new key without withdrawal; never run with this one |
| `outbound-address` | the address the exchange sees is not the one the key is bound to, or could not be read | bind the key to the address shown, or fix the route |
| `bot-files-readable` | WARN: a bot file in `state/bots/` was written by a newer build, or is damaged; its bot is **not loaded** and the file is left untouched | §8: roll back to the build that wrote it, or copy the file out if it is damaged; do not edit it |

`--skip <ids>` skips checks; `run --skip-preflight` skips them all and logs a WARNING. Neither belongs in the unit.

## 5. First run, on the testnet

```bash
sudo systemctl enable --now sew-run
systemctl status sew-run --no-pager
journalctl -u sew-run -o cat -f
```

Expected, in order: `[run]` (the options in effect), `[preflight]`, `[host] BOOTING -> SERVING`, the one `[alerts]` WARNING from §0, then a `[health]` line every 60 seconds. Look at it from a second process:

```bash
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew \
  /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py status
echo "exit $?"
```

`status` opens no connection and takes no lock: it reads `state/health.json` and the lock. Exit `0` the host is running and healthy, `10` no host is running, `11` running but unhealthy (the snapshot is stale or a section is unavailable or degraded).

## 6. Day to day

| Want | Linux | Windows |
| :--- | :--- | :--- |
| Start / stop / restart | `systemctl start\|stop\|restart sew-run` | `nssm start\|stop\|restart sew-run` |
| Run at boot | `systemctl enable sew-run` | set by the install script (`SERVICE_AUTO_START`) |
| Is it alive and what does it hold | `main.py status` (as §5) | the same, from the service account or an Administrator who sets `SEW_DATA_ROOT` |
| Follow the log | `journalctl -u sew-run -o cat -f` | `Get-Content C:\ProgramData\sew\service-logs\sew-run.log -Wait` |
| Only problems | `journalctl -u sew-run -o cat \| grep -E ' - (WARNING\|ERROR\|CRITICAL) - '` | `Get-Content C:\ProgramData\sew\service-logs\sew-run.log \| Select-String ' - (WARNING\|ERROR\|CRITICAL) - '` |

**Reading the health line** (full table in [`LOGGING.md`](LOGGING.md) §4): `[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0,recovering:0 tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310`. It is progress, not liveness: alert yourself when the line stops appearing, when `tick_age_s` or `stream_down_s` keep growing, when `halted` or `recovering` is above zero that you did not expect, or when `skew_ms` approaches 1000. `na` means "not measured yet".

## 7. What the exit codes mean for you

The full table is [`exit_codes.md`](exit_codes.md). The ones a service meets:

| Code | systemd does | You do |
| :-: | :--- | :--- |
| `0` | nothing (a requested stop, or a second signal) | nothing |
| `1` | restarts after 10 s | read the traceback in the journal; a crash loop is a bug to report with the log **file** |
| `2` | does not restart | a flag in the unit is wrong; `journalctl` names it |
| `3` | does not restart | another copy holds the data root: a second `run`, or the desktop app on the same `SEW_DATA_ROOT`. Stop it |
| `4` | does not restart | a machine check failed: the table in §4 |
| `5` | does not restart | the key: absent, rejected, can withdraw, or `--resume-recovering` without an alert channel; §3 and §4 |
| `6` | restarts after 10 s | the exchange is down or unreachable; it retries until it is back |

After fixing a code `2`–`5` cause, `systemctl reset-failed sew-run && systemctl start sew-run`.

## 8. Upgrade and rollback

The state is the data root's `state/` (the bots' files, the alert outbox, the snapshot). The upgrade **leaves resting orders on the exchange** (the default stop, §0) and nothing watches them while the host is down; do it when that is acceptable. `--on-stop stop-bots` cancels first, but it is a flag of the process being stopped: it only applies if the running host was *started* with it (a drop-in for `ExecStart`).

```bash
# 1. See what is running.
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py bot list
# 2. Stop, and read that it drained: "DRAINING -> STOPPED" and "workers closed", exit 0.
sudo systemctl stop sew-run
journalctl -u sew-run -o cat -n 40
# 3. Copy the state aside (the way back).
sudo cp -a /var/lib/sew/state "/var/lib/sew/state.before-$(date +%F)"
# 4. Upgrade the code and its dependencies.
sudo git -C /opt/sew/Sagittarius_Elite_Warrior fetch --tags
REF='<the release tag or commit>'   # edit this line first
sudo git -C /opt/sew/Sagittarius_Elite_Warrior checkout "$REF"
sudo /opt/sew/venv/bin/pip install -r /opt/sew/Sagittarius_Elite_Warrior/requirements-headless.txt \
    -c /opt/sew/Sagittarius_Elite_Warrior/requirements.lock
sudo /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/scripts/engine_pin.py install
# 5. Regenerate the unit if the release changed it, then:
sudo cp /opt/sew/Sagittarius_Elite_Warrior/deploy/linux/sew-run.service /etc/systemd/system/ && sudo systemctl daemon-reload
# 6. Pre-flight (testnet: §4; mainnet: the start does it), start, look.
sudo systemctl start sew-run
sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python \
    /opt/sew/Sagittarius_Elite_Warrior/src/main.py status
```

Read the `[preflight]` lines after the start. **`bot-files-readable` WARN** means a bot file was written by a newer build than this one and its bot is not loaded; `status` and `bot list` list that file with its path and reason (`unknown schema_version 2`). The file is never rewritten. Every bot a restart found RUNNING or PAUSED is now RECOVERING and **stays so until a person resumes it**; one WARNING per bot names it (§0).

**Rollback**: stop, `git checkout` the previous release, reinstall its dependencies (step 4), and put the state back from step 3 **if the newer build has written bot files** (an older build refuses a newer file and leaves it; restoring the copy returns the bots as they were). Start and check as above.

### Plan files and version control (`bot export`, `bot apply`, `run --start-planned`)

A plan is a JSON file (`sew.bot-plan/1`) that names each bot by name and venue and holds **no key, secret or account identifier**, so it is safe to keep in version control and to review as a diff. It is how a server's bots are defined without the desktop app. The procedure, each step run as in §5 (`M` is the `sudo -u sew env ... main.py` prefix there):

```bash
M="sudo -u sew env PYTHONPATH=/opt/sew SEW_DATA_ROOT=/var/lib/sew /opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py"
$M bot export --all --output /var/lib/sew/plan.json   # once; read-only; never overwrites a file
# edit plan.json (or keep it in git and copy it over), then:
$M bot apply /var/lib/sew/plan.json --dry-run         # prints what would change; changes nothing; works beside a running host
sudo systemctl stop sew-run
$M bot apply /var/lib/sew/plan.json [--prune]         # creates and edits bots (with --prune deletes the ones the plan omits, if at rest); starts and stops nothing
sudo systemctl start sew-run
```

- `bot apply` changes bots, so it needs the data root's lock: with the host running it exits `3` and changes nothing (control of a running host is `EPIC-038J`, decision O4). A real apply is a **writable boot**, so the restart rule runs first, as at any start: a bot saved as RUNNING or PAUSED becomes RECOVERING in its file (the same state the next `run` would have made it). `--dry-run` boots read-only and changes nothing, which is why it is safe beside a running host. A second apply of the same plan changes nothing. An entry that would edit a bot in a state the lifecycle forbids (it must be stopped first) is reported, not applied, and the command exits `2`; the other entries are applied.
- `apply` records what the plan wants in **`state/bot_plan.json`** (beside the bots' files, keyed by bot id). **Only that applied record is what the host reads**, never the file you edit, so an edit counts once it has been applied.
- **`run --start-planned`** starts the bots the applied plan says are running and that are at rest. It is not in the unit by default. With no applied plan, or a record that cannot be read, it exits **`5`** before anything boots, which the unit does not restart; so add it to the unit only after a plan has been applied. To add it, use a drop-in (`sudo systemctl edit sew-run`): write `[Service]`, an empty `ExecStart=`, then `ExecStart=` followed by the unit's own line with ` --start-planned` appended.

  `systemctl edit` opens an editor. Its `--stdin` option needs systemd 256 or newer, and Ubuntu 24.04 ships 255, where it answers `unrecognized option '--stdin'`. To do it without an editor, write the drop-in file yourself:

  ```bash
  sudo mkdir -p /etc/systemd/system/sew-run.service.d
  sudo tee /etc/systemd/system/sew-run.service.d/override.conf > /dev/null <<'EOF'
  [Service]
  ExecStart=
  ExecStart=/opt/sew/venv/bin/python /opt/sew/Sagittarius_Elite_Warrior/src/main.py run --stop-timeout 25 --health-interval 60 --on-stop leave-orders --host-signal sdnotify --start-planned
  EOF
  sudo systemctl daemon-reload
  sudo systemctl reset-failed sew-run
  sudo systemctl restart sew-run
  systemctl cat sew-run | grep -E "LoadCredential|ExecStart"   # the drop-in's lines come last and win
  ```

  On a testnet-only server without the four credential files (§3), add the line `LoadCredential=` under `[Service]` in the same file.
- A bot on a **mainnet** venue is started only with `--confirm-venue <venue>` in the same line; without it the host exits `2` and starts nothing. One `--confirm-venue` names one venue.

## 9. Install on Windows (NSSM)

*Not run on a Windows machine by its author; §11 is how it is proven.* Decision O5: NSSM is documented as an external tool, Task Scheduler as the stated fallback; neither is a dependency of the app.

1. Python 3.12+, `git`, then the same three steps as §2 with Windows paths: clone to `C:\sew\Sagittarius_Elite_Warrior` (the directory name is required), `python -m venv C:\sew\venv`, `C:\sew\venv\Scripts\pip install -r requirements-headless.txt -c requirements.lock`, then `scripts\engine_pin.py install`.
2. Download NSSM from <https://nssm.cc> to a folder you control (for example `C:\tools\nssm.exe`). Check the download against the publisher's page; the install runs it as an Administrator.
3. From an elevated PowerShell:

```powershell
.\deploy\windows\nssm-install.ps1 -Nssm C:\tools\nssm.exe -Python C:\sew\venv\Scripts\python.exe `
    -Checkout C:\sew\Sagittarius_Elite_Warrior -DataRoot C:\ProgramData\sew
```

The script ([`deploy/windows/nssm-install.ps1`](../../deploy/windows/nssm-install.ps1), generated by the same `render_service_files.py`) is idempotent: every setting is a `nssm set`, so running it again changes nothing. It sets:

- `AppExit Default Restart` and `AppExit 0|2|3|4|5 Exit`: NSSM restarts on every status unless told otherwise, so it ends the service on a clean exit `0` (as the unit's `Restart=on-failure` does) and on the unit's `RestartPreventExitStatus` codes, with `AppRestartDelay 10000`.
- **`AppStopMethodConsole 62000`**: NSSM stops a console program by sending **Ctrl-C first**, which the host handles as `SIGINT` (a drain, then exit 0), and waits this long before it tries `WM_CLOSE` and then `TerminateProcess`. NSSM's default wait is 1500 ms, far below the host's 57 s worst case, which would kill a drain in progress. The figure is the unit's `TimeoutStopSec` in milliseconds.
- `AppStdout`/`AppStderr` to `service-logs\sew-run.log` with `AppRotateFiles 1`, `AppRotateOnline 1`, `AppRotateBytes 10485760`: the log is rotated by the wrapper; the app sets no `log.file`.
- `AppEnvironmentExtra` with `PYTHONPATH` and `SEW_DATA_ROOT`; the service account `NT SERVICE\sew-run` (a virtual account, no password), granted modify on the data root and nothing else.

**Keys on Windows.** There is no `LoadCredential`. For a **mainnet** venue use the permission-checked file store (decision O3's fallback): a directory outside the checkout whose ACL grants only the service account, SYSTEM and Administrators, named by `SEW_SECRET_FILES_DIR`, one file per secret (`futures_mainnet_api_key`, `futures_mainnet_api_secret`, and the spot pair). The store refuses a file anyone else can reach and prints the `icacls` command that fixes it. Whether the Windows Credential Manager works for a service account is **unanswered** (`EPIC-038E`); do not rely on it.

```powershell
$dir = 'C:\ProgramData\sew\secrets'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
icacls $dir /inheritance:r /grant 'NT SERVICE\sew-run:(OI)(CI)R' 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F'
$secret = Read-Host -AsSecureString 'futures mainnet key'
$plain = [System.Net.NetworkCredential]::new('', $secret).Password
[System.IO.File]::WriteAllText("$dir\futures_mainnet_api_key", $plain, [System.Text.UTF8Encoding]::new($false))
```

Then install (or re-run the install script) with `-SecretFilesDir C:\ProgramData\sew\secrets`, which sets `SEW_SECRET_FILES_DIR` for the service.

A **testnet** key goes in the service's environment: `nssm set sew-run AppEnvironmentExtra "+BINANCE_FUTURES_TESTNET_API_KEY=<key>"` (the `+` appends). NSSM keeps that in the registry, readable by Administrators: acceptable for a testnet key, not for a mainnet one. **Running the install script again replaces the whole environment list**, so append the testnet variables again afterwards.

**Reboot.** Windows gives a service a limited time to stop at shutdown (`WaitToKillServiceTimeout`, 5 s by default for the system), shorter than a drain. A host that was killed at a reboot has not written `STOPPED`; the next start reads each bot as RECOVERING, as after a crash. The checklist records what a reboot does on your server.

**Task Scheduler (the fallback).** Use it only if NSSM is unacceptable. Per the research this decision rests on (R10, not run here): its restart settings are coarse (a fixed count and interval, no way to say which exit codes not to restart on, so a configuration fault would loop), and it has no setting that sends Ctrl-C first, so a stop ends the process outright and no drain runs. It can start a task at boot with highest privileges and "run whether the user is logged on or not"; everything else in §6–§8 is the same.

## 10. Logs

The host writes to standard output only. systemd's journal captures and bounds it (`SystemMaxUse=` in `journald.conf`, `journalctl --vacuum-time=14d`); NSSM rotates what it captures. If you set `log.file` anyway it grows without bound until the Engine gains rotation (decision O7); [`LOGGING.md`](LOGGING.md) §2 has the `logrotate` stanza and says why `copytruncate` is required. Do not restate it here.

## 11. The checklist the owner signs

Testnet only. Two machines: a fresh Linux VPS and a fresh Windows server. **Not run yet**; each row is filled in with the date, the result and the log line that proves it, and signed.

| # | Do | Pass when | Linux | Windows |
| :-: | :--- | :--- | :-: | :-: |
| 1 | Install per §2 / §9, provision the testnet keys, start | `status` exits 0; the journal shows `BOOTING -> SERVING` and a `[health]` line | ☐ | ☐ |
| 2 | `kill -9` the process (Windows: end the task in Task Manager) | the service restarts within ~15 s; bots that were running are RECOVERING and named in a WARNING each; `[health]` lines resume; the alert for the crash is the one `EPIC-036` defines (until it merges, none) | ☐ | ☐ |
| 3 | Reboot the machine | the service is running again without a login; record whether `STOPPED` was written | ☐ | ☐ |
| 4 | `systemctl stop` / `nssm stop` while a bot is RUNNING | the log shows `DRAINING -> STOPPED` and `workers closed`; the stop took less than `TimeoutStopSec`; exit 0; orders are still on the testnet exchange | ☐ | ☐ |
| 5 | While the service runs, start a second service on the same data root (Linux: a copy of the unit named `sew-run2`; Windows: a second NSSM service) | the second exits `3` and its supervisor does **not** restart it (`systemctl status` shows `failed`, one start only; NSSM shows it stopped); the first is unaffected; remove the second | ☐ | ☐ |
| 6 | Set the clock 2 s ahead, start | the pre-flight fails `clock-skew` (exit 4) and the unit is not restarted; fix the clock and `reset-failed` | ☐ | ☐ |
| 7 | Fill the data volume below 100 MiB (a throwaway file) and start | `disk-space` is reported FAIL with its remedy (exit 4); remove the file | ☐ | ☐ |
| 8 | Remove the testnet key and start | exit 5 (`credentials-present`), not restarted | ☐ | ☐ |
| 9 | Put a bot file with `"schema_version": 99` in `state/bots/` and start | the `bot-files-readable` WARN names it; `bot list` lists it; the file is byte-for-byte unchanged | ☐ | ☐ |
| 10 | Upgrade per §8 to the next commit and back (rollback) | the bots return as RECOVERING; the state copy restores them | ☐ | ☐ |
| 11 | Set `log.file` to `/var/log/sew/sew.log` (Linux), install the `logrotate` stanza of [`LOGGING.md`](LOGGING.md) §2, run `logrotate -f` | the file rotates, the app keeps writing to it, nothing is lost beyond the documented `copytruncate` window; then remove `log.file` | ☐ | n/a |
| 12 | Stop the host on purpose and wait the heartbeat interval | the dead man's switch tells you. **Needs `EPIC-036E`; leave unchecked until it merges.** | ☐ | ☐ |

Signed: ____________________ date: ____________ machine: ____________________

## 12. What is proven mechanically, and what is not

Guards in the test suite (`tests/unit/scripts/test_service_files.py`, `test_nssm_install_script.py`, `test_headless_runbook.py`, `test_runbook_shell_snippets.py`): the unit and the NSSM script equal their generator; `RestartPreventExitStatus` equals the exit-code table's non-restarting codes; `TimeoutStopSec` and `AppStopMethodConsole` exceed `--stop-timeout` + the host's grace and snapshot constants; the unit's arguments are accepted by the real command-line parser; no `log.file`, `--dev` or `--debug`; the credential names are the ones the store reads; the hardening leaves the data root and the notify socket open; `systemd-analyze verify` accepts the unit; the NSSM script parses as PowerShell and, run against a stand-in `nssm`, issues the settings above and installs nothing the second time; this runbook names those figures and every pre-flight check; every bash block in it parses and the key-provisioning step is run for real with a placeholder value. On the CI runner a missing `pwsh`, `systemd-analyze` or `bash` fails these tests rather than skipping them.

**Not proven**: the unit under a running systemd (no systemd was PID 1 where it was written), the NSSM script on Windows, the reboot and `kill -9` rows above, and the Windows Credential Manager. The checklist is how they get proven.

## 13. Containers

`--host-signal sdnotify` does not work inside Docker unless the host's notify socket is mounted into the container, and systemd credentials do not exist there. A Dockerfile is out of scope for this epic; if you run the app in a container, run `main.py run` without `--host-signal`, supply keys through the container runtime's secrets as environment variables, and let the container runtime restart it with the same policy: do not restart on exit codes `2`–`5`.
