#!/usr/bin/env bash
# ROjapaneseRE client pack assembler.
#
# Builds a Client/ folder (data-folder override pack) from the translated
# Translation tree, mirroring Tools/ClientGenerator.bat but cross-platform.
#
# Usage: ./tools/build_client.sh [client_date] [mode]
#   client_date: e.g. 2025-09-02 (default: 2025-09-02)
#   mode: renewal|pre-renewal (default: renewal)
#
# Output: Client/ in repo root (gitignored).
set -euo pipefail
cd "$(dirname "$0")/.."

CLIENT_DATE="${1:-2025-09-02}"
MODE="${2:-renewal}"
OUT="Client"

echo "=== ROjapaneseRE client pack: $MODE @ $CLIENT_DATE ==="

rm -rf "$OUT"
mkdir -p "$OUT"

# 1. Base translation tree
if [ "$MODE" = "pre-renewal" ]; then
    # Pre-Renewal overlays Renewal (per upstream docs)
    cp -r Translation/Renewal/. "$OUT/"
    cp -r Translation/Pre-Renewal/. "$OUT/"
else
    cp -r Translation/Renewal/. "$OUT/"
fi

# 2. Compatibility patch for the client date
COMPAT="Translation/Compatibility/$CLIENT_DATE"
if [ -d "$COMPAT" ]; then
    if [ -d "$COMPAT/$MODE" ]; then
        cp -r "$COMPAT/$MODE/." "$OUT/"
    else
        cp -r "$COMPAT/." "$OUT/"
    fi
    echo "applied compatibility $CLIENT_DATE"
else
    echo "WARN: no compatibility dir for $CLIENT_DATE"
fi

# 3. Additions
if [ -d Additions/data ]; then
    cp -r Additions/data/. "$OUT/data/" 2>/dev/null || true
fi
if [ -d Additions/SystemEN ]; then
    mkdir -p "$OUT/SystemEN"
    cp -r Additions/SystemEN/. "$OUT/SystemEN/"
fi

# 4. JP fonts drop-in (critical: kanji rendering)
mkdir -p "$OUT/System/Font"
if [ -f "Additions/JP Fonts/System/Font/ipag.ttf" ]; then
    cp "Additions/JP Fonts/System/Font/ipag.ttf" "$OUT/System/Font/SCDream4.otf"
    cp "Additions/JP Fonts/System/Font/ipagp.ttf" "$OUT/System/Font/SCDream6.otf"
    cp "Additions/JP Fonts/System/Font/ipag.ttf" "$OUT/System/Font/NHCgogo_10.eot"
    cp "Additions/JP Fonts/System/Font/ipag.ttf" "$OUT/System/Font/NHCgogo_12.eot"
    echo "installed JP fonts (SCDream4/6 + NHCgogo drop-ins)"
fi

# 5. clientinfo.xml pointing at our server (keep upstream's if present)
if [ -f "$OUT/data/clientinfo.xml" ]; then
    echo "clientinfo.xml present (check server address before distributing)"
fi

echo
echo "=== Pack built at $OUT ==="
du -sh "$OUT" 2>/dev/null || true
find "$OUT" -type f | wc -l | xargs echo "files:"
echo
echo "To distribute: zip the Client folder, or use the repo's GRF tooling."
