#!/usr/bin/env bash
# ROjapaneseRE master pipeline — runs ALL remaining translation surfaces
# sequentially, then applies them to the repo files and commits.
#
# Waits for an in-flight surface job to finish (detected via pgrep), so it
# can be started while another surface is still translating without
# competing for the LLM gateway rate limit.
#
# Usage: ./tools/run_pipeline.sh [--wait-for items_descs]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p catalog

# ---- wait for an in-flight translation job (optional) ----
WAIT_FOR="${1:-items_descs}"
if [ -n "$WAIT_FOR" ]; then
    echo "=== waiting for in-flight job: $WAIT_FOR ==="
    while pgrep -f "$WAIT_FOR" >/dev/null 2>&1; do
        sleep 60
    done
    echo "=== in-flight job finished ==="
fi

run_surface() {
    local name="$1" catalog="$2" surface="$3"
    echo "===== [$name] translate ====="
    python3 tools/translate.py \
        --catalog "catalog/$catalog.jsonl" \
        --out "catalog/${catalog}_ja.jsonl" \
        --batch 100 --pace 15 --surface "$surface" --dedupe
    echo "===== [$name] normalize ====="
    python3 tools/normalize_ja.py "catalog/${catalog}_ja.jsonl" --in-place || true
    echo "===== [$name] consistency ====="
    python3 tools/fix_consistency.py "catalog/${catalog}_ja.jsonl" --in-place || true
    echo "===== [$name] done ====="
}

# surface registry: catalog | surface | repo file (for apply)
run_surface "skills" "skills" "skill"
run_surface "datainfo (pets/titles/help)" "datainfo" "items"   # items surface includes monsters glossary for pet names
run_surface "systemen (quests/achiev/navi)" "systemen" "quest"
run_surface "text tables (maps/cards/quests)" "texttables" "plain"
run_surface "books" "books" "book"

echo
echo "=== ALL SURFACES TRANSLATED ==="
echo "Applying to repo files (dry-run to /tmp/apply-all)..."
python3 tools/apply.py --all --out-dir /tmp/apply-all 2>&1 | tail -20
echo
echo "Run tools/apply.py --all to write into the repo, then commit."
