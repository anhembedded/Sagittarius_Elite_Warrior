# shellcheck shell=sh
# /etc/profile.d/sew.sh - the shell helpers of the sew-run service.
#
# Written by sew-install and sew-update from deploy/linux/sew-profile.sh and overwritten on every
# run: do not edit it (your own aliases belong in your ~/.bashrc). It is plain POSIX sh, because
# /etc/profile reads it for every kind of login shell. Open a new login shell, or `. /etc/profile.d/sew.sh`,
# after an install. Docs/OPERATIONS/headless_runbook.md section 6 describes the helpers.

SEW_HOME=${SEW_HOME:-/opt/sew}
SEW_DATA=${SEW_DATA:-/var/lib/sew}
SEW_CHECKOUT=$SEW_HOME/Sagittarius_Elite_Warrior
export SEW_HOME SEW_DATA SEW_CHECKOUT

# _sew_as_service <command...>: as the sew account; sudo is used unless you already are it.
_sew_as_service() {
    if [ "$(id -un)" = sew ]; then
        "$@"
    else
        sudo -u sew "$@"
    fi
}

# _sew_as_root <command...>: as root, with sudo unless you already are.
_sew_as_root() {
    if [ "$(id -u)" = 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

# M <arguments of main.py>: the app's command line, as the service account, in this directory's
# terminal. Typed `M bot list`, `M status`, `M bot resume <id>`. The terminal's width, TERM,
# NO_COLOR and COLORTERM are passed on by hand: sudo resets the environment, and a COLUMNS lost
# on the way made `rich` draw at 80 columns (BOT-198).
M() {
    _sew_cols=${COLUMNS:-$(tput cols 2> /dev/null)}
    # shellcheck disable=SC2086 # ${x:+"NAME=$x"} is one word, or none when x is empty
    _sew_as_service env \
        "PYTHONPATH=$SEW_HOME" "SEW_DATA_ROOT=$SEW_DATA" "TERM=${TERM:-dumb}" \
        ${_sew_cols:+"COLUMNS=$_sew_cols"} \
        ${NO_COLOR:+"NO_COLOR=$NO_COLOR"} \
        ${COLORTERM:+"COLORTERM=$COLORTERM"} \
        "$SEW_HOME/venv/bin/python" "$SEW_CHECKOUT/src/main.py" "$@"
    _sew_status=$?
    unset _sew_cols
    return "$_sew_status"
}

# sewlog [logs options]: follow the service's log, coloured: `sewlog --level warning --bot <id>`.
sewlog() {
    _sew_as_root journalctl -u sew-run -o cat -f | M logs "$@"
}

# sewstatus: is the host alive and healthy (exit 0, 10 no host, 11 unhealthy).
sewstatus() {
    M status "$@"
}

# sewbots: every bot, one row each.
sewbots() {
    M bot list "$@"
}

# sewproblems [journalctl options]: only the WARNING, ERROR and CRITICAL records, since today.
sewproblems() {
    [ "$#" -gt 0 ] || set -- --since today
    _sew_as_root journalctl -u sew-run -o cat "$@" | grep -E ' - (WARNING|ERROR|CRITICAL) - '
}

sewhelp() {
    cat << 'HELP'
M <args>         the app's command line as the service account: M bot list, M status, M bot resume <id>
sewlog [opts]    follow the log, coloured (--level warning, --bot <id>, --tag <name>, --since 2h)
sewstatus        is the host alive and healthy
sewbots          every bot, one row each
sewproblems      only WARNING, ERROR and CRITICAL records since today (or pass journalctl options)
variables        SEW_HOME SEW_DATA SEW_CHECKOUT
sudo sew-key add | list | remove    the Binance keys      sudo sew-update [ref]    upgrade
sudo sew-backup                     a dated archive of the state
HELP
}
