"""Build the frothedboard banner.

gpt-image-1 renders the flat house style and the keyboard beautifully, and gets essentially every
countable or lettered detail wrong: across roughly twenty attempts it never once produced ten
cards, never put the highlight where it was told, spelled the wordmark "froteccboard", and
repeatedly drew two C keys and no 3.

So the division of labour is: the model paints the backdrop — background and an unlit keyboard —
and this script draws everything whose correctness matters. The board count, the ordering, the
alignment of board 3 with the third card, the key legends and the wordmark are all local.
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFont

PROMPT = """A clean modern technical illustration on a plain flat dark charcoal background, wide
horizontal composition, flat vector style, crisp geometric shapes, no gradients.

The picture contains exactly one object: a stylised mechanical keyboard seen at a slight
three-quarter angle, sitting in the BOTTOM LEFT of the frame. It is complete and uncropped with
clear empty margin around it, and takes up no more than a third of the picture width and a bit
under half its height. It sits entirely below the midline.

The keyboard is entirely dark charcoal, only slightly lighter than the background, with soft
rounded keycaps. Every key is blank and unlit. There is no colour on it anywhere — no amber, no
teal, no white, no highlighted keys.

Absolutely nothing else appears in the picture. No text, letters, digits, words or watermark. No
arrows, lines, cards, boxes, icons or symbols. The entire top half and the whole right-hand side
are completely empty plain dark charcoal.

Documentation artwork, minimal and precise. No photorealism, no glow, no drop shadows, no clutter."""

TEAL = (122, 178, 178)
TEAL_DEEP = (58, 138, 140)
AMBER = (237, 155, 64)
CARD = (52, 58, 62)
GLYPH = (128, 138, 143)
ON_AMBER = (120, 70, 12)
PALE = (214, 214, 208)
MUTED = (120, 128, 133)
INK = (26, 29, 31)

SS = 3  # supersample factor, for antialiased edges

LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
HIGHLIGHT = 2  # zero-based: the third card, which is board 3
KINDS = ["text", "image", "doc", "table", "list", "code", "chart", "folder", "photo", "link"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def generate(path):
    body = json.dumps({
        "model": "gpt-image-1", "prompt": PROMPT,
        "size": "1536x1024", "quality": "high", "n": 1,
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


def occupancy(im, bg, box, step=4, tol=18):
    px = im.load()
    x0, y0, x1, y1 = box
    busy = total = 0
    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            total += 1
            if max(abs(px[x, y][i] - bg[i]) for i in range(3)) > tol:
                busy += 1
    return busy / max(total, 1)


def keyboard_bbox(im, bg):
    """Bounding box of the one object in the lower half."""
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(h // 2, h, 3):
        for x in range(0, w, 3):
            if max(abs(px[x, y][i] - bg[i]) for i in range(3)) > 14:
                xs.append(x)
                ys.append(y)
    if len(xs) < 400:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def has_colour(im, bg):
    """The keyboard is meant to be monochrome; reject stray amber or teal keys."""
    px = im.load()
    w, h = im.size
    hits = 0
    for y in range(h // 2, h, 3):
        for x in range(0, w, 3):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 42:
                hits += 1
    return hits > 260


def rounded(d, box, radius, fill):
    d.rounded_rectangle(box, radius=radius, fill=fill)


def glyph(d, kind, x, y, w, h, colour):
    """Simple flat marks saying 'a board holds that kind of thing too'."""
    cx, cy = x + w // 2, y + h // 2
    r = max(2, w // 22)

    if kind == "text":
        for i, frac in enumerate((1.0, 0.78, 0.9)):
            rounded(d, (x, y + i * (h // 3), x + int(w * frac), y + i * (h // 3) + h // 6), r, colour)
    elif kind == "image":
        d.rounded_rectangle((x, y, x + w, y + h), radius=r * 2, outline=colour, width=r)
        d.ellipse((x + w // 6, y + h // 6, x + w // 6 + w // 6, y + h // 6 + w // 6), fill=colour)
        d.polygon([(x + r, y + h - r), (cx, y + h // 2), (x + w - r, y + h - r)], fill=colour)
    elif kind == "doc":
        fold = w // 3
        d.polygon([(x, y), (x + w - fold, y), (x + w, y + fold), (x + w, y + h), (x, y + h)],
                  fill=colour)
    elif kind == "table":
        for i in range(4):
            d.line((x, y + i * h // 3, x + w, y + i * h // 3), fill=colour, width=r)
            d.line((x + i * w // 3, y, x + i * w // 3, y + h), fill=colour, width=r)
    elif kind == "list":
        for i in range(3):
            yy = y + i * (h // 2 - 2)
            d.ellipse((x, yy, x + r * 3, yy + r * 3), fill=colour)
            rounded(d, (x + r * 5, yy + r // 2, x + w, yy + r * 2 + r // 2), r, colour)
    elif kind == "code":
        d.line([(cx - w // 8, y), (x, cy), (cx - w // 8, y + h)], fill=colour, width=r * 2,
               joint="curve")
        d.line([(cx + w // 8, y), (x + w, cy), (cx + w // 8, y + h)], fill=colour, width=r * 2,
               joint="curve")
    elif kind == "chart":
        for i, frac in enumerate((0.45, 0.75, 1.0)):
            bw = w // 4
            bx = x + i * (w - bw) // 2
            rounded(d, (bx, y + int(h * (1 - frac)), bx + bw, y + h), r, colour)
    elif kind == "folder":
        tab = w // 2
        d.polygon([(x, y + h // 5), (x + tab, y + h // 5), (x + tab + w // 10, y), (x, y)],
                  fill=colour)
        rounded(d, (x, y + h // 6, x + w, y + h), r * 2, colour)
    elif kind == "photo":
        d.rounded_rectangle((x, y + h // 8, x + w, y + h), radius=r * 2, fill=colour)
        d.rounded_rectangle((x + w // 4, y, x + w - w // 4, y + h // 4), radius=r, fill=colour)
    elif kind == "link":
        d.rounded_rectangle((x, cy - h // 5, x + int(w * 0.62), cy + h // 5), radius=h // 5,
                            outline=colour, width=r * 2)
        d.rounded_rectangle((x + w - int(w * 0.62), cy - h // 5, x + w, cy + h // 5),
                            radius=h // 5, outline=colour, width=r * 2)
    elif kind == "clipboard":
        d.rounded_rectangle((x, y + h // 10, x + w, y + h), radius=r * 3, outline=colour, width=r * 2)
        d.rounded_rectangle((x + w // 4, y, x + w - w // 4, y + h // 6), radius=r, fill=colour)
        for i in range(3):
            yy = y + h // 3 + i * (h // 6)
            d.line((x + w // 5, yy, x + w - w // 5, yy), fill=colour, width=r)


def bezier(p0, p1, p2, steps=200):
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def arrow(d, p0, p1, p2, colour, width, head=18):
    pts = bezier(p0, p1, p2)
    d.line([(x * SS, y * SS) for x, y in pts], fill=colour + (255,), width=width * SS,
           joint="curve")
    ax, ay = pts[-1]
    bx, by = pts[-16]
    dx, dy = ax - bx, ay - by
    n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    dx, dy = dx / n, dy / n
    nx, ny = -dy, dx
    d.polygon([((ax + dx * head * 0.7) * SS, (ay + dy * head * 0.7) * SS),
               ((ax - dx * head + nx * head * 0.7) * SS, (ay - dy * head + ny * head * 0.7) * SS),
               ((ax - dx * head - nx * head * 0.7) * SS, (ay - dy * head - ny * head * 0.7) * SS)],
              fill=colour + (255,))


def compose(base_path, out_path):
    im = Image.open(base_path).convert("RGB")
    W, H = im.size
    bg = im.load()[20, H // 2]

    kb = keyboard_bbox(im, bg)
    print(f"  keyboard bbox {kb}")

    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cw, ch, gap = 108, 132, 20
    pitch = cw + gap
    n = 10
    sep = 46
    total = n * pitch - gap + sep + cw
    x0 = (W - total) // 2
    top = 236

    # Keycaps sit clear of the keyboard, to its right, stepping up towards the boards.
    cap_left = max((kb[2] if kb else int(W * 0.36)) + 56, int(W * 0.40))
    cap_left = min(cap_left, W - 580)
    base_y = int(H * 0.77)

    caps = [
        ("CTRL", cap_left, base_y, 156, 92, AMBER),
        ("C", cap_left + 218, base_y - 88, 96, 92, TEAL_DEEP),
        ("3", cap_left + 218 + 182, base_y - 176, 96, 92, AMBER),
    ]

    # Connector first, so the amber card sits over the end of it.
    three = caps[2]
    start = (x0 + HIGHLIGHT * pitch + cw / 2, top + ch)
    end = (three[1] + three[3] / 2, three[2] - 12)
    ctrl_pt = (start[0] + (end[0] - start[0]) * 0.10, start[1] + (end[1] - start[1]) * 0.74)
    d.line([(x * SS, y * SS) for x, y in bezier(start, ctrl_pt, end)],
           fill=AMBER + (255,), width=5 * SS, joint="curve")

    # Chord arrows: CTRL to C, then C to 3.
    for a, b in ((caps[0], caps[1]), (caps[1], caps[2])):
        p0 = (a[1] + a[3] + 8, a[2] + a[4] * 0.4)
        p2 = (b[1] - 20, b[2] + b[4] * 0.66)
        p1 = (p0[0] + (p2[0] - p0[0]) * 0.6, p0[1] - 40)
        arrow(d, p0, p1, p2, TEAL, 7)

    for _, x, y, w, h, colour in caps:
        rounded(d, (x * SS, y * SS, (x + w) * SS, (y + h) * SS), 16 * SS, colour + (255,))

    for i in range(n):
        x = x0 + i * pitch
        chosen = i == HIGHLIGHT
        rounded(d, (x * SS, top * SS, (x + cw) * SS, (top + ch) * SS), 18 * SS,
                (AMBER if chosen else CARD) + (255,))
        gw, gh = int(cw * 0.46), int(ch * 0.36)
        glyph(d, KINDS[i], (x + (cw - gw) // 2) * SS, (top + (ch - gh) // 2) * SS,
              gw * SS, gh * SS, (ON_AMBER if chosen else GLYPH) + (255,))

    cx = x0 + n * pitch - gap + sep
    rounded(d, (cx * SS, top * SS, (cx + cw) * SS, (top + ch) * SS), 18 * SS, PALE + (255,))
    gw, gh = int(cw * 0.44), int(ch * 0.42)
    glyph(d, "clipboard", (cx + (cw - gw) // 2) * SS, (top + (ch - gh) // 2) * SS,
          gw * SS, gh * SS, (90, 96, 100, 255))

    layer = layer.resize((W, H), Image.LANCZOS)
    im = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")

    # Text last, at full resolution, so it stays crisp.
    d2 = ImageDraw.Draw(im)
    num = ImageFont.truetype(FONT, 32)
    small = ImageFont.truetype(FONT, 21)

    for i in range(n):
        x = x0 + i * pitch
        bb = d2.textbbox((0, 0), LABELS[i], font=num)
        d2.text((x + (cw - (bb[2] - bb[0])) // 2 - bb[0], top - 46), LABELS[i], font=num,
                fill=AMBER if i == HIGHLIGHT else TEAL)

    for text, x, y, w, h, _ in caps:
        f = ImageFont.truetype(FONT, 30 if text == "CTRL" else 42)
        bb = d2.textbbox((0, 0), text, font=f)
        d2.text((x + (w - (bb[2] - bb[0])) // 2 - bb[0], y + (h - (bb[3] - bb[1])) // 2 - bb[1]),
                text, font=f, fill=(240, 244, 244) if text == "C" else INK)

    d2.text((x0, top - 104), "every board holds text  ·  images  ·  files  ·  formatted documents",
            font=small, fill=MUTED)

    caption = "system clipboard"
    bb = d2.textbbox((0, 0), caption, font=small)
    d2.text((cx + (cw - (bb[2] - bb[0])) // 2 - bb[0], top + ch + 16), caption, font=small,
            fill=MUTED)

    wordmark = ImageFont.truetype(FONT, 76)
    bb = d2.textbbox((0, 0), "frothedboard", font=wordmark)
    d2.text((W - (bb[2] - bb[0]) - 74 - bb[0], 38 - bb[1]), "frothedboard", font=wordmark,
            fill=TEAL)

    tag = "why one clipboard when many clipboard do better"
    bb2 = d2.textbbox((0, 0), tag, font=small)
    d2.text((W - (bb2[2] - bb2[0]) - 76 - bb2[0], 128 - bb2[1]), tag, font=small, fill=MUTED)

    im.save(out_path)
    print(f"  wrote {out_path}")


def main():
    out = sys.argv[1]
    base = os.path.join(os.path.dirname(out) or ".", "_base.png")

    if not (len(sys.argv) > 2 and sys.argv[2] == "--reuse"):
        for attempt in range(1, 6):
            print(f"attempt {attempt}: generating backdrop…")
            if not generate(base):
                continue
            im = Image.open(base).convert("RGB")
            W, H = im.size
            bg = im.load()[20, H // 2]

            top_busy = occupancy(im, bg, (60, 120, W - 40, 460))
            if top_busy > 0.03:
                print(f"  rejected: top is {top_busy:.1%} occupied, needs to be empty")
                continue
            if has_colour(im, bg):
                print("  rejected: keyboard has coloured keys, which would fight my own")
                continue
            kb = keyboard_bbox(im, bg)
            if kb is None or kb[2] > W * 0.58 or kb[1] < H * 0.40:
                print(f"  rejected: keyboard bbox {kb} is not tucked into the lower left")
                continue
            right_busy = occupancy(im, bg, (int(W * 0.62), int(H * 0.52), W - 40, H - 40))
            if right_busy > 0.03:
                print(f"  rejected: right side is {right_busy:.1%} occupied")
                continue
            print(f"  accepted backdrop (top {top_busy:.1%}, right {right_busy:.1%}, kb {kb})")
            break
        else:
            print("gave up on the backdrop")
            return 1

    compose(base, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
