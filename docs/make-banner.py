"""Build the frothedboard banner.

    WIM_OPENAI_KEY=... python3 docs/make-banner.py docs/frothedboard.png

History explains the shape of this script. On gpt-image-1 essentially every countable or lettered
detail came out wrong: across roughly twenty attempts it never once produced ten cards, never put
the highlight on the card it was told to, spelled the wordmark "froteccboard", and repeatedly drew
two C keys and no 3. That forced a hybrid where the model painted only a backdrop and the whole
board row was composed locally.

gpt-image-2 draws the entire picture correctly, and passed the layout check below on its first
attempt. So this is back to a single generation, with two things still done here:

  * the geometry is measured, and the image rejected unless it really is ten cards plus a separate
    system clipboard card with the highlight on the third — trust, but verify
  * the board numbers and captions are drawn locally, because digit sequences are the one thing
    still not worth gambling on, and because they have to agree with the docs exactly

Board numbers run 1-9 then 0, matching the number row on a keyboard, so the third card along
genuinely is board 3 — which is what the amber connector points at.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFont

MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")

PROMPT = """A clean modern technical infographic banner for a developer tool called
"frothedboard", with the word frothedboard in lowercase teal at the top right. Wide horizontal
composition, dark charcoal background, soft teal and warm amber accents, flat vector illustration
style with crisp geometric shapes and generous negative space.

LOWER LEFT: a stylised mechanical keyboard seen at a slight three-quarter angle, fully inside the
frame with clear margin around it, occupying about a third of the width. Exactly three of its keys
are lit: a wide key clearly lettered CTRL glowing amber and shown pressed down, a key lettered C
glowing teal, and a key showing the digit 3 glowing amber. Two slim curved arrows connect them in
order, CTRL to C and C to 3.

UPPER RIGHT: exactly one single horizontal row of ten rounded cards, side by side in a straight
line, evenly spaced, all exactly the same size, with a clear even gap between neighbours. The cards
carry no numerals, letters or words of any kind. Each card instead shows a different kind of
content as a simple flat glyph, to say that these hold anything you can copy: a few short lines of
text, a small mountain-and-sun picture glyph, a document page with a folded corner, a small
spreadsheet grid, a bulleted list, a photograph frame, a folder, a code bracket, a chart, a link.

Counting from the left end of the row, the FIRST card is dark slate, the SECOND card is dark slate,
and the THIRD card is the highlighted one: it alone is filled solid amber. All seven cards after it
are dark slate too. Exactly one card in the whole row is amber, and it is the third from the left.
One thin amber line arcs from the keyboard's 3 key up to that third card.

Set apart at the far right end of the row, separated from the ten by a clear wide gap, sits one
final card in pale grey bearing a simple clipboard glyph.

Documentation artwork, minimal and precise. No photorealism, no glow, no drop shadows, no clutter."""

LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
HIGHLIGHT = 2  # zero-based: the third card, which is board 3

TEAL = (122, 178, 178)
AMBER = (237, 155, 64)
MUTED = (126, 134, 140)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def generate(path):
    body = json.dumps({
        "model": MODEL, "prompt": PROMPT, "size": "1536x1024", "quality": "high", "n": 1,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=body,
        headers={"Authorization": "Bearer " + os.environ["WIM_OPENAI_KEY"],
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
        return False

    item = payload["data"][0]
    raw = base64.b64decode(item["b64_json"]) if "b64_json" in item else None
    if raw is None:
        with urllib.request.urlopen(item["url"], timeout=300) as r:
            raw = r.read()
    open(path, "wb").write(raw)
    return True


def measure(path):
    """Ten uniform cards plus one pale clipboard card. Returns (row, runs, amber, pale) or None."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = px[20, h // 2]

    for row in range(150, 620, 3):
        runs, cur = [], None
        for x in range(w):
            on = max(abs(px[x, row][i] - bg[i]) for i in range(3)) > 10
            if on and cur is None:
                cur = x
            if not on and cur is not None:
                if x - cur > 40:
                    runs.append((cur, x))
                cur = None
        if cur is not None and w - cur > 40:
            runs.append((cur, w))

        if len(runs) != 11:
            continue
        widths = [b - a for a, b in runs]
        if max(widths) - min(widths) > 22:  # a scanline through the keyboard is never this uniform
            continue

        cols = [px[(a + b) // 2, row] for a, b in runs]
        amber = [i for i, c in enumerate(cols) if c[0] > 180 and 100 < c[1] < 200 and c[2] < 110]
        pale = [i for i, c in enumerate(cols) if min(c) > 150]
        if len(amber) == 1 and len(pale) == 1:
            return row, runs, amber[0], pale[0]

    return None


def card_extent(im, bg, runs, row):
    """
    Top and bottom of the card row. Grown contiguously outward from the row we already measured —
    taking the min and max over the whole column instead picks up the keyboard further down and
    drops the captions at the foot of the image.
    """
    px = im.load()
    mid = (runs[0][0] + runs[0][1]) // 2

    def solid(y):
        return max(abs(px[mid, y][i] - bg[i]) for i in range(3)) > 10

    top = bottom = row
    while top > 1 and solid(top - 1):
        top -= 1
    while bottom < im.size[1] - 2 and solid(bottom + 1):
        bottom += 1
    return top, bottom


def annotate(src, out):
    found = measure(src)
    if found is None:
        return False
    row, runs, amber, pale = found
    if amber != HIGHLIGHT or pale != 10:
        return False

    im = Image.open(src).convert("RGB")
    W, H = im.size
    bg = im.load()[20, H // 2]
    top, bottom = card_extent(im, bg, runs, row)

    d = ImageDraw.Draw(im)
    num = ImageFont.truetype(FONT, 34)
    small = ImageFont.truetype(FONT, 21)

    def centred(text, font, x0, x1, y, fill):
        bb = d.textbbox((0, 0), text, font=font)
        width = bb[2] - bb[0]
        # The clipboard card sits hard against the right edge, so keep its caption in frame.
        x = min(max((x0 + x1) // 2 - width // 2, 12), W - width - 12)
        d.text((x - bb[0], y - bb[1]), text, font=font, fill=fill)

    for i, (x0, x1) in enumerate(runs[:10]):
        centred(LABELS[i], num, x0, x1, top - 52, AMBER if i == HIGHLIGHT else TEAL)

    centred("system clipboard", small, runs[10][0], runs[10][1], bottom + 22, MUTED)
    d.text((runs[0][0], bottom + 22), "every board holds text  ·  images  ·  files  ·  documents",
           font=small, fill=MUTED)

    tag = "why one clipboard when many clipboard do better"
    bb = d.textbbox((0, 0), tag, font=small)
    d.text((W - (bb[2] - bb[0]) - 76 - bb[0], H - 68 - bb[1]), tag, font=small, fill=MUTED)

    im.save(out)
    return True


def main():
    out = sys.argv[1]
    candidate = os.path.join(os.path.dirname(out) or ".", "_candidate.png")

    if not (len(sys.argv) > 2 and sys.argv[2] == "--reuse"):
        for attempt in range(1, 6):
            print(f"attempt {attempt}: generating with {MODEL}…")
            if not generate(candidate):
                continue
            found = measure(candidate)
            if found is None:
                print("  rejected: not a clean row of ten cards plus the clipboard")
                continue
            _, _, amber, pale = found
            if amber != HIGHLIGHT:
                print(f"  rejected: highlight is on card {amber + 1}, needs the 3rd")
                continue
            if pale != 10:
                print(f"  rejected: clipboard card is at index {pale}, needs to be last")
                continue
            print(f"  accepted: ten cards plus clipboard, highlight on card {amber + 1}")
            break
        else:
            print("gave up: no generation satisfied the layout check")
            return 1

    if not annotate(candidate, out):
        print("annotate failed: geometry no longer measurable")
        return 1
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
