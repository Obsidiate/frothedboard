"""Refine the banner, one correction per pass.

    WIM_OPENAI_KEY=... python3 docs/refine-banner.py docs/frothedboard.png

Runs after make-banner.py. Each pass is a single edit call with one correction stated up front and
an explicit hold-everything-else list after it — without that list the model treats the prompt as a
brief for a fresh picture and quietly redraws the parts you were happy with.

The two passes exist separately because the first caused the second. Fixing the keyboard into a
real US ANSI layout also moved the ribbons so they started at the number keys, which destroys the
whole point: one key going ten places. Pass two puts the fan back on the C key while holding the
new keyboard. Correcting one thing at a time, and checking what else moved, is the only way this
converges.
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

MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")

PASSES = [
    ("qwerty", """The keyboard is slop, make it look a bit more like a normal QWERTY US English keyboard
layout.

Specifically, the keyboard should read as a real US ANSI board: a number row running 1 2 3 4 5 6 7
8 9 0 across the top, then QWERTYUIOP, then ASDFGHJKL, then ZXCVBNM, with the correct row-to-row
stagger and sensibly proportioned keys. A wide spacebar along the bottom, with Ctrl at the bottom
left corner, and Shift keys at the outer ends of the ZXCVBNM row. Keycaps evenly sized and evenly
spaced, in convincing three-quarter perspective, all sitting properly on the board.

The C key stays where it belongs on a real keyboard — in the bottom letter row, third along after Z
and X — and remains the teal lit key that every ribbon originates from.

CHANGE NOTHING ELSE. Hold all of the following exactly as they already are:
- the row of dark rounded cards across the top, their outlined white content glyphs, and the thin
  coloured bar along the bottom edge of each one
- the pale grey system clipboard card set apart at the right hand end of that row
- the ten slim ribbons rising from the C key and fanning out to the ten cards, each leaving C in
  teal and drifting to its own hue, sweeping amber, orange, rose, magenta, violet, indigo, blue,
  cyan
- each ribbon still passing through its own number key, and those ten number keys still lit in the
  colour of the ribbon that passes through them
- the short amber link from the Ctrl key to the C key
- the single extra ribbon from C to the pale system clipboard card, still teal along its whole
  length and never changing colour
- the near-black charcoal background, the flat vector finish, the lowercase teal "frothedboard"
  wordmark in the top right corner, and the overall composition and framing

Only the keyboard's own layout and key geometry changes."""),
    ("restore-fan", """The coloured ribbons are wrong and must be redrawn. They currently start at the number keys.
They should all start at the single teal C key.

Redraw them so that every one of the ten coloured ribbons emerges from the teal C key in the
bottom letter row, gathers there in a tight bundle, then fans outward and upward across the
keyboard. On its way up each ribbon passes through its own matching lit number key — the amber
ribbon through key 1, the orange through 2, and so on through to the cyan ribbon through key 0 —
and then continues on to its own card in the row above. Each ribbon leaves the C key teal and
gradually shifts into its own hue as it climbs, so all ten look identical where they meet at C and
fully separated in colour by the time they reach the cards.

The eleventh ribbon also starts at the C key. It leaves C, sweeps out to the right, and travels to
the pale grey system clipboard card at the far right end of the top row. It stays teal along its
entire length and never changes colour, and it does not pass through any number key.

The ribbons are slim, smooth and elegant, and must not obscure the key legends.

CHANGE NOTHING ELSE. Keep the keyboard exactly as it is: the same US ANSI QWERTY layout, the same
key legends and proportions and perspective, the number row still reading 1 2 3 4 5 6 7 8 9 0 with
each key lit in its ribbon's colour, the amber Ctrl key at the bottom left with its short amber
link running to the teal C key. Keep the row of dark cards, their outlined white glyphs and their
coloured bottom bars, the pale system clipboard card, the near-black background, the flat vector
finish, the lowercase teal "frothedboard" wordmark, and the overall composition, all exactly as
they are."""),
]


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



def edit(src_path, prompt):
    body, ctype = multipart(
        {"model": MODEL, "prompt": prompt, "size": "1536x1024", "quality": "high", "n": "1"},
        [("image[]", src_path)],
    )
    req = urllib.request.Request("https://api.openai.com/v1/images/edits", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + os.environ["WIM_OPENAI_KEY"])
    req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}\n{e.read().decode()[:600]}")

    item = payload["data"][0]
    if "b64_json" in item:
        return base64.b64decode(item["b64_json"])
    with urllib.request.urlopen(item["url"], timeout=300) as r:
        return r.read()


def main():
    target = pathlib.Path(sys.argv[1])
    work = target
    for i, (name, prompt) in enumerate(PASSES, 1):
        print(f"pass {i} ({name}) on {work.name}…")
        out = target.with_name(f"{target.stem}-pass{i}{target.suffix}")
        out.write_bytes(edit(work, prompt))
        print(f"  wrote {out.name}")
        work = out
    print(f"\nfinal: {work}   copy over {target.name} when happy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
