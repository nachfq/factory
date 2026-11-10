#!/usr/bin/env bash
set -euo pipefail
script=$(readlink -f -- "${BASH_SOURCE[0]}")
export AGENT_ENV_HOST=local
exec python3 "$(dirname -- "$script")/agent-env.py" "$@"
