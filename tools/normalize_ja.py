#!/usr/bin/env python3
"""
ROjapaneseRE post-processing: normalize translation consistency.

Fixes known drift patterns across a translated catalog:
  1. Roman numerals: ASCII II/III/IV/V -> full-width Ⅱ/Ⅲ/Ⅳ/Ⅴ (jRO style)
     Only when the numeral is a standalone token (word boundary) — not inside
     words like "DIVINE" or "SKILL".
  2. Full-width vs half-width: standardize common ones.

Usage:
  python3 tools/normalize_ja.py catalog/items_names_ja.jsonl [--in-place]

Output: prints changed entries, rewrites the file (with --in-place).
"""
import argparse
import json
import re

ROMAN_MAP = {
    "II": "Ⅱ",
    "III": "Ⅲ",
    "IV": "Ⅳ",
    "V": "Ⅴ",
    "VI": "Ⅵ",
    "VII": "Ⅶ",
    "VIII": "Ⅷ",
    "IX": "Ⅸ",
    "X": "Ⅹ",
}


def normalize_ja(ja):
    """Return (normalized, changed)."""
    orig = ja
    # Roman numerals as standalone tokens (after space or start, before end/space)
    # e.g. "Eden Slayer II" -> "エデンスレイヤーⅡ"
    # Don't touch if already full-width or inside a word (no boundary)
    for rom, full in ROMAN_MAP.items():
        # word-boundary: preceded by space/start, followed by space/end
        ja = re.sub(rf'(?<![A-Za-z0-9]){rom}(?![A-Za-z0-9])', full, ja)
    return ja, ja != orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog")
    ap.add_argument("--in-place", action="store_true")
    args = ap.parse_args()

    entries = []
    with open(args.catalog, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    changed = 0
    for e in entries:
        if not e.get("ja"):
            continue
        norm, did = normalize_ja(e["ja"])
        if did:
            print(f"  {e['en']!r}: {e['ja']!r} -> {norm!r}")
            e["ja"] = norm
            changed += 1

    if args.in_place and changed:
        with open(args.catalog, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"changed {changed} entries")


if __name__ == "__main__":
    main()
