#!/usr/bin/env bash
# ROjapaneseRE translation runner — sequential surface translation.
# Usage: ./tools/translate_surfaces.sh [--only msg|items|skills|...]
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p catalog

run_surface() {
    local name="$1" catalog="$2" surface="$3" batch="$4" pace="$5"
    echo "=== translating $name ($surface) ==="
    python3 tools/translate.py \
        --catalog "catalog/$catalog.jsonl" \
        --out "catalog/${catalog}_ja.jsonl" \
        --batch "$batch" --pace "$pace" --surface "$surface"
    echo "=== done $name ==="
}

ONLY="${1:-all}"

if [ "$ONLY" = "all" ] || [ "$ONLY" = "msg" ]; then
    run_surface "msgstringtable" "msgstringtable" "msg" 100 15
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "items" ]; then
    run_surface "item names" "items_names" "items" 100 15
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "skills" ]; then
    run_surface "skills" "skills" "skill" 100 15
fi

echo "All requested surfaces done."
