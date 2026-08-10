#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPCH_DATA_DIR="${SCRIPT_DIR}/tpch-data"
TPCH_REPO_DIR="${TPCH_DATA_DIR}/tpch-dbgen"
SOURCE_REPO_URL="https://github.com/electrum/tpch-dbgen.git"

mkdir -p "${TPCH_DATA_DIR}"

if [[ ! -d "${TPCH_REPO_DIR}/.git" ]]; then
  rm -rf "${TPCH_REPO_DIR}"
  git clone "${SOURCE_REPO_URL}" "${TPCH_REPO_DIR}"
else
  git -C "${TPCH_REPO_DIR}" fetch --all --prune
fi

pushd "${TPCH_REPO_DIR}" >/dev/null

perl -pi -e 's/\r$//' makefile.suite dss.ddl queries/*.sql answers/*.out 2>/dev/null || true
cp makefile.suite makefile

python3 - <<'PY'
from pathlib import Path
import re

makefile = Path('makefile')
text = makefile.read_text()
text = re.sub(r'^CC\s*=.*$', 'CC      = gcc', text, flags=re.M)
text = re.sub(r'^DATABASE=.*$', 'DATABASE= ORACLE', text, flags=re.M)
text = re.sub(r'^MACHINE\s*=.*$', 'MACHINE = LINUX', text, flags=re.M)
text = re.sub(r'^WORKLOAD\s*=.*$', 'WORKLOAD = TPCH', text, flags=re.M)
makefile.write_text(text)
PY

make -j"$(nproc)" dbgen qgen
./dbgen -s 1 -f

popd >/dev/null

echo "TPC-H build and data generation complete."
echo "Generated .tbl files are in: ${TPCH_REPO_DIR}"