from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PNG_PATH = ROOT / "renderer" / "vela-icon.png"
ICO_PATH = ROOT / "build" / "vela-icon.ico"


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((18, 18, size - 19, size - 19), radius=radius, fill=255)
    return mask


def make_icon(size: int = 1024) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = image.load()
    mask = rounded_mask(size, 216)
    for y in range(size):
        ratio = y / max(1, size - 1)
        shade = int(30 - ratio * 18)
        for x in range(size):
            if mask.getpixel((x, y)):
                pixels[x, y] = (shade, shade, shade + 2, 255)

    draw = ImageDraw.Draw(image)
    border = (86, 86, 90, 255)
    draw.rounded_rectangle((18, 18, size - 19, size - 19), radius=216, outline=border, width=8)

    # A single, calm geometric V. The rounded caps keep it closer to a native
    # macOS symbol than the previous V-plus-sparkle mark.
    stroke = (232, 232, 235, 255)
    width = 88
    left = (278, 250)
    point = (512, 742)
    right = (746, 250)
    draw.line((left, point, right), fill=stroke, width=width, joint="curve")
    radius = width // 2
    for x, y in (left, point, right):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=stroke)

    # Restore the inner corner so the mark reads as one deliberate monogram.
    draw.line((left, point, right), fill=stroke, width=width, joint="curve")
    return image


icon = make_icon()
PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
icon.save(PNG_PATH, "PNG", optimize=True)
icon.save(
    ICO_PATH,
    "ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print(f"Wrote {PNG_PATH}")
print(f"Wrote {ICO_PATH}")
