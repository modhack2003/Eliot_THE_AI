#!/usr/bin/env bash
# Compatibility alias. Historical system-wide deployment is archived in legacy/.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/install.sh" "$@"
