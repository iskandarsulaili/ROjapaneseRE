# Ragnarok Online 日本語翻訳プロジェクト (ROjapaneseRE)

An unofficial **Japanese** translation project for Korea Ragnarok Online (kRO),
forked from [ROenglishRE](https://github.com/llchrisll/ROenglishRE).

This project translates the kRO Renewal client (and Pre-Renewal
compatibility) into Japanese: **items, skills, quests, monsters, pets, NPC
dialogue, client UI strings, books, and textures** — everything ROenglishRE
covers, but in Japanese instead of English.

## Status

🚧 Active development. The toolchain is complete; bulk translation is in
progress surface by surface. See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)
for the roadmap and current progress.

## What's translated so far

| Surface | Status |
|---|---|
| Client UI strings (msgstringtable.txt) | ✅ 100% (4,012 strings) |
| Items — names | ✅ 100% (26,641 items) |
| Items — descriptions | ✅ 100% (294,483 lines) |
| Skills | 🔄 In progress (19,220 unique) |
| Quests / achievements / navi | ⏳ Queued |
| Pets / titles / enchants | ⏳ Queued |
| Books | ⏳ Queued |
| Textures | Planned |

## Setup / usage

The translation pipeline works on the repo's data files directly:

```bash
# Extract translatable strings from a file into a JSONL catalog
python3 tools/catalog.py extract --out catalog/msg.jsonl \
    Translation/Renewal/data/msgstringtable.txt

# Translate catalog entries EN->JA (LLM-assisted, glossary-constrained)
python3 tools/translate.py --catalog catalog/msg.jsonl \
    --out catalog/msg_ja.jsonl --surface msg

# Rebuild the translated file (byte-safe, Shift-JIS output)
python3 tools/catalog.py rebuild Translation/Renewal/data/msgstringtable.txt \
    --catalog catalog/msg_ja.jsonl --out Translation/Renewal/data/msgstringtable.txt

# Run quality-gate tests
python3 tools/test_pipeline.py
```

Output files are encoded **Shift-JIS (cp932)** — the standard for Japanese
Windows and Japanese RO clients. Sprite/resource filenames and all
non-translated content are preserved byte-for-byte.

## Credits

- Original translation works of zackdreaver: https://github.com/zackdreaver/ROenglishRE
- Continued by llchrisll at https://github.com/llchrisll/ROenglishRE
- jRO official data (Gungho) used as terminology reference
- This fork: iskandarsulaili/ROjapaneseRE

This is an unofficial fan-translation project for educational purposes only.
Any commercial or illegal use is not the responsibility of the authors.

## Related

- [RO Translation Project - Discord](https://discord.gg/sagbPhH)
- [ROTP Docs](https://llchrisll.github.io/ROTPDocs)
