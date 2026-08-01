"""Concept preview: coloured flows diverging from the C key to different boards.

Two readings of "numbers up top where they would be on a normal keyboard", so both are drawn:

  A  numbers stay above the boards; the fan runs straight from C to each board
  B  numbers move onto the keyboard's number row where they physically live, and each flow runs
     C -> its number key -> its board, with the boards identified by colour alone

Every ribbon leaves C in the same teal and drifts to its own hue on the way up, so the divergence
reads as one key going ten places rather than ten unrelated lines.
"""

import colorsys
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, SS = 1536, 1024, 2
BG = (36, 40, 43)
KEYBOARD = (52, 58, 62)
KEYCAP = (66, 73, 78)
CARD = (52, 58, 62)
PALE = (214, 214, 208)
MUTED = (126, 134, 140)
AMBER = (237, 155, 64)
INK = (24, 27, 29)
C_HUE = 186 / 360.0  # the teal every flow starts from

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
KINDS = ["text", "image", "doc", "table", "list", "code", "chart", "folder", "photo", "link"]


def hue_for(i):
    """Amber through rose, violet and blue to teal — ten hues that stay apart on charcoal."""
    return ((42 - i * 24) % 360) / 360.0


def rgb(h, s=0.60, v=0.95):
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1.0, s, v))


def lerp_colour(t, target_hue):
    h = C_HUE + (target_hue - C_HUE) * t
    return rgb(h, 0.34 + 0.30 * t, 0.86 + 0.10 * t)


def quad(p0, p1, p2, steps):
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        yield (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
               u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def ribbon(d, pts, target_hue, t0, t1, w0, w1):
    """Draw a path as many short segments so colour and width can travel along it."""
    pts = list(pts)
    for i in range(len(pts) - 1):
        f = i / max(len(pts) - 2, 1)
        t = t0 + (t1 - t0) * f
        width = w0 + (w1 - w0) * f
        d.line([(pts[i][0] * SS, pts[i][1] * SS), (pts[i + 1][0] * SS, pts[i + 1][1] * SS)],
               fill=lerp_colour(t, target_hue) + (255,), width=max(2, int(width * SS)))


def ribbon2(d, pts, c0, c1, w0, w1):
    """Ribbon between two explicit colours, for links that don't follow the hue fan."""
    pts = list(pts)
    for i in range(len(pts) - 1):
        f = i / max(len(pts) - 2, 1)
        col = tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
        d.line([(pts[i][0] * SS, pts[i][1] * SS), (pts[i + 1][0] * SS, pts[i + 1][1] * SS)],
               fill=col + (255,), width=max(2, int((w0 + (w1 - w0) * f) * SS)))


def glyph(d, kind, x, y, w, h, colour):
    r = max(2, w // 20)
    cx, cy = x + w // 2, y + h // 2
    if kind == "text":
        for i, frac in enumerate((1.0, 0.74, 0.88)):
            d.rounded_rectangle((x, y + i * (h // 3), x + int(w * frac), y + i * (h // 3) + h // 7),
                                radius=r, fill=colour)
    elif kind in ("image", "photo"):
        d.rounded_rectangle((x, y, x + w, y + h), radius=r * 2, outline=colour, width=r)
        d.ellipse((x + w // 6, y + h // 6, x + w // 3, y + h // 3), fill=colour)
        d.polygon([(x + r, y + h - r), (cx, cy - h // 8), (x + w - r, y + h - r)], fill=colour)
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
            d.rounded_rectangle((x + r * 5, yy + r // 2, x + w, yy + r * 2), radius=r, fill=colour)
    elif kind == "code":
        d.line([(cx - w // 8, y), (x, cy), (cx - w // 8, y + h)], fill=colour, width=r * 2,
               joint="curve")
        d.line([(cx + w // 8, y), (x + w, cy), (cx + w // 8, y + h)], fill=colour, width=r * 2,
               joint="curve")
    elif kind == "chart":
        for i, frac in enumerate((0.45, 0.75, 1.0)):
            bw = w // 4
            bx = x + i * (w - bw) // 2
            d.rounded_rectangle((bx, y + int(h * (1 - frac)), bx + bw, y + h), radius=r, fill=colour)
    elif kind == "folder":
        d.polygon([(x, y + h // 5), (x + w // 2, y + h // 5), (x + w // 2 + w // 10, y), (x, y)],
                  fill=colour)
        d.rounded_rectangle((x, y + h // 6, x + w, y + h), radius=r * 2, fill=colour)
    elif kind == "link":
        d.rounded_rectangle((x, cy - h // 5, x + int(w * .62), cy + h // 5), radius=h // 5,
                            outline=colour, width=r * 2)
        d.rounded_rectangle((x + w - int(w * .62), cy - h // 5, x + w, cy + h // 5), radius=h // 5,
                            outline=colour, width=r * 2)
    elif kind == "clipboard":
        d.rounded_rectangle((x, y + h // 10, x + w, y + h), radius=r * 3, outline=colour, width=r * 2)
        d.rounded_rectangle((x + w // 4, y, x + w - w // 4, y + h // 6), radius=r, fill=colour)
        for i in range(3):
            yy = y + h // 3 + i * (h // 6)
            d.line((x + w // 5, yy, x + w - w // 5, yy), fill=colour, width=r)


def build(variant):
    im = Image.new("RGBA", (W * SS, H * SS), BG + (255,))
    d = ImageDraw.Draw(im)

    # --- boards across the top -------------------------------------------------------------
    cw, ch, pitch, sep = 108, 132, 128, 46
    total = 10 * pitch - (pitch - cw) + sep + cw
    x0, top = (W - total) // 2, 178
    boards = [(x0 + i * pitch, top) for i in range(10)]
    clip_x = x0 + 10 * pitch - (pitch - cw) + sep

    # --- keyboard --------------------------------------------------------------------------
    kb = (392, 590, 1148, 952)
    numkeys = [(410 + i * 72, 606, 60, 60) for i in range(10)]
    rows = [(438, 676, 9), (452, 746, 9), (466, 816, 8)]
    c_key = (466 + 2 * 72, 816, 60, 60)
    ctrl = (410, 886, 118, 60)
    teal = rgb(C_HUE, 0.52, 0.86)

    d.rounded_rectangle([(kb[0] * SS, kb[1] * SS), (kb[2] * SS, kb[3] * SS)], radius=22 * SS,
                        fill=KEYBOARD + (255,))

    for rx, ry, n in rows:
        for i in range(n):
            if (rx, ry) == (466, 816) and i == 2:
                continue
            d.rounded_rectangle([((rx + i * 72) * SS, ry * SS), ((rx + i * 72 + 60) * SS,
                                                                 (ry + 60) * SS)],
                                radius=10 * SS, fill=KEYCAP + (255,))
    for i in range(5):
        x = 548 + i * 72
        d.rounded_rectangle([(x * SS, 886 * SS), ((x + (188 if i == 2 else 60)) * SS, 946 * SS)],
                            radius=10 * SS, fill=KEYCAP + (255,))
        if i == 2:
            break

    # --- the fan ---------------------------------------------------------------------------
    c_top = (c_key[0] + c_key[2] / 2, c_key[1])
    for i, (bx, by) in enumerate(boards):
        hue = hue_for(i)
        board_bottom = (bx + cw / 2, by + ch)
        nk = numkeys[i]
        key_top = (nk[0] + nk[2] / 2, nk[1])
        key_bottom = (nk[0] + nk[2] / 2, nk[1] + nk[3])

        if variant == "A":
            ctrl_pt = (c_top[0] + (board_bottom[0] - c_top[0]) * 0.18,
                       c_top[1] - (c_top[1] - board_bottom[1]) * 0.62)
            ribbon(d, quad(c_top, ctrl_pt, board_bottom, 220), hue, 0.0, 1.0, 9, 5)
        else:
            c1 = (c_top[0] + (key_bottom[0] - c_top[0]) * 0.2,
                  c_top[1] - (c_top[1] - key_bottom[1]) * 0.66)
            ribbon(d, quad(c_top, c1, key_bottom, 140), hue, 0.0, 0.45, 9, 6)
            c2 = (key_top[0] + (board_bottom[0] - key_top[0]) * 0.15,
                  key_top[1] - (key_top[1] - board_bottom[1]) * 0.62)
            ribbon(d, quad(key_top, c2, board_bottom, 180), hue, 0.45, 1.0, 6, 5)

    # --- Ctrl -> C, the chord's prefix, and C -> the system clipboard, its default -----------
    if variant == "B":
        p0 = (ctrl[0] + ctrl[2] - 4, ctrl[1] + 16)
        p2 = (c_key[0] + 14, c_key[1] + c_key[3] + 4)
        ribbon2(d, quad(p0, (p0[0] + 54, p2[1] + 34), p2, 90), AMBER, teal, 13, 10)

        # Tap no number and the copy goes where it always went. The one flow that never changes
        # colour — which is the whole promise of the tool, in a single line.
        c_right = (c_key[0] + c_key[2], c_key[1] + c_key[3] / 2)
        clip_bottom = (clip_x + cw / 2, top + ch)
        ribbon2(d, quad(c_right, (1372, 856), clip_bottom, 240), teal, teal, 9, 6)

    # --- number keys on top of their ribbons ------------------------------------------------
    for i, (nx, ny, nw, nh) in enumerate(numkeys):
        lit = variant == "B"
        fill = rgb(hue_for(i), 0.58, 0.95) if lit else KEYCAP
        d.rounded_rectangle([(nx * SS, ny * SS), ((nx + nw) * SS, (ny + nh) * SS)],
                            radius=10 * SS, fill=fill + (255,))

    d.rounded_rectangle([(ctrl[0] * SS, ctrl[1] * SS),
                         ((ctrl[0] + ctrl[2]) * SS, (ctrl[1] + ctrl[3]) * SS)],
                        radius=10 * SS, fill=AMBER + (255,))
    d.rounded_rectangle([(c_key[0] * SS, c_key[1] * SS),
                         ((c_key[0] + c_key[2]) * SS, (c_key[1] + c_key[3]) * SS)],
                        radius=10 * SS, fill=rgb(C_HUE, 0.52, 0.82) + (255,))

    # --- board cards -----------------------------------------------------------------------
    for i, (bx, by) in enumerate(boards):
        hue = hue_for(i)
        d.rounded_rectangle([(bx * SS, by * SS), ((bx + cw) * SS, (by + ch) * SS)],
                            radius=18 * SS, fill=CARD + (255,))
        d.rounded_rectangle([(bx * SS, (by + ch - 9) * SS), ((bx + cw) * SS, (by + ch) * SS)],
                            radius=4 * SS, fill=rgb(hue, 0.58, 0.95) + (255,))
        gw, gh = int(cw * 0.44), int(ch * 0.34)
        glyph(d, KINDS[i], (bx + (cw - gw) // 2) * SS, (by + (ch - gh) // 2 - 6) * SS,
              gw * SS, gh * SS, rgb(hue, 0.30, 0.90) + (255,))

    d.rounded_rectangle([(clip_x * SS, top * SS), ((clip_x + cw) * SS, (top + ch) * SS)],
                        radius=18 * SS, fill=PALE + (255,))
    gw, gh = int(cw * 0.42), int(ch * 0.40)
    glyph(d, "clipboard", (clip_x + (cw - gw) // 2) * SS, (top + (ch - gh) // 2) * SS,
          gw * SS, gh * SS, (92, 98, 102, 255))

    im = im.resize((W, H), Image.LANCZOS).convert("RGB")

    # --- text ------------------------------------------------------------------------------
    d2 = ImageDraw.Draw(im)
    num = ImageFont.truetype(FONT, 30)
    keyfont = ImageFont.truetype(FONT, 26)
    small = ImageFont.truetype(FONT, 20)
    big = ImageFont.truetype(FONT, 56)

    def centre(text, font, x, y, w, h, fill):
        bb = d2.textbbox((0, 0), text, font=font)
        d2.text((x + (w - (bb[2] - bb[0])) // 2 - bb[0], y + (h - (bb[3] - bb[1])) // 2 - bb[1]),
                text, font=font, fill=fill)

    for i, (nx, ny, nw, nh) in enumerate(numkeys):
        centre(LABELS[i], keyfont, nx, ny, nw, nh,
               INK if variant == "B" else (150, 158, 164))

    centre("C", keyfont, c_key[0], c_key[1], c_key[2], c_key[3], (16, 30, 32))
    centre("CTRL", small, ctrl[0], ctrl[1], ctrl[2], ctrl[3], INK)

    if variant == "A":
        for i, (bx, by) in enumerate(boards):
            centre(LABELS[i], num, bx, by - 52, cw, 40, rgb(hue_for(i), 0.55, 0.95))

    cap_y = top - 40 if variant == "B" else top + ch + 10
    centre("system clipboard", small, clip_x - 40, cap_y, cw + 80, 30, MUTED)
    if variant == "B":
        d2.text((1206, 902), "no number,", font=small, fill=MUTED)
        d2.text((1206, 928), "no change", font=small, fill=MUTED)

    # Both live in the clear band above the boards, so nothing lands on a card or a number.
    bb = d2.textbbox((0, 0), "frothedboard", font=big)
    d2.text((66 - bb[0], 30 - bb[1]), "frothedboard", font=big, fill=(122, 178, 178))
    note = ("one C, ten places to put it" if variant == "A"
            else "hold Ctrl, tap C, then a number \u2014 or no number, for the usual clipboard")
    bb = d2.textbbox((0, 0), note, font=small)
    d2.text((W - (bb[2] - bb[0]) - 72 - bb[0], 70 - bb[1]), note, font=small, fill=MUTED)

    return im


if __name__ == "__main__":
    out = sys.argv[1]
    for v in ("A", "B"):
        path = out.replace(".png", f"-{v}.png")
        build(v).save(path)
        print("wrote", path)
