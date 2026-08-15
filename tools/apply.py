#!/usr/bin/env python3
"""
ROjapaneseRE apply script — rebuild repo translation files from translated
catalogs.

The catalog entries carry their source file (e["file"]), so apply groups
entries by file and rebuilds each. This handles multi-file surfaces
(skills = 4 lub, systemen = 7 lub, texttables = 4 txt, books = 70 txt).

Usage:
  python3 tools/apply.py --catalog catalog/items_names_ja.jsonl
  python3 tools/apply.py --all [--out-dir /path/to/output] [--encoding cp932]
"""
import argparse
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from catalog import rebuild  # noqa: E402

# surface registry: catalog_name -> note
SURFACES = {
    "msgstringtable": "client UI messages",
    "items_names": "item names (already applied to itemInfo.lua)",
    "items_descs": "item descriptions (already applied to itemInfo.lua)",
    "skills": "skill names + descriptions",
    "datainfo": "pets/titles/help",
    "systemen": "quests/achievements/navi",
    "texttables": "map names/card prefixes/quest display",
    "books": "in-game books",
}


def load_catalog(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def apply_one(cat_path, out_dir, encoding):
    entries = load_catalog(cat_path)
    by_file = defaultdict(list)
    for e in entries:
        by_file[e["file"]].append(e)

    n_ja = sum(1 for e in entries if e.get("ja"))
    print(f"  {cat_path}: {n_ja} ja entries across {len(by_file)} files")

    for relpath, file_entries in sorted(by_file.items()):
        src = os.path.join(ROOT, relpath)
        if not os.path.exists(src):
            print(f"    SKIP (no source): {relpath}")
            continue
        if out_dir:
            out = os.path.join(out_dir, relpath)
            os.makedirs(os.path.dirname(out), exist_ok=True)
        else:
            out = src
        rebuild(src, file_entries, out, encoding)
        print(f"    applied -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", help="translated catalog JSONL")
    ap.add_argument("--all", action="store_true", help="apply all registered surfaces")
    ap.add_argument("--out-dir", default="", help="output dir (default: in place)")
    ap.add_argument("--encoding", default="cp932")
    args = ap.parse_args()

    if args.all:
        for name, note in SURFACES.items():
            cat = os.path.join(ROOT, "catalog", f"{name}_ja.jsonl")
            if not os.path.exists(cat):
                print(f"  SKIP (no catalog): {name}")
                continue
            print(f"== {name} ({note}) ==")
            apply_one(cat, args.out_dir, args.encoding)
    elif args.catalog:
        apply_one(args.catalog, args.out_dir, args.encoding)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
