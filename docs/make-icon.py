"""Generate the frothedboard app icon with OpenAI's image model.

    WIM_OPENAI_KEY=... python3 docs/make-icon.py src/Frothedboard.App/frothedboard.ico [preview.png]

The art is generated at 1024x1024 on a transparent background, trimmed to its own bounding box so
the subject fills the frame rather than floating in whatever margin the model felt like leaving,
then reduced to each size Windows asks for and packed into a multi-resolution .ico.

The reduction matters more than the generation. A tray icon is shown at 16x16, and a straight
resize of detailed art turns to grey soup at that size, so the small entries are sharpened after
downscaling and the alpha is re-hardened to keep the silhouette crisp instead of feathering out.
"""

import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image, ImageEnhance, ImageFilter

MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
SIZES = [16, 24, 32, 48, 64, 128, 256]

PROMPT = """A modern application icon, square, flat vector style, bold and extremely simple.

The subject is a small stack of three rounded cards, seen straight on, fanned with a slight
diagonal offset so the two behind peek out from under the front one. The two rear cards are dark
slate grey. The front card is filled solid warm amber and carries three short, thick, darker
horizontal bars suggesting lines of text.

Chunky forms, thick rounded corners, heavy contrast between the amber front card and the slate
ones. Very few shapes overall. The subject fills the frame with only a small even margin.

The background is one completely flat, solid, uniform pure magenta (RGB 255, 0, 255), covering
every part of the image the cards do not, right to all four edges. It is a plain solid fill: no
checkerboard, no chequered pattern, no squares, no texture, no gradient, no vignette, no border.
Nothing in the picture except the cards and that magenta.

No text, no letters, no numbers, no logo, no drop shadows, no glow, no reflections, no outlines,
no scene, no perspective.

This has to stay readable when shrunk to sixteen pixels across, so keep every element large and
simple with nothing thin or finely detailed."""


def generate():
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "size": "1024x1024",
        "quality": "high",
        "n": 1,
    }

    for attempt in (payload,):
        req = urllib.request.Request(
            "https://api.openai.com/v1/images/generations",
            data=json.dumps(attempt).encode(),
            headers={"Authorization": "Bearer " + os.environ["WIM_OPENAI_KEY"],
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                body = json.load(r)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode()[:220]}")
            continue

        item = body["data"][0]
        if "b64_json" in item:
            return Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGBA")
        with urllib.request.urlopen(item["url"], timeout=300) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGBA")

    return None


KEY = (255, 0, 255)


def chroma_key(im, soft=52, hard=104):
    """
    Cut the magenta backdrop. Asking for a transparent background does not work — the API rejects
    the parameter, and the model answers the word "transparent" by literally painting a
    checkerboard. A flat key colour it can actually draw, and this removes it.

    Distances below `soft` go fully transparent, above `hard` stay fully opaque, and the band
    between is feathered so anti-aliased edges do not turn into a hard jagged cut.
    """
    px = im.load()
    w, h = im.size
    cut = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            dist = abs(r - KEY[0]) + abs(g - KEY[1]) + abs(b - KEY[2])
            if dist <= soft:
                px[x, y] = (r, g, b, 0)
                cut += 1
            elif dist < hard:
                px[x, y] = (r, g, b, int(a * (dist - soft) / (hard - soft)))
            # Despill: magenta bleeding into an edge pixel shows as a pink fringe.
            if 0 < dist < hard * 3 and r > g and b > g:
                px[x, y] = (min(r, g + 40), g, min(b, g + 40), px[x, y][3])
    print(f"  keyed out {cut / (w * h):.0%} of the frame as background")
    return im


def trim(im, margin=0.04):
    box = im.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
    if box is None:
        return im
    im = im.crop(box)

    side = int(max(im.size) * (1 + margin * 2))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im)
    return canvas


def reduce_to(master, px):
    """Downscale, then claw back the definition the reduction costs at small sizes."""
    im = master.resize((px, px), Image.LANCZOS)
    if px <= 48:
        im = im.filter(ImageFilter.UnsharpMask(radius=1.1, percent=190 if px <= 24 else 130,
                                               threshold=2))
        im = ImageEnhance.Contrast(im).enhance(1.14 if px <= 24 else 1.06)
        # Feathered alpha reads as a grubby smudge at 16px; harden it back to a clean edge.
        alpha = im.getchannel("A").point(lambda a: 0 if a < 96 else (255 if a > 168 else a))
        im.putalpha(alpha)
    return im


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "frothedboard.ico"
    preview = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"generating icon art with {MODEL}…")
    art = generate()
    if art is None:
        print("generation failed")
        return 1

    master = trim(chroma_key(art)).resize((512, 512), Image.LANCZOS)
    frames = {px: reduce_to(master, px) for px in SIZES}

    frames[256].save(out, format="ICO", sizes=[(n, n) for n in SIZES],
                     append_images=[frames[n] for n in SIZES if n != 256])
    print(f"wrote {out} with sizes {SIZES}")

    if preview:
        pad, gap = 12, 18
        strip = Image.new("RGBA", (sum(SIZES) + gap * len(SIZES) + pad, 256 + pad * 2),
                          (36, 40, 43, 255))
        x = pad
        for n in SIZES:
            strip.paste(frames[n], (x, pad + (256 - n) // 2), frames[n])
            x += n + gap
        strip.save(preview)
        print(f"wrote {preview}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
