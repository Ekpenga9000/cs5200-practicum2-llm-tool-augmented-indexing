#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TS_NODE_BIN="${SCRIPT_DIR}/../node_modules/.bin/ts-node"

if [[ ! -x "${TS_NODE_BIN}" ]]; then
  echo "Missing ts-node at ${TS_NODE_BIN}. Install the baseline Node dependencies first." >&2
  exit 1
fi

exec "${TS_NODE_BIN}" "${SCRIPT_DIR}/../src/scripts/load-tpcds.ts" "$@"