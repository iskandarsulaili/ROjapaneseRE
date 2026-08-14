#!/usr/bin/env python3
"""
ROjapaneseRE consistency fixer — resolve drift after batch translation.

For each EN string translated multiple ways, pick the WINNER (most frequent
translation, tie-broken by glossary preference) and apply it to all
occurrences. This collapses the 3% drift the batch LLM produces.

Usage:
  python3 tools/fix_consistency.py catalog/items_names_ja.jsonl [--in-place]

Winner selection:
  1. Most frequent ja
  2. Tie-break: prefer the ja that uses glossary terms (Box=箱, etc.)
  3. Tie-break: prefer the shorter ja (item names)
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

# Glossary preference: substrings that signal a preferred translation
PREFERRED_TERMS = [
    "箱",          # Box (over ボックス)
    "レッドポーション",  # official names
]


def pick_winner(jas):
    """Pick the winning translation from a set."""
    counts = Counter(jas)
    max_count = max(counts.values())
    top = [j for j, c in counts.items() if c == max_count]
    if len(top) == 1:
        return top[0]
    # tie-break 1: glossary preference
    for pref in PREFERRED_TERMS:
        hits = [t for t in top if pref in t]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            top = hits
    # tie-break 2: shorter
    return min(top, key=len)


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

    # group translations by EN
    by_en = defaultdict(list)
    for e in entries:
        if e.get("ja"):
            by_en[e["en"]].append(e["ja"])

    # find winners for inconsistent ENs
    fixes = {}
    for en, jas in by_en.items():
        distinct = set(jas)
        if len(distinct) > 1:
            fixes[en] = pick_winner(distinct)

    print(f"inconsistent ENs: {len(fixes)}")
    changed = 0
    for e in entries:
        if e.get("ja") and e["en"] in fixes and e["ja"] != fixes[e["en"]]:
            print(f"  {e['en']!r}: {e['ja']!r} -> {fixes[e['en']]!r}")
            e["ja"] = fixes[e["en"]]
            changed += 1

    if args.in_place and changed:
        with open(args.catalog, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"changed {changed} entries")


if __name__ == "__main__":
    main()
