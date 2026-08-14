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
    echo "=== normalizing $name ==="
    python3 tools/normalize_ja.py "catalog/${catalog}_ja.jsonl" --in-place || true
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

if [ "$ONLY" = "all" ] || [ "$ONLY" = "datainfo" ]; then
    run_surface "datainfo (pets/titles/help)" "datainfo" "plain" 100 15
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "systemen" ]; then
    run_surface "systemen (quests/achiev/navi)" "systemen" "quest" 100 15
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "texttables" ]; then
    run_surface "text tables (maps/cards/quests)" "texttables" "plain" 100 15
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "books" ]; then
    run_surface "books" "books" "book" 100 15
fi

echo "All requested surfaces done."
