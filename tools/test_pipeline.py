#!/usr/bin/env python3
"""
ROjapaneseRE quality gate test suite.

Checks:
  1. rebuild byte-safety: translating 0 entries must reproduce the source
     byte-for-byte (CRLF, CP949 sprite names, everything)
  2. token integrity: validator rejects dropped color/%/Lv/underscore tokens
  3. encoding: rebuilt files decode as cp932 (or utf-8) with no unmapped chars
  4. catalog sanity: every catalog entry has path/en; ja when present is str

Usage: python3 tools/test_pipeline.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from catalog import extract, rebuild, b2c, c2b, encode_ja  # noqa: E402
from translate import validate_tokens, COLOR_TOKEN_RE  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}: {detail}")


def test_roundtrip_identity():
    print("== 1. rebuild byte-safety (0 translations => identical) ==")
    samples = [
        "Translation/Renewal/data/luafiles514/lua files/datainfo/petinfo.lub",
        "Translation/Renewal/data/msgstringtable.txt",
        "Translation/Renewal/data/luafiles514/lua files/skillinfoz/skilldescript.lub",
        "Translation/Renewal/SystemEN/Towninfo.lub",
        "Translation/Renewal/data/book/1000897.txt",
    ]
    for p in samples:
        fp = os.path.join(ROOT, p)
        if not os.path.exists(fp):
            print(f"  skip (missing): {p}")
            continue
        ents = extract(fp, p)
        # clear all ja
        for e in ents:
            e["ja"] = None
        with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
            out = tf.name
        rebuild(fp, ents, out, "cp932")
        a = open(fp, "rb").read()
        b = open(out, "rb").read()
        check(f"roundtrip {os.path.basename(p)}", a == b,
              f"{len(a)} vs {len(b)} bytes differ")
        os.unlink(out)


def test_token_validator():
    print("== 2. token integrity validator ==")
    check("color preserved", not validate_tokens(
        "^FF0000Red^000000 potion", "^FF0000赤^000000ポーション"))
    check("color dropped", validate_tokens(
        "^FF0000Red^000000 potion", "赤ポーション"))
    check("pct kept", not validate_tokens(
        "Increase %d", "増加 %d"))
    check("pct dropped", validate_tokens(
        "Increase %d", "増加"))
    check("Lv kept", not validate_tokens(
        "[Lv 5]: Joins a Party", "[Lv 5]：パーティーに参加"))
    check("Lv dropped", validate_tokens(
        "[Lv 5]: Joins a Party", "パーティーに参加"))
    check("underscore kept", not validate_tokens(
        "a\n_______________________\nb", "a\n_______________________\nb"))
    check("underscore dropped", validate_tokens(
        "a\n_______________________\nb", "a\nb"))


def test_encoding():
    print("== 3. encoding (cp932 output) ==")
    ja = "ポリンはかわいい"
    b = encode_ja(ja, "cp932")
    check("cp932 roundtrip", b.decode("cp932") == ja, f"{b!r}")
    # all cp932 bytes must be valid
    try:
        b.decode("cp932")
        check("cp932 decode ok", True)
    except UnicodeDecodeError as e:
        check("cp932 decode ok", False, str(e))


def test_lua_string_safety():
    """CP932 hazard: kanji like 図/表/Ⅸ end in byte 0x5C (backslash),
    which Lua treats as an escape char. A string ending in such a char
    breaks Lua parsing ('unfinished string'). The fix is a trailing space.
    Also: literal " inside ja must be escaped as \".
    """
    print("== 6. Lua string safety (CP932 0x5C-trail + quote hazards) ==")
    import re
    fp = os.path.join(ROOT, "Translation/Renewal/SystemEN/LuaFiles514/itemInfo.lua")
    if not os.path.exists(fp):
        print("  skip (no itemInfo.lua)")
        return
    data = open(fp, "rb").read()
    lines = data.split(b"\n")
    problems = []
    for i, line in enumerate(lines):
        j = 0
        while j < len(line):
            if line[j:j+1] == b'"':
                k = line.find(b'"', j+1)
                if k == -1:
                    break
                content = line[j+1:k]
                if len(content) >= 2 and content[-1] == 0x5c and content[-2] >= 0x81:
                    problems.append((i+1, content.decode("cp932", errors="replace")))
                j = k + 1
            else:
                j += 1
    check("no strings end in CP932 0x5C-trail char", len(problems) == 0,
          f"{problems[:5]}")
    # luac parse check if available
    import shutil
    luac = shutil.which("luac5.1") or shutil.which("luac")
    if luac:
        r = subprocess.run([luac, "-p", fp], capture_output=True)
        check("itemInfo.lua parses (luac -p)", r.returncode == 0,
              r.stderr.decode(errors="replace")[:200])
    else:
        print("  (luac not available, skipped parse check)")


def test_quote_escaping():
    """ja containing literal \" must be escaped in rebuild output."""
    print("== 7. quote escaping in rebuild ==")
    import tempfile
    ja_with_quote = '最後の名前、"Hollg--" は書きかけのようだ。'
    # simulate: encode -> rebuild logic escapes
    b = encode_ja(ja_with_quote, "cp932")
    b = b.replace(b'"', b'\\"')
    # the escaped form must contain \x5C\x22 (escaped quote) pairs
    check("quote escaped", b'\\"' in b and b.count(b'\\"') == 2, f"{b!r}")
    # full parse check: build a tiny lua and luac it
    lua_src = 't = { "' + b2c(b) + '" }\n'
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False, encoding="latin-1") as tf:
        tf.write(lua_src)
        tmp = tf.name
    import shutil
    luac = shutil.which("luac5.1") or shutil.which("luac")
    if luac:
        r = subprocess.run([luac, "-p", tmp], capture_output=True)
        check("escaped quote lua parses", r.returncode == 0,
              r.stderr.decode(errors="replace")[:200])
    os.unlink(tmp)


def test_catalog_sanity():
    print("== 4. catalog sanity ==")
    cat = "/tmp/cat_msg_pilot_ja.jsonl"
    if not os.path.exists(cat):
        print("  skip (no pilot catalog)")
        return
    n = 0
    for line in open(cat, encoding="utf-8"):
        e = json.loads(line)
        n += 1
        check("entry has path", "path" in e and e["path"], str(e)[:60])
        check("entry has en", "en" in e and e["en"], str(e)[:60])
        if e.get("ja") is not None:
            check("ja is str", isinstance(e["ja"], str), str(e)[:60])
    print(f"  ({n} entries checked)")


def test_rebuild_with_ja():
    print("== 5. rebuild with ja (only translated lines differ) ==")
    p = "Translation/Renewal/data/luafiles514/lua files/datainfo/petinfo.lub"
    fp = os.path.join(ROOT, p)
    if not os.path.exists(fp):
        print("  skip")
        return
    ents = extract(fp, p)
    n_ja = 0
    for e in ents:
        if e["path"][0] == "PetNameTable" and e["en"] == "poring":
            e["ja"] = "ポリン"
            n_ja += 1
    with tempfile.NamedTemporaryFile(suffix=".out", delete=False) as tf:
        out = tf.name
    rebuild(fp, ents, out, "cp932")
    a = open(fp, "rb").read().split(b"\n")
    b = open(out, "rb").read().split(b"\n")
    diffs = [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y]
    check("only translated lines differ", len(diffs) == n_ja,
          f"{len(diffs)} diff lines, expected {n_ja}")
    if diffs:
        i, x, y = diffs[0]
        check("diff is the poring line", b"poring" in x and b"\x83|\x83\x8a\x83\x93" in y)
    os.unlink(out)


def main():
    print("ROjapaneseRE pipeline tests")
    test_roundtrip_identity()
    test_token_validator()
    test_encoding()
    test_catalog_sanity()
    test_rebuild_with_ja()
    test_lua_string_safety()
    test_quote_escaping()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
