"""Local browser interface for Symbol Art.

Run with ``python app.py`` and open the local URL printed in the terminal.
The server only binds to localhost and keeps uploaded images in memory.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from symbol_art import convert, find_font

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
EXAMPLE_IMAGE = ROOT / "examples" / "behrad-input.jpg"
MAX_BODY_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
STATIC_FILES = {
    "/": WEB_ROOT / "index.html",
    "/index.html": WEB_ROOT / "index.html",
    "/styles.css": WEB_ROOT / "styles.css",
    "/app.js": WEB_ROOT / "app.js",
}
ALLOWED_OPTIONS = {
    "width",
    "height",
    "cell_aspect",
    "mode",
    "crop",
    "contrast",
    "gamma",
    "invert",
    "autocontrast",
    "font",
}


def available_fonts() -> dict[str, str]:
    """Return monospace fonts that can be used by both conversion and preview."""
    default = find_font()
    fonts = {"default": default}

    for label, filename in (
        ("Consolas", "consola.ttf"),
        ("Courier New", "cour.ttf"),
        ("Lucida Console", "lucon.ttf"),
    ):
        candidate = Path(default).parent / filename
        if candidate.exists():
            fonts[label] = str(candidate)

    return fonts


def image_to_data_url(image: Image.Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


OUTPUT_BG = "#0e1116"


def render_preview(art: str, font_path: str, cell_aspect: float, invert: bool) -> Image.Image:
    """Rasterize ASCII output for browsers without changing the text itself."""
    lines = art.splitlines()
    longest_line = max((len(line) for line in lines), default=1)
    row_count = max(len(lines), 1)

    # Keep previews bounded while preserving the text grid dimensions.
    size = max(3, min(24, int(2200 / max(longest_line * 0.6, row_count * 0.6 / cell_aspect))))
    font = ImageFont.truetype(font_path, size)
    advance = font.getlength("M")
    line_height = advance / cell_aspect

    background = OUTPUT_BG if invert else "#f7f8f5"
    foreground = "#c9ddff" if invert else "#111611"
    canvas = Image.new(
        "RGB",
        (int(longest_line * advance) + 40, int(row_count * line_height) + 40),
        background,
    )
    draw = ImageDraw.Draw(canvas)

    for row, line in enumerate(lines):
        draw.text((20, 20 + row * line_height), line, font=font, fill=foreground)

    return canvas


def _decode_image(data_url: str | None) -> bytes:
    if data_url is None:
        return EXAMPLE_IMAGE.read_bytes()

    if not isinstance(data_url, str) or not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise ValueError("Select a valid image file.")

    try:
        return base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("The image payload is not valid base64 data.") from exc


def _validate_options(raw_options: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(raw_options, dict):
        raise ValueError("Options must be an object.")

    unknown = set(raw_options) - ALLOWED_OPTIONS
    if unknown:
        raise ValueError(f"Unknown option: {sorted(unknown)[0]}")

    options = dict(raw_options)
    for key in ("width", "height"):
        value = options.get(key)
        if value is not None and type(value) is not int:
            raise ValueError(f"{key} must be an integer.")

    crop = options.get("crop")
    if crop is not None:
        if not isinstance(crop, list) or len(crop) != 4 or any(type(value) is not int for value in crop):
            raise ValueError("Crop must contain four integer coordinates.")
        options["crop"] = tuple(crop)

    fonts = available_fonts()
    font_name = options.pop("font", "default")
    if font_name not in fonts:
        raise ValueError("The selected font is not available.")

    return options, fonts[font_name]


def process_request(payload: Any) -> dict[str, Any]:
    """Convert a browser request payload into ASCII art and preview metadata."""
    started_at = time.perf_counter()
    if not isinstance(payload, dict):
        raise ValueError("Request body must be an object.")

    raw_image = _decode_image(payload.get("image"))
    options, font_path = _validate_options(payload.get("options", {}))

    with Image.open(BytesIO(raw_image)) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image must be 25 megapixels or smaller.")
        image = ImageOps.exif_transpose(source).convert("RGBA")

    art = convert(image, font_path=font_path, **options)
    preview = render_preview(
        art,
        font_path,
        options.get("cell_aspect", 0.5),
        options.get("invert", False),
    )

    thumbnail = image.copy()
    thumbnail.thumbnail((900, 900), Image.Resampling.LANCZOS)
    lines = art.splitlines()

    return {
        "art": art,
        "preview": image_to_data_url(preview),
        "source": image_to_data_url(thumbnail),
        "imageWidth": image.width,
        "imageHeight": image.height,
        "columns": len(lines[0]) if lines else 0,
        "rows": len(lines),
        "elapsed": round((time.perf_counter() - started_at) * 1000),
        "fonts": list(available_fonts()),
        "fontFamily": ImageFont.truetype(font_path, 20).getname()[0],
    }


class Handler(BaseHTTPRequestHandler):
    """Serve the terminal UI and the local conversion endpoint."""

    def log_message(self, *_args: Any) -> None:
        return

    def _send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        file_path = STATIC_FILES.get(path)
        if file_path is None or not file_path.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript"}:
            content_type += "; charset=utf-8"
        self._send(200, file_path.read_bytes(), content_type)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        origin = self.headers.get("Origin")
        expected_origin = f"http://{self.headers.get('Host')}"
        if origin and origin != expected_origin:
            self._send(403, b"Forbidden origin", "text/plain; charset=utf-8")
            return

        if self.path != "/api/convert":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                self._send_json(413, {"error": "Image request is too large (maximum 20 MB)."})
                return

            self.connection.settimeout(30)
            payload = json.loads(self.rfile.read(length))
            self._send_json(200, process_request(payload))
        except (ValueError, TypeError, KeyError, OSError, Image.DecompressionBombError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"symbol-art ready at {url}\nCtrl+C to stop.", flush=True)

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
