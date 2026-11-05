#!/usr/bin/env bash
# curl -fsSL https://erykwieliczko.github.io/omarchy-scripts/install.sh | bash -s -- --options=PK

main() {
    set -euo pipefail
    local options='' account='' check_only=0 dry_run=0
    local options_seen=0
    while (( $# )); do
        case $1 in
            --options=*|-options=*) options=${1#*=}; options_seen=1; shift ;;
            --options|-options) options=${2:?--options needs P, G, K, S, H or a combination}; options_seen=1; shift 2 ;;
            --user) account=${2:?--user needs a desktop account}; shift 2 ;;
            --check) check_only=1; shift ;;
            --dry-run) dry_run=1; shift ;;
            --help|-h)
                printf '%s\n' 'Omarchy Mac setup' \
                    'Usage: bash -s -- --options=PK [--user ACCOUNT] [--check] [--dry-run]' \
                    '  P  KDE Plasma and password login' \
                    '  G  GNOME and GDM password login' \
                    '  K  PC-style Apple keyboard settings' \
                    '  S  Steam with the AoE2-tested FEX, Proton and graphics patches' \
                    '  H  SSH password login for desktop accounts (root keeps key-based login)' \
                    'Choose one desktop (P or G), plus any extras. Only selected installers run.' \
                    '--check runs selected installers in read-only check mode.' \
                    '--dry-run prints the plan without downloads or system changes.' \
                    'Run from your desktop account, or use --user ACCOUNT as root.'
                return 0 ;;
            *) printf 'Unknown argument: %s\n' "$1" >&2; return 2 ;;
        esac
    done
    if (( ! options_seen )) || [[ -z $options ]]; then
        echo 'Choose at least one option: P (Plasma), G (GNOME), K (keyboard), S (Steam), H (SSH).' >&2
        return 2
    fi
    options=${options^^}
    if [[ $options == *[!PGKSH]* ]]; then
        echo 'Unknown option. Use P, G, K, S, H or a combination such as GKH.' >&2
        return 2
    fi
    if [[ $options == *P* && $options == *G* ]]; then
        echo 'Choose one default desktop: P (Plasma) or G (GNOME).' >&2
        return 2
    fi
    local revision=5edf198ccc61e3a7dd490e77bca69376e199e980
    local base=https://raw.githubusercontent.com/erykwieliczko/omarchy-scripts/$revision
    local -a names=() labels=() arguments=()
    if [[ $options == *P* ]]; then
        names+=(install-mac-kde-ultimate-wip.sh)
        labels+=('KDE Plasma and password login')
    fi
    if [[ $options == *G* ]]; then
        names+=(install-mac-gnome-ultimate-wip.sh)
        labels+=('GNOME and GDM password login')
    fi
    if [[ $options == *K* ]]; then
        names+=(setup-mac-keyboard.sh)
        labels+=('Apple keyboard settings')
    fi
    if [[ $options == *S* ]]; then
        names+=(install-mac-steam-ultimate-wip.sh)
        labels+=('Steam with AoE2 patches')
    fi
    if [[ $options == *H* ]]; then
        names+=(setup-mac-ssh.sh)
        labels+=('SSH password login for desktop accounts')
    fi
    printf 'Omarchy Mac setup — %s selected\n' "${#names[@]}"
    local index
    for index in "${!names[@]}"; do
        printf '  %s. %s\n' "$((index + 1))" "${labels[index]}"
        if (( dry_run )); then printf '     %s/%s\n' "$base" "${names[index]}"; fi
    done
    (( dry_run )) && return 0
    # Each existing installer owns its privilege handling and feature checks.
    # Read the entire dispatcher before curl, sudo or a child can consume stdin.
    local temporary cleanup
    temporary=$(mktemp -d)
    printf -v cleanup 'rm -rf -- %q' "$temporary"
    # Capture the shell-escaped path now: the function's locals expire before EXIT.
    # shellcheck disable=SC2064
    trap "$cleanup" EXIT
    # Fetch every selected installer before changing anything. Never fetch an
    # unselected component, and use one published revision for the whole plan.
    for index in "${!names[@]}"; do
        curl --fail --silent --show-error --location --retry 3 --proto '=https' --tlsv1.2 \
            "$base/${names[index]}" -o "$temporary/${names[index]}"
        bash -n "$temporary/${names[index]}"
    done
    for index in "${!names[@]}"; do
        arguments=()
        if [[ ${names[index]} != setup-mac-keyboard.sh && -n $account ]]; then
            arguments+=(--user "$account")
        fi
        if (( check_only )); then arguments+=(--check); fi
        printf '\n[%s/%s] %s\n' "$((index + 1))" "${#names[@]}" "${labels[index]}"
        # Explicit propagation also works if this function is used in an if/||
        # context, where Bash otherwise disables errexit inside the function.
        if bash "$temporary/${names[index]}" "${arguments[@]}"; then
            :
        else
            local status=$?
            printf 'Stopped: %s failed (exit %s).\n' "${labels[index]}" "$status" >&2
            return "$status"
        fi
    done
    if (( check_only )); then
        printf '\nSelected configuration checks passed.\n'
    else
        printf '\nYour selected configuration is installed.\n'
        if [[ $options == *[PGS]* ]]; then
            echo 'Reboot when ready to activate the desktop or kernel boot settings.'
        fi
    fi
}

main "$@"
