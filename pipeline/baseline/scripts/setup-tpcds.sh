#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPCDS_DATA_DIR="${SCRIPT_DIR}/tpcds-data"
TPCDS_REPO_DIR="${TPCDS_DATA_DIR}/tpcds-kit"
SOURCE_REPO_URL="https://github.com/gregrahn/tpcds-kit.git"
OUTPUT_DIR="${TPCDS_DATA_DIR}/generated"

mkdir -p "${TPCDS_DATA_DIR}"

if [[ ! -d "${TPCDS_REPO_DIR}/.git" ]]; then
  rm -rf "${TPCDS_REPO_DIR}"
  git clone "${SOURCE_REPO_URL}" "${TPCDS_REPO_DIR}"
else
  git -C "${TPCDS_REPO_DIR}" fetch --all --prune
fi

pushd "${TPCDS_REPO_DIR}/tools" >/dev/null

python3 - <<'PY'
from pathlib import Path
import re

makefile = Path('makefile')
text = makefile.read_text()
if '-fcommon' not in text:
  text = re.sub(r'^(CFLAGS\s*=\s*.*)$', r'\1 -fcommon', text, flags=re.M)
  makefile.write_text(text)
PY

make clean >/dev/null 2>&1 || true

make OS=LINUX

mkdir -p "${OUTPUT_DIR}"
./dsdgen -quiet -f -scale 1 -dir "${OUTPUT_DIR}"

popd >/dev/null

echo "TPC-DS build and data generation complete."
echo "Generated .dat files are in: ${OUTPUT_DIR}"