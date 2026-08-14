#!/usr/bin/env python3
"""
ROjapaneseRE consistency checker.

Detects inconsistent translations: the same English string translated
differently in different places (across a catalog or between catalogs).

This matters because batch LLM translation can produce drift — e.g. "Red
Potion" -> レッドポーション in one batch but 赤ポーション in another.

Usage:
  python3 tools/check_consistency.py catalog/items_names_ja.jsonl [more.jsonl...]

Output: groups of (en, [different ja]) sorted by frequency, plus a summary.
"""
import json
import sys
from collections import defaultdict


def load(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return
    en_to_ja = defaultdict(set)  # en -> set of distinct ja
    for p in paths:
        for e in load(p):
            en = e.get("en")
            ja = e.get("ja")
            if en and ja and en != ja:
                en_to_ja[en].add(ja)

    # find inconsistent ones
    inconsistent = {en: jas for en, jas in en_to_ja.items() if len(jas) > 1}
    print(f"checked {len(en_to_ja)} distinct EN strings")
    print(f"inconsistent: {len(inconsistent)} ({len(inconsistent)*100//max(len(en_to_ja),1)}%)")
    print()
    # sort by total occurrence
    ranked = sorted(inconsistent.items(), key=lambda kv: -sum(1 for _ in kv[1]))
    for en, jas in ranked[:40]:
        print(f"  {en!r}")
        for j in sorted(jas):
            print(f"      -> {j!r}")


if __name__ == "__main__":
    main()
