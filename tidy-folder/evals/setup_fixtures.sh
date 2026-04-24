#!/bin/bash
# Creates content-bearing test folders for tidy-folder skill evals.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Setting up eval fixtures ==="
"$SCRIPT_DIR/fixture_builder.py"

for fixture in \
  "$SCRIPT_DIR/fixtures/freelance-designer/test-folder" \
  "$SCRIPT_DIR/fixtures/polluted-project/test-folder" \
  "$SCRIPT_DIR/fixtures/retiree-documents/test-folder"
do
  count="$(find "$fixture" -type f | wc -l | tr -d ' ')"
  echo "  $(basename "$(dirname "$fixture")"): $count files"
done

echo
echo "=== All fixtures ready ==="
