# ROjapaneseRE — Japanese Translation Conventions

This document records the conventions, terminology sources, and style rules
used for the Japanese translation. It is the reference for both LLM-driven
bulk translation and any human review.

## Terminology sources (priority order)

1. **Official jRO (Gungho)** — the gold standard. jRO was an official
   Japanese server with official translations for most classic content.
   - https://rotool.gungho.jp/ (official item/monster tool)
   - https://ragnaplace.com/ja/jro/ (jRO database mirror)
2. **ROenglishRE jRO-derived strings** — the repo's Addons/jRO Enchants
   Display and other jRO-sourced data.
3. **JP MMORPG convention** — for content that never existed on jRO
   (newer kRO-only items), use natural JP game terminology.

## Confirmed official jRO terms (verified 2026-08-14)

| EN | jRO |
|---|---|
| Poring | ポリン |
| Poring Card | ポリンカード |
| Knife [3] | ナイフ [3] |
| Sword Wing | ソードウィング |
| Red Potion | レッドポーション |
| Creator | クリエイター |
| Clown | クラウン |
| Paladin | パラディン |
| Champion | チャンピオン |
| Professor | プロフェッサー |
| Stalker | チェイサー |
| Sura | 修羅 |
| Kagerou | 影狼 |
| Oboro | 朧 |
| (Card prefix) Lucky | ラッキー |

## Style rules

### Item names
- Use official jRO name when the item existed on jRO.
- Roman numerals: full-width (Ⅱ/Ⅲ/Ⅳ/Ⅴ) — NOT ASCII (II/III) or kanji.
- Equipment slots: Upper = 上段, Mid = 中段, Lower = 下段.
- Shadow equipment: Shadow = シャドウ (kept as-is, e.g. シャドウアーマー).
- Costume = 衣装 (e.g. 衣装ハット), NOT コスチューム for item names.
- Prefixes like [Event], [Blank], [2021] are preserved as-is.
- (null) stays (null).

### Item description labels (^CCClabel:^000000)
- Weight → 重量, Type → 種類, Requirement → 必要職業, Position → 装備位置
- Armor Level → 防具レベル, Defense → 防御力, Attack → 攻撃力
- Weapon Level → 武器レベル, Compound on → 装着部位, Refineable → 精錬可能
- Effect → 効果, Heal → 回復量, Duration → 持続時間, Cooldown → クールタイム
- Cast → 詠唱時間, Required Level → 要求レベル, Level Limit → レベル制限

### Client UI (msgstringtable)
- Formal/imperative Japanese (です/ます体, してください).
- Keep slash-commands (/navi, /where, /h) and %-formats verbatim.
- Server = サーバー, Password = パスワード, Character = キャラクター,
  Guild = ギルド, Zeny = ゼニー.

### Skills
- Passive = パッシブ, Active = アクティブ.
- Max Level = 最大レベル, Cast Time = 詠唱時間, Cooldown = クールタイム.
- [Lv N] markers preserved.

### Quests / achievements
- Natural polite narrative Japanese (です/ます体).
- Map names from the world glossary (プロンテラ, ゲフェン, etc.).
- Quest titles: short, noun-phrase style.

### Books
- Literary narrative style; keep line structure.

## Format tokens (MUST preserve in every translation)

- `^RRGGBBtext^000000` — color spans (keep the exact codes)
- `%d %s %f %lld` — format specifiers (keep order)
- `[Lv N]` — level markers
- `_______________________` — separator lines (keep length ~23)
- `#` — record delimiters in .txt tables
- Slash commands and URLs — verbatim

## Encoding

- Output: Shift-JIS (cp932) — Japanese Windows ANSI codepage.
- Sprite filenames (.bmp/.act/.spr) and resource keys: NEVER translated.
- The pipeline is byte-safe: only translated strings change.

## Fonts

kRO client default fonts (SCDream4/6.otf) have hiragana/katakana but NOT
most kanji. The JP font drop-in (Additions/JP Fonts, IPA Gothic) is
required for kanji to render. See Additions/JP Fonts/System/Font/README.
