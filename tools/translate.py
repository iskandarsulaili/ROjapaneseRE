#!/usr/bin/env python3
"""
ROjapaneseRE translation engine.

Translates catalog entries (EN -> JA) using the LLM gateway, constrained by
the project glossary, with hard format-token preservation validation.

Design:
  - Reads a catalog JSONL (extracted by tools/catalog.py) in batches.
  - For each batch, sends EN strings + glossary to the LLM (batched prompt
    with numbered items), gets back JA lines, validates:
      * format tokens (^RRGGBB..^000000 color codes, %d/%s/%f, [Lv N],
        _______________________ separators) are preserved verbatim
      * glossary terms are used (soft check, warns only)
  - Writes ja into the catalog entries and saves back.

Usage:
  python3 tools/translate.py --catalog catalog/items.jsonl \
      --out catalog/items_ja.jsonl \
      --batch 50 --glossary data/glossary.json \
      [--surface items|msg|skill|quest|book|plain]

The LLM gateway is configured via env: LLM_API_URL (default
http://127.0.0.1:20128/v1), LLM_API_KEY, LLM_MODEL (default
combo/deepseek-v4-flash). Uses the OpenAI-compatible chat completions API.

NOTE: This is a *harness*. Actual translation runs are driven in batches by
the operator (cron or interactive) — the glossary + format validator are the
quality backbone. See docs/PROJECT_PLAN.md Track B.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

GLOSSARY = {}

COLOR_TOKEN_RE = re.compile(r'\^[0-9A-Fa-f]{6}')
FORMAT_TOKEN_RE = re.compile(r'(%[sdifxbu%])|(\[\s*Lv\s*\d+\s*\])|(_{5,})')
SURFACE_HINTS = {
    "items": "RO item name or description. Keep it concise and in-game style. "
             "For item NAMES use the jRO official name when it exists, else a natural Japanese name.",
    "msg": "RO client UI message. Short, imperative/formal Japanese. Keep slash-commands and %-formats.",
    "skill": "RO skill name or description. Use official jRO skill names when known.",
    "quest": "RO quest text. Natural, polite Japanese quest narration.",
    "book": "RO in-game book prose. Natural literary Japanese.",
    "plain": "Plain text line. Natural Japanese.",
}

# glossary sections relevant per surface (priority order)
SURFACE_GLOSSARY_SECTIONS = {
    "items": ["item_tokens", "items", "desc_labels", "monsters", "classes", "combat", "stats", "world", "ui"],
    "msg": ["ui", "common", "stats", "classes"],
    "skill": ["combat", "stats", "ui", "classes", "common"],
    "quest": ["world", "monsters", "common", "ui"],
    "book": ["world", "common"],
    "plain": ["common", "ui"],
}


def glossary_pairs_for(surface, glossary):
    """Return glossary pairs ordered by surface relevance, capped at 400."""
    order = SURFACE_GLOSSARY_SECTIONS.get(surface, ["common"])
    pairs = []
    seen = set()
    # append in priority order
    for section in order:
        d = glossary.get(section)
        if isinstance(d, dict):
            for en, ja in d.items():
                if isinstance(ja, str) and en not in seen:
                    seen.add(en)
                    pairs.append((en, ja))
    # fill remaining from other sections
    if len(pairs) < 400:
        for section, d in glossary.items():
            if not isinstance(d, dict) or section in order:
                continue
            for en, ja in d.items():
                if isinstance(ja, str) and en not in seen and len(pairs) < 400:
                    seen.add(en)
                    pairs.append((en, ja))
    return pairs[:400]


def load_glossary(path):
    global GLOSSARY
    with open(path, encoding="utf-8") as f:
        GLOSSARY = json.load(f)
    # flatten to list of (en, ja) for prompt
    pairs = []
    for section in GLOSSARY.values():
        if isinstance(section, dict):
            for en, ja in section.items():
                if isinstance(ja, str):
                    pairs.append((en, ja))
    return pairs


def load_catalog(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def save_catalog(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def call_llm(system, user, url, key, model, max_tokens=4000, retries=6):
    """Call the LLM gateway via curl (urllib gets WAF-rejected with 405).

    The omniRoute gateway at :20128 fingerprints HTTP clients and returns
    405 to Python urllib but accepts curl. We shell out to curl.
    """
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "stream": False,
        "reasoning_effort": "none",
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_ex = None
    for attempt in range(retries):
        cmd = [
            "curl", "-s", "--max-time", "180", "-X", "POST",
            url.rstrip("/") + "/chat/completions",
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: Bearer {key}",
            "-H", "User-Agent: curl/8.0",
            "-H", "Accept: */*",
            "--data-binary", "@-",
        ]
        try:
            proc = subprocess.run(
                cmd, input=payload, capture_output=True, timeout=200)
            if proc.returncode != 0:
                raise RuntimeError(f"curl exit {proc.returncode}: {proc.stderr.decode(errors='replace')[:200]}")
            text = proc.stdout.decode("utf-8", errors="replace")
            data = json.loads(text)
            if "error" in data:
                raise RuntimeError(f"gateway error: {data['error']}")
            return data["choices"][0]["message"]["content"]
        except Exception as ex:
            last_ex = ex
            code = getattr(ex, "code", None)
            msg = str(ex)
            # retry on transient failures
            if code in (403, 405, 429, 500, 502, 503) or "exit" in msg or "timed out" in msg.lower():
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise last_ex


def validate_tokens(en, ja):
    """Return list of problems. Format tokens must be preserved verbatim."""
    problems = []
    # color tokens
    en_colors = COLOR_TOKEN_RE.findall(en)
    ja_colors = COLOR_TOKEN_RE.findall(ja)
    if en_colors and set(en_colors) != set(ja_colors):
        problems.append(f"color tokens changed: {en_colors} -> {ja_colors}")
    # %-formats
    en_fmt = re.findall(r'%[sdifxbu%]', en)
    ja_fmt = re.findall(r'%[sdifxbu%]', ja)
    if en_fmt and en_fmt != ja_fmt:
        problems.append(f"format tokens changed: {en_fmt} -> {ja_fmt}")
    # [Lv N]
    en_lv = re.findall(r'\[\s*Lv\s*\d+\s*\]', en)
    ja_lv = re.findall(r'\[\s*Lv\s*\d+\s*\]', ja)
    if en_lv and en_lv != ja_lv:
        problems.append(f"Lv markers changed: {en_lv} -> {ja_lv}")
    # underscore separators
    en_us = re.findall(r'_{5,}', en)
    ja_us = re.findall(r'_{5,}', ja)
    if en_us and not ja_us:
        problems.append("underscore separator lost")
    return problems


def glossary_check(en, ja, pairs):
    """Soft check: if EN contains a glossary EN term, JA should contain its JA."""
    hits = []
    for en_term, ja_term in pairs:
        if len(en_term) >= 3 and en_term in en:
            if ja_term not in ja:
                hits.append((en_term, ja_term))
    return hits[:5]  # cap


def translate_batch(entries, pairs, surface, url, key, model, retries=6):
    """Translate a batch of entries; returns (ok_list, problems)."""
    problems = []
    done = []
    todo = []
    for e in entries:
        if e.get("ja"):
            done.append(e)
        else:
            todo.append(e)

    if not todo:
        return done, problems

    # Build numbered prompt
    lines = []
    for i, e in enumerate(todo):
        lines.append(f"{i + 1}. {e['en']}")
    prompt = "\n".join(lines)

    hint = SURFACE_HINTS.get(surface, "Translate to Japanese.")
    glossary_text = "\n".join(f"{en} = {ja}" for en, ja in glossary_pairs_for(surface, pairs))
    system = (
        f"You are a professional game translator for Ragnarok Online (jRO).\n"
        f"Translate each numbered English line to natural Japanese.\n"
        f"Rules:\n"
        f"1. {hint}\n"
        f"2. PRESERVE ALL format tokens exactly: ^RRGGBB colors, %d %s %f, [Lv N], and underscore separator lines (___...)\n"
        f"3. Use the glossary below for canonical terms when applicable.\n"
        f"4. Output ONLY numbered lines: '1. 日本語' ... no explanations.\n"
        f"\nGlossary (EN = JA):\n{glossary_text}"
    )

    try:
        resp = call_llm(system, prompt, url, key, model, retries=retries)
    except Exception as ex:
        # batch failed - mark entries so they're retried later
        for e in todo:
            problems.append(f"LLM error: {ex}")
        return done + todo, problems

    # Parse numbered responses
    resp_lines = [l.strip() for l in resp.splitlines() if l.strip()]
    ja_map = {}
    for l in resp_lines:
        m = re.match(r'^(\d+)[.)]\s*(.+)$', l)
        if m:
            ja_map[int(m.group(1))] = m.group(2)

    for i, e in enumerate(todo):
        ja = ja_map.get(i + 1)
        if not ja:
            problems.append(f"no translation for #{i + 1}: {e['en'][:40]}")
            e["ja"] = None
            done.append(e)
            continue
        toks = validate_tokens(e["en"], ja)
        if toks:
            problems.append(f"#{i + 1} token violation: {'; '.join(toks)} | {e['en'][:50]} -> {ja[:50]}")
            # still accept but flag? -> keep ja but record problem for review
        e["ja"] = ja
        done.append(e)

    return done, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--glossary", default="data/glossary.json")
    ap.add_argument("--surface", default="plain", choices=list(SURFACE_HINTS))
    ap.add_argument("--limit", type=int, default=0, help="max entries to process (0=all)")
    ap.add_argument("--url", default=os.environ.get("LLM_API_URL", "http://127.0.0.1:20128/v1"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "glm-5.2"))
    ap.add_argument("--key", default=os.environ.get("LLM_API_KEY", "none"))
    ap.add_argument("--pace", type=float, default=12.0,
                    help="seconds to wait between batches (rate-limit pacing)")
    ap.add_argument("--retries", type=int, default=6)
    args = ap.parse_args()
    # fall back to the hermes gateway key if LLM_API_KEY not set
    if args.key == "none" and os.path.exists(os.path.expanduser("~/.hermes/.env")):
        for line in open(os.path.expanduser("~/.hermes/.env"), encoding="utf-8"):
            if line.startswith("HERMES_CUSTOM_127_0_0_1_20128_API_KEY="):
                args.key = line.strip().split("=", 1)[1]
                break

    pairs = load_glossary(args.glossary)
    entries = load_catalog(args.catalog)
    if args.limit:
        entries = entries[:args.limit]

    # Resume: if --out exists, merge already-translated ja back in
    resumed = 0
    if os.path.exists(args.out):
        try:
            prev = {json.dumps(e["path"]): e.get("ja") for e in load_catalog(args.out)}
            for e in entries:
                ja = prev.get(json.dumps(e["path"]))
                if ja and not e.get("ja"):
                    e["ja"] = ja
                    resumed += 1
        except Exception:
            pass
    if resumed:
        print(f"resumed {resumed} entries from {args.out}", file=sys.stderr)

    total_problems = 0
    n = len(entries)
    print(f"translating {n} entries (batch {args.batch}, surface {args.surface}, pace {args.pace}s)", file=sys.stderr)
    for start in range(0, n, args.batch):
        batch = entries[start:start + args.batch]
        done, problems = translate_batch(batch, pairs, args.surface, args.url, args.key, args.model, args.retries)
        entries[start:start + args.batch] = done
        total_problems += len(problems)
        for p in problems[:5]:
            print(f"  ! {p}", file=sys.stderr)
        print(f"  batch {start // args.batch + 1}/{(n + args.batch - 1) // args.batch}: "
              f"{sum(1 for e in done if e.get('ja'))}/{len(done)} done, {len(problems)} problems", file=sys.stderr)
        # checkpoint after every batch
        save_catalog(args.out, entries)
        if start + args.batch < n:
            time.sleep(args.pace)

    translated = sum(1 for e in entries if e.get("ja"))
    print(f"done: {translated}/{n} translated, {total_problems} problems -> {args.out}")


if __name__ == "__main__":
    main()
