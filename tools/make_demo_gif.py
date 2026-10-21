"""Combine the demo screenshots into one GIF (build-time only; needs Pillow, not a MoreMe dependency).

    py -3.12 tools/make_demo_gif.py docs/demo
"""
import sys
from pathlib import Path

from PIL import Image

BG = (30, 30, 30)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    folder = Path(argv[0])
    frames = [Image.open(p).convert("RGB") for p in sorted(folder.glob("[0-9]-*.png"))]
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    padded = []
    for f in frames:
        canvas = Image.new("RGB", (w, h), BG)
        canvas.paste(f, (0, 0))
        padded.append(canvas.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    out = folder / "moreme-demo.gif"
    padded[0].save(out, save_all=True, append_images=padded[1:], duration=4000, loop=0, optimize=True)
    print(out, len(padded), "frames", w, "x", h, out.stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
