# JP Fonts — System/Font drop-in

The kRO client renders UI text using fonts from `System/Font`. The default
Korean fonts (SCDream4/6.otf, NHCgogo_*.eot) lack most kanji glyphs, so
Japanese translations would render as tofu (□) without a font fix.

## What this is

A Japanese-capable font (IPA Gothic, IPA Font License — freely
redistributable) that replaces the client's System/Font files.

## How to install

1. Copy `ipag.ttf` and `ipagp.ttf` into the client's `System/Font/` folder.
2. Rename them to the filenames the client actually loads:
   - `ipag.ttf` -> `SCDream4.otf`  (regular weight)
   - `ipagp.ttf` -> `SCDream6.otf` (bold weight)
   (The client loads by filename; the extension in the filename does not
   matter to the font loader — it reads the embedded font data.)
3. Alternatively, if the client has a font config/lub that lists fonts,
   point it at `ipag.ttf` directly.

## Verification

Launch the client with a translated msgstringtable.txt (Japanese) and
confirm kanji renders in chat/UI/dialogs. If the client still shows tofu,
it is loading the .eot files (NHCgogo_10.eot etc.) — replace those too
with copies of ipag.ttf under the same .eot filenames.

## License

IPA Font License v1.0 — see LICENSE-IPA.txt. Free for commercial and
non-commercial use with attribution. Source: IPA Font (Japan), packaged in
Debian/Ubuntu fonts-ipafont-gothic.
