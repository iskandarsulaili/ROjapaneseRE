# ROjapaneseRE — Japanese Translation Project Plan

Fork of [ROenglishRE](https://github.com/llchrisll/ROenglishRE) — an unofficial
Korean Ragnarok Online (kRO) translation project. ROjapaneseRE translates the
entire client surface to **Japanese** instead of English.

## Goal

A complete, drop-in Japanese translation pack for kRO Renewal (and Pre-Renewal
compatibility), matching the scope and quality bar of ROenglishRE: items,
skills, quests, monsters, pets, NPC dialogue, client UI strings, books, and
textures — all rendered in proper Japanese.

## Repo layout (inherited from ROenglishRE)

```
Translation/Renewal/        main translation (items/skills/quests/UI/textures)
Translation/Pre-Renewal/    pre-renewal variant (mirrors Renewal structure)
Translation/Compatibility/  per-client-date override patches
Additions/                  extra data + SystemEN additions
Addons/                     optional addon packs (jRO Enchants Display, etc.)
Tools/                      translation helper tooling
```

## Translation surface (measured, 2026-08-14)

| Surface | Files | Strings (est.) | Notes |
|---|---|---|---|
| items (SystemEN/LuaFiles514/itemInfo.lua) | 3 | ~435,800 | 26,656 items; names + descriptions |
| system lub (quests/achievements/navi/towninfo) | 7 | ~55,200 | OngoingQuests.lub alone is 3 MB |
| datainfo lub (pets/titles/help/enchants) | 4 | ~1,000 | |
| skillinfoz lub (skill names/descriptions) | 4 | ~29,200 | |
| misc lua files | 26 | ~35,400 | signboards, stateicons, etc. |
| msgstringtable.txt (client UI strings) | 1 | ~4,000 | in-game system messages |
| books (data/book/*.txt) | 70 | ~15,000 | readable books |
| text tables (map names, card prefixes, monster talk) | 78 | ~5,000 | |
| texture images (buttons, UI art) | 502 | — | image translation (manual) |
| Additions + Addons + Compatibility | 161 | ~393,000 | includes English/jRO extras |
| **TOTAL** | **~856** | **~980,000** | |

## Encoding model (CRITICAL — do not change without re-reading this)

- Source files are ANSI multi-byte (CP949 Korean). The pipeline treats all
  files as **bytes** (latin-1 as a lossless bytes-as-chars carrier).
- Translated output is encoded **cp932 (Shift-JIS)** — the standard encoding
  for Japanese Windows ANSI codepage and Japanese RO clients.
- **Sprite/resource filenames** (`개_포링.bmp`, `*_XXXXX.act`) MUST remain
  byte-identical — the client resolves them against the kRO data.grf. The
  extractor auto-skips any string ending in .bmp/.act/.spr/.gat/.gnd/.rsw/
  .tga/.wav/.ogg/.mp3/.xml/.txt/.pal.
- Non-translated content (code structure, comments, keys, numerics) is
  preserved byte-for-byte by the rebuild.
- Formatting tokens (`^RRGGBB..^000000`, `%d`, `%s`, `[Lv N]`,
  `_______________________` separator lines, `Weight : X`, `Type:`, etc.)
  must be preserved in translations.

## Translation pipeline

```
tools/catalog.py extract --out catalog/items.jsonl Translation/.../itemInfo.lua
   -> JSONL: {"file","path":[...],"en":"...","ja":null}
   (translator/MT fills "ja")
tools/catalog.py rebuild <file> --catalog catalog/items.jsonl --out <newfile> --encoding cp932
   -> byte-exact rebuild with Japanese strings
```

- `tools/inventory.py` — per-surface inventory report (strings/bytes).
- Catalogs live in `catalog/` (gitignored until a bulk commit is ready).
- Rebuild validates: translated file must differ from source ONLY on
  translated lines (automated check in CI/test).

## Translation approach — two tracks

### Track A: glossary + terminology database (foundation)
Build a `data/glossary.json` mapping canonical RO terms EN->JA:
- Item names (ポリン/Poring, サラマンダー/Salamander, etc.)
- Job/class names, skill names
- Status/bonus terms, elemental names
- Consistent honorifics/particles for item descriptions
- jRO official terms where available (jRO was an official server; its
  official item names are the gold standard — e.g. use jRO's own translations
  for items that existed there, which is much of the catalog)

Current glossary: 705 terms (world/monsters/items/classes/stats/combat/ui/
common + 137 high-frequency item-name tokens covering 45% of item-name
tokens).

### Translation throughput (measured 2026-08-14)
- Batch 10, pace 12s: ~26 strings/min (too slow)
- Batch 30, pace 10s: ~60 strings/min
- Batch 100, pace 15s: ~200 strings/min  ← CURRENT STANDARD
- The omniRoute gateway (:20128) rate-limits aggressively (405 on burst);
  curl subprocess + 15s pacing + retries is the working recipe. urllib gets
  WAF-rejected (405) — always use curl for LLM calls.
- Resume support: `--out` checkpoint is merged on restart, so interrupted
  runs continue without re-translating.

### Track B: bulk translation by surface, in priority order
1. msgstringtable.txt (client UI — small, high visibility)
2. itemInfo.lua item NAMES (26k items — most impactful)
3. itemInfo.lua descriptions (longest tail)
4. skillinfoz (skill names + descriptions)
5. datainfo (pets, titles, enchants)
6. system lub (quests/achievements/navi/towninfo)
7. books + text tables
8. textures (image assets — manual image editing)
9. Additions/Addons/Compatibility
10. Pre-Renewal mirror + per-client-date compatibility patches

Bulk translation is done via the LLM translation tier (see tools/translate.py)
with the glossary as constraint; every string is reviewed against the
glossary, and format tokens are enforced by a validator that refuses
translations that drop `^color^000000` / `%s` / `%d` tokens or `[Lv N]`
markers.

## Texture strategy

502 images (mostly Korean-label UI buttons: btn_use_a.bmp, etc.). Options:
- Ship JP-labeled bitmap replacements (best quality; manual/GIMP work)
- The kRO client loads fonts from System/Font (SCDream4.otf/SCDream6.otf) —
  a JP font drop-in under those exact filenames makes ALL text (including
  translated strings) render correctly. This is required regardless of
  texture work.
- Priority: fonts first (unlocks everything), then core UI buttons.

## Font coverage (CRITICAL FINDING, 2026-08-14)

Analyzed the kRO client fonts (System/Font):
- SCDream4.otf / SCDream6.otf (13,494 glyphs each):
  - Hiragana: 25/25 ✓  Katakana: 25/25 ✓
  - Kanji: only 4/17 (日本語翻訳項目武 all MISSING)
  - Full-width: 5/7 (・ー missing)
- The .eot UI fonts (NHCgogo_10.eot etc.) are a non-standard EOT flavor
  (not parseable by fonttools) — presumed Korean-only like the OTFs.

**Implication: the default kRO fonts CANNOT render most kanji.** Japanese
translations with common kanji (武器, 魔法, 翻訳) would show as tofu (□)
without a font fix. The font drop-in (replacing System/Font files with a
JP-capable font, or adding one) is a HARD prerequisite, not optional.

Strategy: ship a JP-capable font under the client's expected filenames in
the System/Font folder (e.g. replace SCDream4/6.otf with a JP OTF, or add
the font the client falls back to). Verify on the user's Windows test
machine: launch client with a translated msgstringtable + JP font, confirm
kanji renders. This is the first on-client verification milestone.

## Compatibility patches

- Per-client-date dirs (2015-10-29aRagexe ... 2026-01-07 Ragexe) contain
  client-specific SystemEN/data overrides. Each needs the same treatment as
  the main tree. Automated: the pipeline runs per tree.
- `Translation/Compatibility/*/SystemEN` — new clients read SystemEN;
  older clients read data/. Both must be kept in sync.

## Quality gates

1. **Byte-safety**: rebuild is byte-exact on non-translated lines (test).
2. **Token integrity**: no dropped `^color^000000` / `%d` / `%s` / `[Lv N]`.
3. **Glossary conformance**: term lookups resolve through glossary.json.
4. **Lua validity**: rebuilt .lub/.lua parse (luac -p or lua -e loadfile).
5. **Encoding**: output files decode cleanly as cp932 with no unmapped chars.
6. **Field skips**: sprite names, resource keys, numeric/struct fields never
   touched (extractor guarantee + rebuild test).

## Upstream sync

`git remote add upstream https://github.com/llchrisll/ROenglishRE.git`
Sync: `git fetch upstream && git merge upstream/master` — translation files
are ours; tooling/structural changes merge cleanly (keep tooling in tools/,
catalogs in catalog/).

## Roadmap

- [x] Fork + metadata (2026-08-14)
- [x] Toolchain: catalog extract/rebuild (byte-safe, cp932) + inventory
- [x] Glossary v1 (705 EN->JA canonical terms, 45% item-name token coverage)
- [x] msgstringtable.txt (4,012 strings) — **100% translated** (2026-08-14)
- [x] Item names (26,641) — **100% translated** (2026-08-14), luac-validated
- [x] Item descriptions (294,483 lines) — **100% translated** (2026-08-14), luac-validated
- [x] Skills (28,970 entries) — **100% translated** (2026-08-15), luac-validated
- [x] Pets/titles/help (397) — **100% translated** (2026-08-15)
- [x] Quests/achievements/navi (39,866 entries) — **100% translated** (2026-08-15), luac-validated
- [x] Text tables (11,056) — **100% translated** (2026-08-15)
- [x] Books (13,606) — **100% translated** (2026-08-15)
- [ ] Textures (502 images) — image asset translation (manual/GIMP)
- [ ] Additions/Addons/Compatibility + Pre-Renewal mirror
- [ ] Test on client (JP font + rendered Japanese)

## Notes

- README.md should eventually describe the JP project + setup docs link.
- The parent repo has 331 stars / 229 forks; our fork is a derivative
  fan-translation project — keep the "unofficial/educational" framing and
  credits to zackdreaver + llchrisll in file headers (already present).
- jRO official translations (from jRO data/official grfs) are the highest
  quality reference — the ROenglishRE repo already contains jRO-derived
  strings (Addons/jRO Enchants Display etc.) that can be reused directly.
