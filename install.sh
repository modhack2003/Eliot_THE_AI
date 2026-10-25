#!/usr/bin/env bash
# Supported Kali/Debian/Ubuntu bootstrap. Run as your normal user.
set -Eeuo pipefail
trap 'printf "\nEliot setup stopped at line %s. Fix the error above and rerun the same command.\n" "$LINENO" >&2' ERR

source_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]:-./install.sh}")" && pwd)
skip_system=false
source_ref=main
installer_arguments=()
while (($#)); do
    argument=$1
    case "$argument" in
        --skip-system) skip_system=true; installer_arguments+=("$argument") ;;
        --no-desktop) installer_arguments+=("$argument") ;;
        --prefix|--ref)
            if (($# < 2)) || [[ -z $2 || $2 == --* ]]; then
                printf 'Missing value for %s\n' "$argument" >&2; exit 2
            fi
            if [[ $argument == --ref ]]; then
                source_ref=$2
            else
                installer_arguments+=("$argument" "$2")
            fi
            shift ;;
        --help|-h)
            printf '%s\n' 'Usage: bash install.sh [--prefix DIRECTORY] [--skip-system] [--no-desktop] [--ref BRANCH]' \
                'Installs prerequisites, an isolated runtime, bundled skills and a launcher.' \
                'Kali/Debian/Ubuntu: sudo is used only for missing OS packages.' \
                'Default paths follow XDG; --prefix keeps everything below one directory.'
            exit 0 ;;
        *) printf 'Unknown option: %s. Use --help.\n' "$argument" >&2; exit 2 ;;
    esac
    shift
done

if [[ $(uname -s) != Linux ]]; then
    printf '%s\n' 'Use install.cmd on Windows. This bootstrap supports Linux.' >&2
    exit 1
fi
if [[ $skip_system == false ]]; then
    if ! command -v apt-get >/dev/null || ! command -v dpkg-query >/dev/null; then
        printf '%s\n' 'Automatic OS setup requires Kali/Debian/Ubuntu. Install Python 3.11+, venv, pip, git, curl, CA certificates and nmap, then use --skip-system.' >&2
        exit 1
    fi
    missing=()
    for package in python3 python3-venv python3-pip git curl ca-certificates nmap; do
        if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) != 'install ok installed' ]]; then
            missing+=("$package")
        fi
    done
    if ((${#missing[@]})); then
        privilege=()
        if ((EUID != 0)); then
            if ! command -v sudo >/dev/null; then
                printf '%s\n' 'Install sudo or ask an administrator to install the listed prerequisites, then rerun with --skip-system.' >&2
                printf 'Missing: %s\n' "${missing[*]}" >&2
                exit 1
            fi
            privilege=(sudo)
        fi
        printf 'Installing OS prerequisites: %s\n' "${missing[*]}"
        "${privilege[@]}" apt-get update
        "${privilege[@]}" apt-get install -y --no-install-recommends "${missing[@]}"
    fi
fi
if ! command -v python3 >/dev/null; then
    printf '%s\n' 'Python 3.11+ is required. Rerun without --skip-system to install prerequisites.' >&2
    exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Python 3.11+ required. Use current Kali, Debian 12+, or Ubuntu 24.04+.")'
if [[ ! -f $source_dir/scripts/install.py || ! -f $source_dir/pyproject.toml ]]; then
    # Also works as a downloaded standalone installer or through bash process substitution.
    temporary_source=$(mktemp -d -t eliot-source-XXXXXXXX)
    trap 'rm -rf -- "$temporary_source"' EXIT
    git clone --depth 1 --branch "$source_ref" -- https://github.com/modhack2003/Eliot_THE_AI.git "$temporary_source/source"
    source_dir=$temporary_source/source
fi
python3 -I "$source_dir/scripts/install.py" "${installer_arguments[@]}"
