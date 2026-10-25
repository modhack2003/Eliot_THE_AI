#!/usr/bin/env bash
# Compatibility alias. This installs the local app, not a remote production service.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/install.sh" "$@"
