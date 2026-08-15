#!/usr/bin/env python3
"""
ROjapaneseRE catalog tool: extract translatable strings from ROenglishRE
files into a JSONL translation catalog, and rebuild translated files from it.

ENCODING MODEL (critical):
  - Source files are ANSI multi-byte (CP949 for kRO Korean resources).
  - The pipeline treats every file as BYTES and uses latin-1 as a lossless
    "bytes-as-chars" representation internally, so no byte is ever corrupted.
  - The ja (Japanese) output is encoded with --encoding (default: cp932,
    a.k.a. Shift-JIS - the standard encoding for Japanese RO clients and
    Japanese Windows ANSI codepage).
  - Strings whose ja is null/identical are left byte-identical.

Supported formats:
  - text Lua (.lua / .lub): string values inside tables
  - msgstringtable.txt:     one "message#" per line
  - plain text (.txt):      raw prose (books, tables) - one entry per line

Catalog entry (JSONL):
  {"file": relpath, "path": [...], "en": "<latin1-escaped>", "ja": null}

Usage:
  python3 tools/catalog.py extract --out catalog.jsonl <file>...
  python3 tools/catalog.py rebuild <original-file> --catalog catalog.jsonl \
      --out <output-file> [--encoding cp932|utf-8]
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
TABLE_OPEN_RE = re.compile(r'^\s*(?:\[([^\]]+)\]|\w+)\s*=\s*\{\s*$')
TABLE_CLOSE_RE = re.compile(r'^\s*\},?\s*$')
FIELD_STRING_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$')
KEYED_STRING_RE = re.compile(r'^\s*\["?([^"\]]+)"?\]\s*=\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$')
BARE_STRING_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$')

# Fields that are not translation targets (sprite names, numeric/struct data)
NON_TRANSLATABLE_FIELDS = {
    "Server", "ClassNum", "slotCount", "costume", "ViewSprite", "Sprite",
    "unidentifiedResourceName", "identifiedResourceName",
    "resourceName", "ResourceName",
}

# Heuristic: values that look like file/resource paths are never translated
RESOURCE_RE = re.compile(r'\.(bmp|act|spr|gat|gnd|rsw|tga|wav|ogg|mp3|xml|txt|pal)$', re.I)


def b2c(data: bytes) -> str:
    """bytes -> latin-1 str (1:1 lossless)."""
    return data.decode("latin-1")


def c2b(s: str) -> bytes:
    return s.encode("latin-1")


def encode_ja(s: str, encoding: str) -> bytes:
    """Encode a Japanese string for output; latin-1 fallback for ASCII-only."""
    try:
        return s.encode(encoding)
    except UnicodeEncodeError:
        # mixed content that can't be fully encoded -> emit latin-1-safe as-is
        return s.encode("latin-1", errors="replace")


def strip_escapes(s):
    return s.replace('\\"', '"').replace("\\\\", "\\")


def restore_escapes(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


class LuaScanner:
    """Line-based scanner that records (path, field, en) for every string value."""

    def __init__(self, relpath):
        self.relpath = relpath
        self.entries = []
        self.stack = []
        self.array_counter = []

    def _push(self, key):
        self.stack.append(key)
        self.array_counter.append(0)

    def _pop(self):
        if self.stack:
            self.stack.pop()
            self.array_counter.pop()

    def _add(self, field, en, lineno):
        if field in NON_TRANSLATABLE_FIELDS:
            return
        if RESOURCE_RE.search(en):
            return
        self.entries.append({
            "file": self.relpath,
            "path": list(self.stack) + [field],
            "en": strip_escapes(en),
            "ja": None,
            "line": lineno,
        })

    def scan_line(self, line, lineno):
        stripped = line.strip()
        if stripped.startswith("--"):
            return
        m = TABLE_OPEN_RE.match(line)
        if m:
            key = m.group(1) if m.group(1) else stripped.split("=")[0].strip()
            self._push(key)
            return
        m = TABLE_CLOSE_RE.match(line)
        if m:
            self._pop()
            return
        m = FIELD_STRING_RE.match(line)
        if m:
            self._add(m.group(1), m.group(2), lineno)
            return
        m = KEYED_STRING_RE.match(line)
        if m:
            self._add(m.group(1), m.group(2), lineno)
            return
        m = BARE_STRING_RE.match(line)
        if m:
            idx = self.array_counter[-1] if self.array_counter else 0
            if self.array_counter:
                self.array_counter[-1] += 1
            self._add(str(idx), m.group(1), lineno)
            return


def extract_lua(path, relpath):
    scanner = LuaScanner(relpath)
    with open(path, "rb") as f:
        data = f.read()
    for i, line in enumerate(b2c(data).split("\n"), 1):
        scanner.scan_line(line.rstrip("\r"), i)
    return scanner.entries


def extract_msgstring(path, relpath):
    entries = []
    with open(path, "rb") as f:
        data = f.read()
    for i, line in enumerate(b2c(data).split("\n"), 1):
        line = line.rstrip("\r")
        if line.endswith("#") and line != "#":
            entries.append({
                "file": relpath,
                "path": ["msgstringtable", str(i)],
                "en": line[:-1],
                "ja": None,
                "line": i,
            })
    return entries


def extract_plain(path, relpath):
    entries = []
    with open(path, "rb") as f:
        data = f.read()
    for i, line in enumerate(b2c(data).split("\n"), 1):
        line = line.rstrip("\r")
        if line.strip():
            entries.append({
                "file": relpath,
                "path": ["line", str(i)],
                "en": line,
                "ja": None,
                "line": i,
            })
    return entries


# Hash-delimited tables: key#Display Name# (mapnametable, cardprefix, questid2display)
HASH_DELIMITED_TABLES = {
    "mapnametable.txt", "cardprefixnametable.txt", "cardpostfixnametable.txt",
    "questid2display.txt",
}


def extract_hash_delimited(path, relpath):
    """Extract only the display-name fields of #-delimited records.

    Format: field1#field2#field3# ... — fields that are NOT the leading key
    (id/rsw) and not trailing structural fields get translated. The leading
    key and structural fields (like SG_FEEL, QUE_NOIMAGE) stay untouched.
    """
    entries = []
    with open(path, "rb") as f:
        data = f.read()
    for i, line in enumerate(b2c(data).split("\n"), 1):
        line = line.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        parts = line.split("#")
        if len(parts) < 2:
            continue
        # fields to translate: everything except index 0 (key) and trailing
        # structural markers (ALL_CAPS tokens, *_* codes)
        for fi, part in enumerate(parts):
            if fi == 0:
                continue
            if not part.strip():
                continue
            # skip structural tokens: all-caps w/ underscore, or *.rsw etc.
            if re.fullmatch(r"[A-Z0-9_]+", part):
                continue
            if part.endswith((".rsw", ".gat", ".gnd")):
                continue
            entries.append({
                "file": relpath,
                "path": ["hashline", str(i), str(fi)],
                "en": part,
                "ja": None,
                "line": i,
            })
    return entries


def extract(path, relpath):
    name = os.path.basename(path).lower()
    if name.endswith((".lub", ".lua")):
        return extract_lua(path, relpath)
    if name == "msgstringtable.txt":
        return extract_msgstring(path, relpath)
    if name in HASH_DELIMITED_TABLES:
        return extract_hash_delimited(path, relpath)
    if name.endswith(".txt"):
        return extract_plain(path, relpath)
    return []


# ----------------------------- rebuild ----------------------------------

def rebuild_lua(path, catalog, out_path, encoding):
    """Rewrite string values byte-safely using the catalog (path+en keyed)."""
    lookup = {}
    for e in catalog:
        lookup[(json.dumps(e["path"]), e["en"])] = e.get("ja") or e["en"]

    with open(path, "rb") as f:
        data = f.read()
    raw_lines = data.split(b"\n")  # keep trailing \r inside each line

    scanner = LuaScanner(os.path.relpath(path, ROOT))
    per_line = []  # list of list[(path, en)] per line, in scan order
    for line in raw_lines:
        sline = line.decode("latin-1").rstrip("\r")
        before = len(scanner.entries)
        scanner.scan_line(sline, 0)
        per_line.append([(e["path"], e["en"]) for e in scanner.entries[before:]])

    out = []
    for line, ents in zip(raw_lines, per_line):
        text = line.decode("latin-1")
        sline = text.rstrip("\r")
        cr = "\r" if text.endswith("\r") else ""
        if not ents:
            out.append(text)
            continue

        def repl(m):
            nonlocal ents
            if not ents:
                return m.group(0)
            path, en = ents.pop(0)
            ja = lookup.get((json.dumps(path), en))
            if ja is None:
                # en-key mismatch (escape variants): try the stripped form
                ja = lookup.get((json.dumps(path), strip_escapes(en)))
            if ja is None or ja == en:
                return m.group(0)
            ja_bytes = encode_ja(ja, encoding)
            # CP932 hazard: if the encoded string ends in 0x5C as a trail
            # byte (e.g. 図/表/Ⅸ), append a trailing space so Lua doesn't
            # treat it as an escape before the closing quote.
            if len(ja_bytes) >= 2 and ja_bytes[-1] == 0x5c and ja_bytes[-2] >= 0x81:
                ja_bytes += b" "
            # Quote hazard: ja may contain literal " (from EN strings that had
            # escaped quotes, e.g. "Hollg--" or \"%hi\"). Work at the BYTE level
            # with even-backslash awareness so CP932 trail bytes (0x5C) are
            # never mistaken for escapes: only a " whose preceding backslash
            # run is EVEN gets escaped (odd run means it was already escaped).
            out_bytes = bytearray()
            bs = 0
            for b in ja_bytes:
                if b == 0x5c:
                    bs += 1
                    out_bytes.append(b)
                elif b == 0x22:
                    if bs % 2 == 0:
                        out_bytes.append(0x5c)
                    out_bytes.append(b)
                    bs = 0
                else:
                    bs = 0
                    out_bytes.append(b)
            ja_bytes = bytes(out_bytes)
            return '"' + b2c(ja_bytes) + '"'

        out.append(STRING_RE.sub(repl, sline) + cr)

    with open(out_path, "wb") as f:
        f.write(c2b("\n".join(out)))


def rebuild_msgstring(path, catalog, out_path, encoding):
    lookup = {e["path"][1]: e.get("ja") or e["en"] for e in catalog}
    with open(path, "rb") as f:
        data = f.read()
    raw_lines = data.split(b"\n")
    out = []
    for i, raw in enumerate(raw_lines, 1):
        text = raw.decode("latin-1")
        line = text.rstrip("\r")
        cr = "\r" if text.endswith("\r") else ""
        if line.endswith("#") and line != "#":
            ja = lookup.get(str(i))
            if ja and ja != line[:-1]:
                out.append(b2c(encode_ja(ja, encoding)) + "#" + cr)
            else:
                out.append(line + cr)
        else:
            out.append(text)
    with open(out_path, "wb") as f:
        f.write(c2b("\n".join(out)))


def rebuild_plain(path, catalog, out_path, encoding):
    lookup = {e["path"][1]: e.get("ja") or e["en"] for e in catalog}
    with open(path, "rb") as f:
        data = f.read()
    raw_lines = data.split(b"\n")
    out = []
    for i, raw in enumerate(raw_lines, 1):
        text = raw.decode("latin-1")
        line = text.rstrip("\r")
        cr = "\r" if text.endswith("\r") else ""
        if line.strip():
            ja = lookup.get(str(i))
            if ja and ja != line:
                out.append(b2c(encode_ja(ja, encoding)) + cr)
            else:
                out.append(text)
        else:
            out.append(text)
    with open(out_path, "wb") as f:
        f.write(c2b("\n".join(out)))


def rebuild_hash_delimited(path, catalog, out_path, encoding):
    """Rebuild a #-delimited table, translating only extracted display fields.

    Catalog paths are ["hashline", line_no, field_idx] — field_idx is the
    0-based #-split index. Keys (index 0) and structural fields stay as-is.
    """
    lookup = {}
    for e in catalog:
        if e["path"][0] == "hashline":
            lookup[(int(e["path"][1]), int(e["path"][2]))] = e.get("ja") or e["en"]
    with open(path, "rb") as f:
        data = f.read()
    raw_lines = data.split(b"\n")
    out = []
    for i, raw in enumerate(raw_lines, 1):
        text = raw.decode("latin-1")
        line = text.rstrip("\r")
        cr = "\r" if text.endswith("\r") else ""
        if line and not line.lstrip().startswith("//") and "#" in line:
            parts = line.split("#")
            for fi in range(1, len(parts)):
                ja = lookup.get((i, fi))
                if ja and ja != parts[fi]:
                    parts[fi] = b2c(encode_ja(ja, encoding))
            out.append("#".join(parts) + cr)
        else:
            out.append(text)
    with open(out_path, "wb") as f:
        f.write(c2b("\n".join(out)))


def rebuild(path, catalog, out_path, encoding):
    name = os.path.basename(path).lower()
    if name.endswith((".lub", ".lua")):
        rebuild_lua(path, catalog, out_path, encoding)
    elif name == "msgstringtable.txt":
        rebuild_msgstring(path, catalog, out_path, encoding)
    elif name in HASH_DELIMITED_TABLES:
        rebuild_hash_delimited(path, catalog, out_path, encoding)
    elif name.endswith(".txt"):
        rebuild_plain(path, catalog, out_path, encoding)
    else:
        raise SystemExit(f"unsupported format: {path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("files", nargs="+")
    ex.add_argument("--out", required=True)
    rb = sub.add_parser("rebuild")
    rb.add_argument("file")
    rb.add_argument("--catalog", required=True)
    rb.add_argument("--out", required=True)
    rb.add_argument("--encoding", default="cp932")
    args = ap.parse_args()

    if args.cmd == "extract":
        all_entries = []
        for fp in args.files:
            relpath = os.path.relpath(fp, ROOT)
            entries = extract(fp, relpath)
            all_entries.extend(entries)
            print(f"{relpath}: {len(entries)} strings", file=sys.stderr)
        with open(args.out, "w", encoding="utf-8") as f:
            for e in all_entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"wrote {len(all_entries)} entries -> {args.out}")
    elif args.cmd == "rebuild":
        catalog = []
        with open(args.catalog, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    catalog.append(json.loads(line))
        rebuild(args.file, catalog, args.out, args.encoding)
        print(f"rebuilt -> {args.out}")


if __name__ == "__main__":
    main()
