#!/usr/bin/env bash
# Enable password SSH for desktop accounts; root continues to require a key.

main() {
    set -euo pipefail
    local check_only=0 account=${SUDO_USER:-}
    while (( $# )); do
        case $1 in
            --check) check_only=1; shift ;;
            --user) account=${2:?--user needs an account}; shift 2 ;;
            --help|-h)
                printf '%s\n' 'Enable SSH password login' \
                    'Usage: bash setup-mac-ssh.sh [--check] [--user ACCOUNT]' \
                    'Enables sshd and password login for existing desktop accounts.' \
                    'Root keeps key-based login. No account passwords are changed.'
                return 0 ;;
            *) printf 'Unknown argument: %s\n' "$1" >&2; return 2 ;;
        esac
    done
    if [[ -z $account && $EUID != 0 ]]; then account=$(id -un); fi
    if [[ -z $account ]]; then
        account=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
    fi
    [[ -n $account && $account != root ]] || { echo 'Use --user YOUR_DESKTOP_ACCOUNT.' >&2; return 1; }
    if (( EUID != 0 )); then
        local -a elevated_args=(--user "$account")
        (( check_only )) && elevated_args+=(--check)
        # Even sshd -T must read root-owned host keys to validate its config.
        exec sudo -- bash -c "$(declare -f main); main \"\$@\"" bash "${elevated_args[@]}"
    fi
    if (( check_only )); then
        command -v sshd >/dev/null || { echo 'OpenSSH server is not installed.' >&2; return 1; }
        sshd -T -C "user=$account,host=localhost,addr=127.0.0.1" | awk '
            tolower($1) ~ /^(passwordauthentication|permitrootlogin|permitemptypasswords|authenticationmethods|port)$/ {print}'
        return 0
    fi
    if ! command -v sshd >/dev/null; then
        command -v pacman >/dev/null || { echo 'Install the OpenSSH server first.' >&2; return 1; }
        pacman -S --needed --noconfirm openssh
    fi
    for tool in systemctl python3 ssh-keygen flock; do
        command -v "$tool" >/dev/null || { printf 'Required command is missing: %s\n' "$tool" >&2; return 1; }
    done
    exec 9>/run/lock/omarchy-ssh-install.lock
    flock -n 9 || { echo 'Another SSH setup is running.' >&2; return 1; }
    ssh_setup_config=/etc/ssh/sshd_config
    ssh_setup_backup=/var/lib/omarchy-ssh/backups/$(date -u +%Y%m%dT%H%M%SZ)-$$
    install -d -m700 "$ssh_setup_backup"
    cp -a -- "$ssh_setup_config" "$ssh_setup_backup/sshd_config"
    ssh_setup_previous_active=0 ssh_setup_changed=0 ssh_setup_temporary=''
    if systemctl is-active --quiet sshd.service; then ssh_setup_previous_active=1; fi
    # shellcheck disable=SC2329
    cleanup() {
        local status=$?
        trap - EXIT
        if (( status != 0 && ssh_setup_changed )); then
            cp -a -- "$ssh_setup_backup/sshd_config" "$ssh_setup_config"
            if (( ssh_setup_previous_active )); then systemctl reload sshd.service || :; fi
            echo "SSH setup failed; restored the previous configuration. Backup: $ssh_setup_backup" >&2
        fi
        if [[ -n $ssh_setup_temporary ]]; then rm -f -- "$ssh_setup_temporary"; fi
        exit "$status"
    }
    # Trap state uses dedicated globals so it survives an errexit stack unwind.
    trap cleanup EXIT
    ssh_setup_temporary=$(mktemp /etc/ssh/.omarchy-password-XXXXXX)
    python3 - "$ssh_setup_config" "$ssh_setup_temporary" <<'PY'
from pathlib import Path
import re, sys
source, destination = map(Path, sys.argv[1:])
text = source.read_text()
text = re.sub(r'^# BEGIN OMARCHY PASSWORD SSH\n.*?^# END OMARCHY PASSWORD SSH\n?', '', text, flags=re.M | re.S)
block = '''# BEGIN OMARCHY PASSWORD SSH
PasswordAuthentication yes
AuthenticationMethods any
PermitEmptyPasswords no
PermitRootLogin prohibit-password
UsePAM yes
# END OMARCHY PASSWORD SSH
'''
# OpenSSH uses the first global value, so prepend before includes and Match
# sections instead of assuming a late drop-in wins over existing settings.
destination.write_text(block + '\n' + text.lstrip('\n'))
PY
    chmod --reference="$ssh_setup_config" "$ssh_setup_temporary"
    ssh-keygen -A
    sshd -t -f "$ssh_setup_temporary"
    local effective
    effective=$(sshd -T -f "$ssh_setup_temporary" -C "user=$account,host=localhost,addr=127.0.0.1")
    if ! awk 'tolower($1)=="passwordauthentication" && tolower($2)=="yes" {ok=1} END{exit !ok}' <<< "$effective" ||
            ! awk 'tolower($1)=="authenticationmethods" && tolower($2)=="any" {ok=1} END{exit !ok}' <<< "$effective"; then
        echo 'An account-specific SSH Match rule still requires keys; no configuration was changed.' >&2
        exit 1
    fi
    effective=$(sshd -T -f "$ssh_setup_temporary" -C 'user=root,host=localhost,addr=127.0.0.1')
    if ! awk 'tolower($1)=="permitrootlogin" && tolower($2) ~ /^(prohibit-password|without-password|no)$/ {ok=1} END{exit !ok}' <<< "$effective"; then
        echo 'An SSH Match rule still allows root passwords; no configuration was changed.' >&2
        exit 1
    fi
    ssh_setup_changed=1
    mv -f -- "$ssh_setup_temporary" "$ssh_setup_config"
    ssh_setup_temporary=''
    sshd -t
    systemctl enable sshd.service
    if (( ssh_setup_previous_active )); then
        systemctl reload sshd.service
    else
        systemctl start sshd.service
    fi
    ssh_setup_changed=0
    printf 'SSH enabled. Connect with your existing password: ssh %s@%s\n' "$account" "$(hostname)"
    printf 'Root keeps key-based login. Backup: %s\n' "$ssh_setup_backup"
    exit 0
}

main "$@"
