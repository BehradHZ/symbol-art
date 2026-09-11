"""Turn an image into compact, font-aware ASCII art. Python 3.10+."""

from __future__ import annotations

import argparse
from functools import lru_cache
import math
import os
from pathlib import Path
import string
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


CELL = (12, 24)
CHARACTERS = " " + string.punctuation + string.digits + string.ascii_letters


def find_font(explicit: str | None = None) -> str:
    if explicit:
        ImageFont.truetype(explicit, 20)
        return explicit
    candidates = [
        str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/consola.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Courier New.ttf",
        "DejaVuSansMono.ttf",
    ]
    for candidate in candidates:
        try:
            ImageFont.truetype(candidate, 20)
            return candidate
        except OSError:
            continue
    raise ValueError("No monospace font found. Pass --font /path/to/font.ttf")


@lru_cache(maxsize=16)
def glyph_atlas(font_path: str) -> tuple[np.ndarray, np.ndarray]:
    """Calibrate tone and spatial features against the actual font glyphs."""
    font = ImageFont.truetype(font_path, 20)
    if abs(font.getlength("i") - font.getlength("W")) > 0.1:
        raise ValueError("--font must be a monospace font")
    masks = []
    for char in CHARACTERS:
        tile = Image.new("L", CELL)
        ImageDraw.Draw(tile).text(
            ((CELL[0] - font.getlength(char)) / 2, 0), char, font=font, fill=255
        )
        tile = tile.filter(ImageFilter.GaussianBlur(0.7)).resize((4, 8), Image.Resampling.BOX)
        masks.append(np.asarray(tile, dtype=np.float32).ravel() / 255)
    masks = np.stack(masks)
    tones = masks.mean(axis=1)
    tones /= tones.max()
    shape = masks - masks.mean(axis=1, keepdims=True)
    shape /= np.maximum(np.linalg.norm(shape, axis=1, keepdims=True), 1e-6)
    return tones, shape


def prepare_image(
    image: Image.Image,
    crop: tuple[int, int, int, int] | None,
    contrast: float,
    gamma: float,
    invert: bool,
    autocontrast: bool,
) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGBA")
    if crop:
        left, top, right, bottom = crop
        if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
            raise ValueError("Crop must lie inside the oriented image: left top right bottom")
        image = image.crop(crop)
    # Transparent areas become empty characters in either polarity.
    background = Image.new("RGBA", image.size, "black" if invert else "white")
    image = Image.alpha_composite(background, image).convert("L")
    if autocontrast:
        image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageEnhance.Contrast(image).enhance(contrast)
    image = image.point([round(255 * (i / 255) ** gamma) for i in range(256)])
    return image if invert else ImageOps.invert(image)


def convert(
    image: Image.Image,
    width: int = 40,
    *,
    height: int | None = None,
    cell_aspect: float = 0.5,
    mode: str = "shape",
    font_path: str | None = None,
    crop: tuple[int, int, int, int] | None = None,
    contrast: float = 1.15,
    gamma: float = 1.0,
    invert: bool = False,
    autocontrast: bool = True,
) -> str:
    if not 1 <= width <= 500:
        raise ValueError("Width must be between 1 and 500")
    if height is not None and not 1 <= height <= 500:
        raise ValueError("Height must be between 1 and 500")
    if not math.isfinite(cell_aspect) or not 0.1 <= cell_aspect <= 2:
        raise ValueError("Cell aspect must be between 0.1 and 2")
    if any(not math.isfinite(v) or not 0 < v <= 5 for v in (contrast, gamma)):
        raise ValueError("Contrast and gamma must be greater than 0 and at most 5")
    if mode not in ("shape", "tone"):
        raise ValueError("Mode must be shape or tone")
    image = prepare_image(image, crop, contrast, gamma, invert, autocontrast)
    rows = height if height is not None else max(1, round(width * image.height / image.width * cell_aspect))
    if rows > 500:
        raise ValueError("Image is too tall. Crop it or specify --height (at most 500)")
    font_path = find_font(font_path)
    tones, shapes = glyph_atlas(font_path)
    # Keep 32 samples per character; a one-pixel resize discards these details.
    sampled = image.resize((width * 4, rows * 8), Image.Resampling.LANCZOS)
    data = np.asarray(sampled, dtype=np.float32) / 255
    tiles = data.reshape(rows, 8, width, 4).transpose(0, 2, 1, 3).reshape(-1, 32)
    means = tiles.mean(axis=1)
    centered = tiles - means[:, None]
    norms = np.linalg.norm(centered, axis=1)
    unit = centered / np.maximum(norms[:, None], 1e-6)
    # Shape matters most at edges; flat areas should follow the calibrated tone.
    edge_weight = np.minimum(tiles.std(axis=1) * 1.5, 0.35) if mode == "shape" else np.zeros_like(means)
    indices = []
    for start in range(0, len(tiles), 512):
        end = start + 512
        loss = 4 * (means[start:end, None] - tones[None, :]) ** 2
        loss += edge_weight[start:end, None] * (1 - unit[start:end] @ shapes.T)
        indices.extend(np.argmin(loss, axis=1).tolist())
    chars = [CHARACTERS[index] for index in indices]
    # Exact column count, including spaces. Plain ASCII is portable to old terminals.
    return "\n".join("".join(chars[row * width:(row + 1) * width]) for row in range(rows))


def save_preview(art: str, output: Path, font_path: str, cell_aspect: float, invert: bool) -> None:
    font = ImageFont.truetype(font_path, 20)
    cell_width = max(1, round(font.getlength("M")))
    cell_height = max(1, round(cell_width / cell_aspect))
    lines = art.splitlines()
    canvas = Image.new("RGB", (len(lines[0]) * cell_width + 32, len(lines) * cell_height + 32), "#161b22" if invert else "#ffffff")
    draw = ImageDraw.Draw(canvas)
    for row, line in enumerate(lines):
        draw.text((16, 16 + row * cell_height), line, font=font, fill="#c9d1d9" if invert else "#161b22")
    canvas.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input image (PNG, JPEG, WebP, etc.)")
    parser.add_argument("-w", "--width", type=int, default=40, help="Columns, default: 40")
    parser.add_argument("--height", type=int, help="Force row count; otherwise preserve proportions")
    parser.add_argument("--cell-aspect", type=float, default=0.5, help="Terminal character width / line height, default: 0.5")
    parser.add_argument("--mode", choices=("shape", "tone"), default="shape")
    parser.add_argument("--font", help="Monospace TTF/OTF font; auto-detect by default")
    parser.add_argument("--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--contrast", type=float, default=1.15)
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--invert", action="store_true", help="Light symbols on a dark background (positive image)")
    parser.add_argument("--no-autocontrast", action="store_true")
    parser.add_argument("-o", "--output", type=Path, help="Also save plain ASCII text")
    parser.add_argument("--preview", type=Path, help="Also render the text to an image (e.g. preview.png)")
    args = parser.parse_args()
    try:
        font_path = find_font(args.font)
        with Image.open(args.image) as image:
            art = convert(
                image, args.width, height=args.height, cell_aspect=args.cell_aspect,
                mode=args.mode, font_path=font_path, crop=tuple(args.crop) if args.crop else None,
                contrast=args.contrast, gamma=args.gamma, invert=args.invert,
                autocontrast=not args.no_autocontrast,
            )
        if args.output:
            args.output.write_text(art + "\n", encoding="ascii")
        if args.preview:
            save_preview(art, args.preview, font_path, args.cell_aspect, args.invert)
        print(art)
    except BrokenPipeError:
        return 0
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
