#!/usr/bin/env bash
# Start the installed app from anywhere; fall back to the source development launcher.
if command -v eliot >/dev/null 2>&1; then
    if (($# == 0)); then set -- serve; fi
    exec eliot "$@"
fi
if [[ -x $HOME/.local/bin/eliot ]]; then
    exec "$HOME/.local/bin/eliot" "$@"
fi
exec sh "$(dirname -- "${BASH_SOURCE[0]}")/eliot" "$@"
