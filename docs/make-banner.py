"""Build the banner: existing artwork for style, the flow concept for information design.

    WIM_OPENAI_KEY=... python3 docs/make-banner.py docs/frothedboard.png

Two reference images go to the image-edit endpoint. The first is the shipped banner and carries
the visual language; the second is the locally-drawn flow diagram and carries only the ideas.
Saying which image governs what is the whole trick — without it the model averages the two and
returns something that looks like neither.
"""

import base64
import json
import mimetypes
import os
import pathlib
import sys
import urllib.error
import urllib.request
import uuid

DOCS = pathlib.Path(__file__).resolve().parent

# frothedboard-base.png is the previous banner and supplies the look; flow-concept.png is the
# schematic from make-flow-concept.py and supplies only the ideas. Both are committed so this
# is reproducible — and note the style reference is deliberately NOT the current banner, or
# rerunning this would feed the model its own output.
STYLE = DOCS / "frothedboard-base.png"
CONCEPT = DOCS / "flow-concept.png"

PROMPT = """You are given two reference images. They serve completely different purposes.

IMAGE 1 IS THE STYLE. Reproduce its visual language exactly: the deep near-black charcoal
background, the clean flat vector illustration quality, the softly shaded three-quarter-view
mechanical keyboard sitting in the lower left, the row of dark rounded slate cards across the top
each holding a thin outlined white content glyph, the pale grey system-clipboard card set apart at
the far right end of that row, and the lowercase teal "frothedboard" wordmark in the top right
corner. Same proportions, same restraint, same finish. The result must look like it came from the
same hand as image 1.

IMAGE 2 IS THE IDEA ONLY. Do not copy its flat schematic keyboard, its blocky drawing or its
typography. Take from it only this information design, and express it in image 1's style:

- Ten slim ribbons rise from the C key on the keyboard and fan outward, one to each of the ten
  cards in the top row. Every ribbon leaves the C key in the same teal, then gradually shifts to
  its own distinct hue as it climbs — sweeping through amber, orange, rose, magenta, violet,
  indigo, blue and cyan — so the fan reads as one key going to ten different places.
- On the way up, each ribbon passes through its own key on the keyboard's number row. Those ten
  number keys read 1 2 3 4 5 6 7 8 9 0 from left to right and each is lit in the colour of the
  ribbon passing through it.
- A short amber link runs from the CTRL key to the C key, showing Ctrl feeding C.
- One additional ribbon leaves the C key and travels to the pale system-clipboard card at the far
  right. This single ribbon stays teal along its entire length and never changes colour.
- Each of the ten cards carries a thin coloured bar along its bottom edge matching its own ribbon.

The ribbons are slim, smooth and elegant — fine glowing filaments, not thick tubes or cables. They
must not obscure the keyboard or the cards. Keep the composition uncluttered with generous dark
space, exactly as in image 1.

No drop shadows, no glow bloom, no photorealism, no 3D perspective beyond the keyboard's own gentle
angle."""


def multipart(fields, files):
    boundary = "----frothed" + uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, path in files:
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                 f"filename=\"{path.name}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
        body += path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def main():
    out = pathlib.Path(sys.argv[1])
    model = os.environ.get("IMAGE_MODEL", "gpt-image-2")

    for path in (STYLE, CONCEPT):
        if not path.exists():
            raise SystemExit(f"missing reference: {path}")

    body, ctype = multipart(
        {"model": model, "prompt": PROMPT, "size": "1536x1024", "quality": "high", "n": "1"},
        [("image[]", STYLE), ("image[]", CONCEPT)],
    )
    print(f"posting {len(body):,} bytes to the edits endpoint as {model}…")

    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + os.environ["WIM_OPENAI_KEY"])
    req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}\n{e.read().decode()[:600]}")

    item = payload["data"][0]
    raw = base64.b64decode(item["b64_json"]) if "b64_json" in item else None
    if raw is None:
        with urllib.request.urlopen(item["url"], timeout=300) as r:
            raw = r.read()
    out.write_bytes(raw)
    print(f"wrote {out} ({len(raw):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
