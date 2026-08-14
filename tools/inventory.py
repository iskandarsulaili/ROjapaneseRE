#!/usr/bin/env python3
"""
ROjapaneseRE inventory tool.

Scans the repo for translatable content and reports per-surface string counts.
Surfaces:
  - SystemEN/LuaFiles514/itemInfo.lua     (item names + descriptions)
  - SystemEN/*.lub                        (quests, achievements, navi, towninfo, ...)
  - data/luafiles514/lua files/datainfo/*.lub  (pets, titles, help, enchants, ...)
  - data/luafiles514/lua files/skillinfoz/*.lub (skills)
  - data/luafiles514/lua files/*.lub      (signboards, misc)
  - data/msgstringtable.txt               (client UI strings)
  - data/book/*.txt                       (in-game books)
  - data/*.txt / *.xml tables             (map names, card prefixes, monster talk, ...)
  - data/texture/**/*.bmp/.tga            (image assets - manual work)
  - Additions/ + Addons/ + Compatibility/ (extras)

Usage: python3 tools/inventory.py [--json out.json]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')

def count_lua_strings(path):
    """Count quoted strings in a text Lua file, skipping comment lines."""
    n = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.lstrip().startswith("--"):
                continue
            n += len(STRING_RE.findall(line))
    return n

def count_msgstring(path):
    n = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line.endswith("#") and line != "#":
                n += 1
    return n

def count_book(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)

def main():
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]

    report = {"surfaces": [], "totals": {}}
    totals = {"files": 0, "strings": 0, "bytes": 0}

    def add_surface(name, path, count_fn, file_glob):
        base = os.path.join(ROOT, path)
        if not os.path.isdir(base):
            return
        files = []
        for dp, _, fns in os.walk(base):
            for fn in fns:
                if fn.endswith(file_glob):
                    files.append(os.path.join(dp, fn))
        files.sort()
        strings = bytes_ = 0
        for fp in files:
            try:
                c = count_fn(fp)
            except Exception:
                c = 0
            strings += c
            bytes_ += os.path.getsize(fp)
        entry = {
            "surface": name,
            "files": len(files),
            "strings": strings,
            "bytes": bytes_,
            "path": path,
        }
        report["surfaces"].append(entry)
        totals["files"] += len(files)
        totals["strings"] += strings
        totals["bytes"] += bytes_

    add_surface("items (itemInfo)", "Translation/Renewal/SystemEN/LuaFiles514", count_lua_strings, ".lua")
    add_surface("system lub (quests/achiev/navi/...)", "Translation/Renewal/SystemEN", count_lua_strings, ".lub")
    add_surface("datainfo lub", "Translation/Renewal/data/luafiles514/lua files/datainfo", count_lua_strings, ".lub")
    add_surface("skillinfoz lub", "Translation/Renewal/data/luafiles514/lua files/skillinfoz", count_lua_strings, ".lub")
    add_surface("lua files (misc)", "Translation/Renewal/data/luafiles514/lua files", count_lua_strings, ".lub")
    add_surface("msgstringtable", "Translation/Renewal/data", count_msgstring, "msgstringtable.txt")
    add_surface("books", "Translation/Renewal/data/book", count_book, ".txt")
    add_surface("text tables (map/card/monster)", "Translation/Renewal/data", count_lua_strings, ".txt")
    add_surface("texture images", "Translation/Renewal/data/texture", lambda p: 0, ".bmp")
    add_surface("Additions", "Additions", count_lua_strings, ".lub")
    add_surface("Addons", "Addons", count_lua_strings, ".lub")
    add_surface("Compatibility", "Translation/Compatibility", count_lua_strings, ".lub")

    # also count .xml tables separately (monster talk etc.)
    xml_strings = 0
    for fn in ("monstertalktable.xml", "pettalktable.xml", "monsterskillinfo.xml"):
        fp = os.path.join(ROOT, "Translation/Renewal/data", fn)
        if os.path.exists(fp):
            with open(fp, encoding="utf-8", errors="replace") as f:
                xml_strings += sum(1 for line in f if "<message" in line or "<desc" in line or ">" in line)
    report["surfaces"].append({
        "surface": "xml talk tables", "files": 3, "strings": xml_strings,
        "bytes": 0, "path": "Translation/Renewal/data/*.xml",
    })

    report["totals"] = totals
    report["grand_total_strings_est"] = totals["strings"] + xml_strings

    if out_json:
        with open(out_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"wrote {out_json}")
    else:
        print(f"{'surface':<42} {'files':>6} {'strings':>9} {'bytes':>12}")
        print("-" * 74)
        for e in report["surfaces"]:
            print(f"{e['surface']:<42} {e['files']:>6} {e['strings']:>9} {e['bytes']:>12,}")
        print("-" * 74)
        print(f"{'TOTAL':<42} {totals['files']:>6} {totals['strings']:>9} {totals['bytes']:>12,}")
        print(f"estimated grand total strings (incl. xml): {report['grand_total_strings_est']:,}")

if __name__ == "__main__":
    main()
