#!/usr/bin/env bash
# Compatibility alias for the supported installer.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/install.sh" "$@"
