#!/usr/bin/env bash
# Block staged files that would leak data into the commit graph.
#
# Used by .pre-commit-config.yaml (local hook) and mirrored in
# .github/workflows/no-data-leak.yml. Exits non-zero on the first
# violation but prints all detected violations first.
set -euo pipefail

BLOCKED_EXT='\.(csv|tsv|psv|xls|xlsx|xlsm|xlsb|ods|parquet|feather|arrow|orc|avro|sav|dta|sas7bdat|rdata|rds|pkl|pickle|joblib|npz|npy|mat|h5|hdf5|nc|db|sqlite|sqlite3|pdf|gz|bz2|xz|zst|zip|tar|7z|rar)$'

violations=0

for f in "$@"; do
  # Rule 1: anything under data/ except the dictionary.
  if [[ "$f" == data/* && "$f" != "data/DATA_DICTIONARY.md" ]]; then
    echo "error: $f — files under /data/ may not be committed (only data/DATA_DICTIONARY.md is permitted)." >&2
    violations=1
    continue
  fi
  # Rule 2: blocked extension anywhere in the tree.
  if echo "$f" | grep -Eqi "$BLOCKED_EXT"; then
    echo "error: $f — extension is in the blocked-data list." >&2
    violations=1
  fi
done

if [ "$violations" -ne 0 ]; then
  echo "" >&2
  echo "If a file was added in error, run \`git restore --staged <file>\` then delete it or move it under /data/." >&2
  echo "If you genuinely need to commit a blocked extension (e.g. a small fixture), name it differently or get reviewer sign-off to update this script." >&2
  exit 1
fi
