#!/usr/bin/env python3
"""
ROjapaneseRE texture translator — replace Korean text labels on UI button
bitmaps with Japanese.

The kRO UI buttons (btn_*.bmp) carry Korean labels baked into the pixels.
ROenglishRE never translated these; we render Japanese text over the text
region using a JP font, preserving the button's frame/background.

Formats handled:
  - 24bpp RGBA BMP (real buttons: btn_agree.bmp etc.)
  - 8bpp paletted BMP (templates: btn_ok.bmp; text often absent/in palette)

Strategy per button: clear the detected dark-text bounding box, re-render
the Japanese label centered, using the same text color and the button's
sampled background color.

Usage:
  python3 tools/texture_translate.py [--dry-run] [--dir <texture dir>]
"""
import argparse
import json
import os
import struct
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# English label -> Japanese. Derived from the btn_* filename meanings and
# official jRO UI terminology.
BTN_JA = {
    "ok": "確認",
    "cancel": "キャンセル",
    "close": "閉じる",
    "buy": "購入",
    "sell": "売却",
    "use": "使用",
    "make": "作成",
    "learn": "習得",
    "send": "送信",
    "add": "追加",
    "del": "削除",
    "edit": "編集",
    "find": "検索",
    "list": "リスト",
    "memo": "メモ",
    "back": "戻る",
    "next": "次へ",
    "info": "情報",
    "help": "ヘルプ",
    "help2": "ヘルプ",
    "view": "表示",
    "write": "書く",
    "sort": "並べ替え",
    "restart": "再起動",
    "rewrite": "書き直し",
    "friend": "フレンド",
    "feed": "餌やり",
    "exchange": "交換",
    "agree": "同意",
    "disagree": "不同意",
    "apply": "適用",
    "reset": "リセット",
    "reply": "返信",
    "get": "受け取る",
    "charge": "チャージ",
    "refresh": "更新",
    "skill": "スキル",
    "shortcut": "ショートカット",
    "emotion": "感情表現",
    "intro": "紹介",
    "big_ok": "確認",
    "big_cancel": "キャンセル",
    "big_next": "次へ",
    "big_change": "変更",
    "big_unused": "未使用",
    "big_used": "使用中",
    "cancel_res": "キャンセル",
    "del_res": "削除",
    "disband": "解散",
    "fired": "解雇",
    "q_active": "受注中",
    "q_inactive": "未受注",
    "friend": "フレンド",
    "join": "参加",
    "array": "整列",
    "prev": "前へ",
    "deposit": "預ける",
    "withdraw": "引き出す",
    "create": "作成",
    "receive": "受け取る",
    "delete": "削除",
    "delete_cancel": "削除キャンセル",
    "delete_reserve": "削除予約",
    "close_out": "閉じる",
    "close_over": "閉じる",
    "close_press": "閉じる",
}

# Font: prefer IPA Gothic (full kanji). Fall back to any JP font.
def find_jp_font():
    candidates = [
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # search common font dirs
    for root, dirs, files in os.walk("/usr/share/fonts"):
        for f in files:
            if f.lower().endswith((".ttf", ".ttc", ".otf")):
                fp = os.path.join(root, f)
                try:
                    ImageFont.truetype(fp, 11)
                    return fp
                except Exception:
                    continue
    return None


def load_bmp(path):
    """Return (PIL Image RGBA, original bytes, is_paletted)."""
    data = open(path, "rb").read()
    if len(data) < 54:
        return None, data, False
    bpp = struct.unpack("<H", data[28:30])[0]
    img = Image.open(path).convert("RGBA")
    return img, data, (bpp == 8)


def detect_text_region(img):
    """Find the dark-text bounding box on a button (or None)."""
    px = img.load()
    w, h = img.size
    min_x, max_x, min_y, max_y = w, -1, h, -1
    count = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            # dark text pixels (Korean glyphs) on light button bg
            if a > 200 and r < 90 and g < 90 and b < 90:
                min_x = min(min_x, x); max_x = max(max_x, x)
                min_y = min(min_y, y); max_y = max(max_y, y)
                count += 1
    if count < 10:
        return None
    return (min_x, min_y, max_x, max_y)


def sample_bg(img, region):
    """Sample the button background color near the text region."""
    px = img.load()
    w, h = img.size
    x0, y0, x1, y1 = region
    # sample a ring just outside the text bbox
    samples = []
    for x in range(max(0, x0 - 3), min(w, x1 + 4)):
        for y in (max(0, y0 - 2), min(h - 1, y1 + 2)):
            r, g, b, a = px[x, y]
            if a > 100 and not (r < 90 and g < 90 and b < 90):
                samples.append((r, g, b))
    for y in range(max(0, y0 - 3), min(h, y1 + 4)):
        for x in (max(0, x0 - 2), min(w - 1, x1 + 2)):
            r, g, b, a = px[x, y]
            if a > 100 and not (r < 90 and g < 90 and b < 90):
                samples.append((r, g, b))
    if not samples:
        return (219, 219, 219, 255)
    c = Counter(samples).most_common(1)[0][0]
    return (c[0], c[1], c[2], 255)


def text_color(img, region):
    """Most common dark color in the text region."""
    px = img.load()
    x0, y0, x1, y1 = region
    dark = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            r, g, b, a = px[x, y]
            if a > 200 and r < 90 and g < 90 and b < 90:
                dark.append((r, g, b))
    if not dark:
        return (49, 49, 49, 255)
    c = Counter(dark).most_common(1)[0][0]
    return (c[0], c[1], c[2], 255)


def render_button(img, region, label, font_path, text_size=11):
    """Clear text region, render Japanese label centered. Returns new RGBA img."""
    work = img.copy()
    draw = ImageDraw.Draw(work)
    x0, y0, x1, y1 = region
    bg = sample_bg(img, region)
    tc = text_color(img, region)

    # clear with margin
    draw.rectangle([max(0, x0 - 1), max(0, y0 - 1), min(img.size[0] - 1, x1 + 1),
                    min(img.size[1] - 1, y1 + 1)], fill=bg)

    font = ImageFont.truetype(font_path, text_size)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # center in the ORIGINAL text region (gives natural button-center position)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    tx = cx - tw // 2 - bbox[0]
    ty = cy - th // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=tc)
    return work


def save_bmp(img_rgba, orig_bytes, path):
    """Save preserving format: 8bpp -> keep palette-ish (quantize), 24bpp -> RGB."""
    bpp = struct.unpack("<H", orig_bytes[28:30])[0]
    if bpp == 8:
        # quantize to palette to keep 8bpp
        out = img_rgba.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        out.save(path, "BMP")
    else:
        out = img_rgba.convert("RGB")
        out.save(path, "BMP")


def label_for(filename):
    """Map btn_*.bmp filename to Japanese label (strip _a/_b/_c suffix)."""
    base = filename
    if base.endswith(".bmp"):
        stem = base[:-4]  # strip .bmp
        for suf in ("_dis", "_a", "_b", "_c", "_disable", "_out", "_over", "_press"):
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
                break
        if stem.startswith("btn_"):
            key = stem[4:].strip()
            if key in BTN_JA:
                return BTN_JA[key]
    return None


def process_dir(texture_dir, dry_run=False, font_path=None):
    """Translate all btn_*.bmp in a texture dir. Returns (done, skipped, errors)."""
    if font_path is None:
        font_path = find_jp_font()
    if font_path is None:
        print("FATAL: no JP font found", file=sys.stderr)
        sys.exit(1)

    done = skipped = errors = 0
    for fn in sorted(os.listdir(texture_dir)):
        if not (fn.startswith("btn_") and fn.endswith(".bmp")):
            continue
        label = label_for(fn)
        if not label:
            skipped += 1
            continue
        path = os.path.join(texture_dir, fn)
        img, orig, is_pal = load_bmp(path)
        if img is None:
            errors += 1
            continue
        region = detect_text_region(img)
        if region is None:
            # 8bpp templates often have no renderable text; skip silently
            skipped += 1
            continue
        # shrink font if the JP label is longer than the original text region
        x0, y0, x1, y1 = region
        region_w = x1 - x0 + 1
        text_size = 11
        if region_w < 24 and len(label) >= 3:
            text_size = 9
        work = render_button(img, region, label, font_path, text_size)
        if not dry_run:
            save_bmp(work, orig, path)
        done += 1
        print(f"  {'DRY' if dry_run else 'OK '} {fn}: {label} (region {region})")
    return done, skipped, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="texture dir to process (default: Renewal UI dir)")
    ap.add_argument("--dry-run", action="store_true", help="report only, no writes")
    ap.add_argument("--font", default=None, help="path to JP TTF/OTF")
    args = ap.parse_args()

    if args.dir:
        texture_dir = args.dir
    else:
        texture_dir = os.path.join(
            ROOT, "Translation/Renewal/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º")
    if not os.path.isdir(texture_dir):
        print(f"no such dir: {texture_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"processing {texture_dir}")
    done, skipped, errors = process_dir(texture_dir, args.dry_run, args.font)
    print(f"\ndone: {done}, skipped: {skipped}, errors: {errors}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
