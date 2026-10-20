# shellcheck shell=bash disable=SC2034,SC2153
# sew-lib.sh - what sew-install and sew-update share. Sourced by them, never run.
#
# The caller sets TOOL (its name, for messages) and DRY_RUN (0|1) before it calls sew_init.
# Exit codes follow Docs/OPERATIONS/exit_codes.md: `die` is a refusal the script designed (2),
# `fail` is a command that failed (1).
#
# Environment overrides, for tests only (refused when really root, as sew-key refuses SEW_KEY_*):
# SEW_DEPLOY_ROOT (a prefix for every path below), SEW_DEPLOY_EUID, SEW_DEPLOY_NO_CHOWN,
# SEW_DEPLOY_MIN_FREE_MB.

umask 022   # a pip install under root's umask 077 would leave a venv the sew account cannot read

die() {
  printf '%s: %s\n' "$TOOL" "$*" >&2
  exit 2
}

fail() {
  printf '%s: %s\n' "$TOOL" "$*" >&2
  exit 1
}

warn() {
  printf '%s: warning: %s\n' "$TOOL" "$*" >&2
}

step() {
  printf '\n== %s\n' "$*"
}

note() {
  printf '  %s\n' "$*"
}

sew_init() {
  REAL_UID=$(id -u)
  if [[ "$REAL_UID" == "0" && -n "$(compgen -e SEW_DEPLOY_)" ]]; then
    printf '%s: refusing to run as root with SEW_DEPLOY_* set in the environment (%s)\n' "$TOOL" \
      "$(compgen -e SEW_DEPLOY_ | tr '\n' ' ')" >&2
    exit 2
  fi
  EFFECTIVE_UID="${SEW_DEPLOY_EUID:-$REAL_UID}"
  NO_CHOWN="${SEW_DEPLOY_NO_CHOWN:-}"
  MIN_FREE_MB="${SEW_DEPLOY_MIN_FREE_MB:-2048}"
  ROOT="${SEW_DEPLOY_ROOT:-}"

  # The layout of runbook section 1; the unit hard-codes the same paths.
  SEW_HOME_DIR="$ROOT/opt/sew"
  CHECKOUT="$SEW_HOME_DIR/Sagittarius_Elite_Warrior"
  VENV="$SEW_HOME_DIR/venv"
  DATA_ROOT="$ROOT/var/lib/sew"
  ETC_DIR="$ROOT/etc/sew"
  CREDENTIALS_DIR="$ETC_DIR/credentials"
  ENV_FILE="$ETC_DIR/sew.env"
  UNIT_DIR="$ROOT/etc/systemd/system"
  PROFILE_FILE="$ROOT/etc/profile.d/sew.sh"
  SBIN_DIR="$ROOT/usr/local/sbin"
  BACKUP_DIR="$ROOT/var/backups/sew"
  SERVICE=sew-run
  EXPECTED_CREDENTIAL_LINE='LoadCredential=sew:/etc/sew/credentials'
  # Linked into $SBIN_DIR; the first three are the operator's commands.
  TOOLS=(sew-key sew-backup sew-update sew-install)
}

require_root() {
  [[ "$EFFECTIVE_UID" == "0" ]] || die "run this as root (sudo $TOOL): it writes /etc, /opt and /usr/local"
}

# --- acting, or saying what it would do -------------------------------------------------------

# act <description> <command...>: say it, then run it; in a dry run only say it.
act() {
  local what="$1" status=0
  shift
  if [[ "$DRY_RUN" == 1 ]]; then
    printf '  would: %s\n' "$what"
    return 0
  fi
  printf '  %s\n' "$what"
  "$@" || status=$?
  [[ "$status" -eq 0 ]] || fail "$what failed (exit $status)"
}

# The -o/-g flags of install(1) for a file owned by $1:$2; none in a test that is not root.
owner_flags() {
  OWNER_FLAGS=()
  [[ -n "$NO_CHOWN" ]] || OWNER_FLAGS=(-o "$1" -g "$2")
}

mode_of() { # path; octal, no leading zero
  stat -c '%a' -- "$1"
}

dir_is() { # mode owner group path
  [[ -d "$4" ]] || return 1
  [[ $((8#$(mode_of "$4"))) -eq $((8#$1)) ]] || return 1
  [[ -n "$NO_CHOWN" ]] || [[ "$(stat -c '%U:%G' -- "$4")" == "$2:$3" ]]
}

# ensure_dir <mode> <owner> <group> <path>: create it, or set its mode and owner; never recursive.
ensure_dir() {
  local mode="$1" owner="$2" group="$3" path="$4"
  if dir_is "$mode" "$owner" "$group" "$path"; then
    note "$path is in place ($mode $owner:$group)"
    return 0
  fi
  owner_flags "$owner" "$group"
  act "directory $path ($mode $owner:$group)" install -d -m "$mode" "${OWNER_FLAGS[@]}" -- "$path"
}

# sync_file <source> <destination> <mode>: root's copy of a file this repository owns; replaced
# when it differs, left alone when it does not. Sets FILE_CHANGED=1 when it wrote.
sync_file() {
  local src="$1" dst="$2" mode="$3"
  if [[ -f "$dst" ]] && cmp -s -- "$src" "$dst"; then
    note "$dst is current"
    return 0
  fi
  FILE_CHANGED=1
  act "install $dst" install -m "$mode" -- "$src" "$dst"
}

# --- the host -----------------------------------------------------------------------------

# Free megabytes on the filesystem that holds (or would hold) $1.
free_mb() {
  local path="$1"
  while [[ ! -e "$path" && "$path" != "/" ]]; do
    path=$(dirname -- "$path")
  done
  df -Pm -- "$path" | awk 'NR == 2 { print $4 }'
}

# active, activating (also: waiting to restart after a failure), reloading, deactivating,
# inactive, failed...; empty when systemctl cannot say.
service_state() {
  systemctl is-active "$SERVICE" 2> /dev/null || true
}

# Whether the service is running or about to: a unit in `activating` is restarting after a
# crash (Restart=on-failure) and would start again under an upgrade's feet.
service_live() {
  case "$(service_state)" in
    active | activating | reloading | deactivating) return 0 ;;
    *) return 1 ;;
  esac
}

# The files of deploy/linux a release must carry for the install scripts to work; prints the
# first one the checkout lacks and returns 0, or returns 1 when none is missing.
RELEASE_FILES=(sew-run.service sew-profile.sh sew-backup sew-backup.service sew-backup.timer sew-key sew-update sew-install sew-lib.sh)

missing_release_file() {
  local file
  for file in "${RELEASE_FILES[@]}"; do
    if [[ ! -f "$CHECKOUT/deploy/linux/$file" ]]; then
      printf '%s\n' "$file"
      return 0
    fi
  done
  return 1
}

# --- git ----------------------------------------------------------------------------------

git_checkout() {
  git -C "$CHECKOUT" "$@"
}

# The commit a ref names, preferring the remote branch (a local branch of the same name is
# whatever the last pull left): prints the full sha, returns 1 when nothing matches.
resolve_ref() { # ref
  local candidate sha
  for candidate in "origin/$1" "$1"; do
    if sha=$(git_checkout rev-parse --verify --quiet "${candidate}^{commit}"); then
      printf '%s\n' "$sha"
      return 0
    fi
  done
  return 1
}

# --- the python environment ---------------------------------------------------------------

# runbook section 2: dependencies under the lock, the pinned engine, then bytecode (the sew
# account cannot write it, and without it every command compiles thousands of files).
install_python_stack() {
  act "pip install the headless requirements under requirements.lock" \
    "$VENV/bin/pip" install --quiet --disable-pip-version-check \
    -r "$CHECKOUT/requirements-headless.txt" -c "$CHECKOUT/requirements.lock"
  act "install the pinned engine (engine.ref)" \
    "$VENV/bin/python" "$CHECKOUT/scripts/engine_pin.py" install
  act "compile the checkout" "$VENV/bin/python" -m compileall -q "$CHECKOUT"
}

# Run the app's command line as the sew account, the way runbook section 6's $M does.
as_service() {
  sudo -u sew env "PYTHONPATH=$SEW_HOME_DIR" "SEW_DATA_ROOT=$DATA_ROOT" \
    "$VENV/bin/python" "$CHECKOUT/src/main.py" "$@"
}

# --- systemd, the shell helpers, the commands ----------------------------------------------

# The unit and the backup units this release ships, the shell helpers and the links into
# /usr/local/sbin. The unit is the generated file, never edited. Sets BACKUP_TIMER_NEW=1 when
# the backup timer did not exist before this run.
install_system_files() {
  local source_dir="$CHECKOUT/deploy/linux" name
  FILE_CHANGED=0
  BACKUP_TIMER_NEW=0
  [[ -f "$UNIT_DIR/sew-backup.timer" ]] || BACKUP_TIMER_NEW=1
  sync_file "$source_dir/sew-run.service" "$UNIT_DIR/$SERVICE.service" 0644
  sync_file "$source_dir/sew-backup.service" "$UNIT_DIR/sew-backup.service" 0644
  sync_file "$source_dir/sew-backup.timer" "$UNIT_DIR/sew-backup.timer" 0644
  ensure_dir 0755 root root "$(dirname -- "$PROFILE_FILE")"
  sync_file "$source_dir/sew-profile.sh" "$PROFILE_FILE" 0644
  ensure_dir 0755 root root "$SBIN_DIR"
  for name in "${TOOLS[@]}"; do
    link_tool "$name"
  done
  act "systemctl daemon-reload" systemctl daemon-reload
}

link_tool() { # name
  local target="$CHECKOUT/deploy/linux/$1" link="$SBIN_DIR/$1"
  if [[ -L "$link" && "$(readlink -- "$link")" == "$target" ]]; then
    note "$link is linked"
    return 0
  fi
  if [[ -e "$link" && ! -L "$link" ]]; then
    local aside
    aside="$link.before-sew-deploy-$(date -u +%Y%m%dT%H%M%SZ)"
    act "keep the existing $link as $aside" mv -- "$link" "$aside"
  fi
  act "link $link" ln -sfn -- "$target" "$link"
}

# systemd takes the *list* of LoadCredential= lines of the unit and its drop-ins; a bare
# `LoadCredential=` in a drop-in empties it, and the service then starts with no key, no
# webhook and no error (runbook section 3). Anchored: the unit's own comments name the word.
check_load_credential() {
  if [[ "$DRY_RUN" == 1 ]]; then
    note "would check that systemctl cat $SERVICE shows exactly: $EXPECTED_CREDENTIAL_LINE"
    return 0
  fi
  local lines
  lines=$(systemctl cat "$SERVICE" | grep -E '^[[:space:]]*LoadCredential=' || true)
  if [[ "$lines" != "$EXPECTED_CREDENTIAL_LINE" ]]; then
    printf '%s: systemctl cat %s shows these LoadCredential= lines:\n%s\nexpected exactly: %s\n' \
      "$TOOL" "$SERVICE" "${lines:-(none)}" "$EXPECTED_CREDENTIAL_LINE" >&2
    die "a drop-in under $UNIT_DIR/$SERVICE.service.d/ adds or resets that line; delete it from the file there, run 'systemctl daemon-reload' and run $TOOL again (runbook section 3)"
  fi
  note "LoadCredential is exactly the unit's one line"
}
