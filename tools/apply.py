#!/usr/bin/env python3
"""
ROjapaneseRE apply script — rebuild repo translation files from translated
catalogs.

For each (source_file, catalog) pair, rebuild the source with the translated
catalog, producing a Japanese file in place (or to --out-dir).

Usage:
  python3 tools/apply.py --catalog catalog/items_names_ja.jsonl \
      --file "Translation/Renewal/SystemEN/LuaFiles514/itemInfo.lua" \
      [--out-dir /path/to/output] [--encoding cp932]

  # apply ALL registered surfaces
  python3 tools/apply.py --all [--out-dir ...]
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from catalog import rebuild  # noqa: E402

# surface registry: catalog_name -> (repo file, note)
SURFACES = {
    "msgstringtable": (
        "Translation/Renewal/data/msgstringtable.txt",
        "client UI messages",
    ),
    "items_names": (
        "Translation/Renewal/SystemEN/LuaFiles514/itemInfo.lua",
        "item names (and descriptions once translated)",
    ),
    "skills": (
        "Translation/Renewal/data/luafiles514/lua files/skillinfoz/skilldescript.lub",
        "skill descriptions",
    ),
    "datainfo": (
        "Translation/Renewal/data/luafiles514/lua files/datainfo/petinfo.lub",
        "pets/titles/help",
    ),
    "systemen": (
        "Translation/Renewal/SystemEN/OngoingQuests.lub",
        "quests/achievements/navi",
    ),
}


def load_catalog(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def apply_one(cat_path, src_rel, out_dir, encoding):
    src = os.path.join(ROOT, src_rel)
    if not os.path.exists(src):
        print(f"  SKIP (no source): {src_rel}")
        return
    ents = load_catalog(cat_path)
    n_ja = sum(1 for e in ents if e.get("ja"))
    if out_dir:
        out = os.path.join(out_dir, src_rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
    else:
        out = src
    rebuild(src, ents, out, encoding)
    print(f"  applied {cat_path} ({n_ja} ja) -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", help="translated catalog JSONL")
    ap.add_argument("--file", help="repo file to rebuild (relative)")
    ap.add_argument("--all", action="store_true", help="apply all registered surfaces")
    ap.add_argument("--out-dir", default="", help="output dir (default: in place)")
    ap.add_argument("--encoding", default="cp932")
    args = ap.parse_args()

    if args.all:
        for name, (src_rel, note) in SURFACES.items():
            cat = os.path.join(ROOT, "catalog", f"{name}_ja.jsonl")
            if not os.path.exists(cat):
                print(f"  SKIP (no catalog): {name}")
                continue
            print(f"== {name} ({note}) ==")
            apply_one(cat, src_rel, args.out_dir, args.encoding)
    elif args.catalog and args.file:
        apply_one(args.catalog, args.file, args.out_dir, args.encoding)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
