"""Wrap the keyboard graphic in a wroteitmyself-style poster header.

    NEXA_FONT=... LORA_FONT=... python3 docs/make-poster.py

The artwork itself is placed untouched — not resized, recoloured or cropped. Everything drawn is
above or around it.

Design tokens are lifted from the ship-log pages in the holding site repo rather than eyeballed:
the deep navy ground, the ink ramp, the hairline rules, and the accent set. Type follows
brand-assets/fonts.txt — Nexa Extra Bold for headers, Lora for body.
"""

import os
import pathlib

from PIL import Image, ImageDraw, ImageFont

DOCS = pathlib.Path(__file__).resolve().parent
ART = DOCS / "clipboard-multislot-keyboard.png"
OUT = DOCS / "frothedboard-poster.png"

# Ship-log tokens (site/blog/weeks-2-4-shiplog.html :root)
BG0 = (10, 15, 30)
PANEL = (17, 26, 53)
INK = (234, 239, 250)
INK2 = (157, 170, 198)
INK3 = (94, 108, 140)
LINE = (255, 255, 255, 19)
LINE_STRONG = (255, 255, 255, 36)
INFRA = (98, 189, 221)
SPARK = (251, 191, 36)
LAUNCH = (255, 122, 89)

# Nexa is a licensed commercial face and is deliberately NOT committed here — point these at
# local copies. Lora is OFL and comes from Google Fonts.
#   NEXA_FONT=/path/to/NexaText-ExtraBold.otf LORA_FONT=/path/to/Lora.ttf python3 docs/make-poster.py
NEXA = os.environ.get("NEXA_FONT", "")
LORA = os.environ.get("LORA_FONT", "")

MARGIN = 72
SS = 2


def lora(size, weight=400):
    f = ImageFont.truetype(LORA, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def main():
    for var, path in (("NEXA_FONT", NEXA), ("LORA_FONT", LORA)):
        if not path or not pathlib.Path(path).exists():
            raise SystemExit(f"set {var} to a readable font file (see the note above)")

    art = Image.open(ART).convert("RGB")
    aw, ah = art.size

    title = ImageFont.truetype(NEXA, 92)
    lede = lora(31, 400)
    explainer = ("Ten extra clipboards on Windows — hold Ctrl, tap C, tap a number. "
                 "Plain Ctrl+C is untouched.")

    # Measure first so the header is exactly as tall as its contents, rather than a guessed
    # constant with the type floating somewhere inside it.
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    tb = probe.textbbox((0, 0), "frothedboard", font=title)
    eb = probe.textbbox((0, 0), explainer, font=lede)

    top = 64
    title_h = tb[3] - tb[1]
    lede_h = eb[3] - eb[1]
    rule_y = top + title_h + 26 + lede_h + 34
    header = rule_y + 26

    width = aw + MARGIN * 2
    height = header + ah + MARGIN

    im = Image.new("RGB", (width, height), BG0)
    d = ImageDraw.Draw(im, "RGBA")

    x, y = MARGIN, top
    d.text((x, y - tb[1]), "frothedboard", font=title, fill=INK)
    y += title_h + 26
    d.text((x, y - eb[1]), explainer, font=lede, fill=INK2)

    # Hairline above the artwork, matching the ship-log rules.
    d.rectangle([MARGIN, rule_y, width - MARGIN, rule_y + 1], fill=LINE_STRONG)

    # A recessed panel one pixel proud of the art, so the black artwork does not float on navy.
    d.rectangle([MARGIN - 1, header - 1, MARGIN + aw, header + ah], fill=PANEL)
    im.paste(art, (MARGIN, header))

    im.save(OUT)
    print(f"wrote {OUT}  {im.size[0]}x{im.size[1]}  ({OUT.stat().st_size:,} bytes)")

    # Prove the artwork went in untouched.
    check = Image.open(OUT).convert("RGB").crop((MARGIN, header, MARGIN + aw, header + ah))
    print("artwork identical to source:", list(check.getdata()) == list(art.getdata()))


if __name__ == "__main__":
    main()
