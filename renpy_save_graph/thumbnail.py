"""Stamp provenance (branch @hash) onto a save's thumbnail.

Ren'Py's load screen renders the `screenshot.png` member of a `.save` as the slot
thumbnail. When the tool *materializes* a commit into a managed slot, it rewrites
that member with a stamped copy so the in-game load screen shows where the slot
currently sits in its graph. Only the slot copy is stamped; the committed library
blob keeps the game's original screenshot (see docs/DESIGN.md).

Requires unsigned saves (no `signatures` member); verified true for the target
game. On a signed game, rewriting members would need the signing key.
"""

from __future__ import annotations

import io
import zipfile

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def stamp_png(png_bytes: bytes, text: str) -> bytes:
    """Return a PNG with provenance (the hash / branch) burned into a bar at the top."""
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception:
        return png_bytes
    w, h = img.size
    row_h = max(20, h // 9)
    font = _load_font(row_h - 8)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, 0, w, row_h], fill=(0, 0, 0, 170))
    draw.text((6, 3), text, fill=(120, 220, 255, 255), font=font)

    out = io.BytesIO()
    Image.alpha_composite(img, overlay).convert("RGB").save(out, format="PNG")
    return out.getvalue()


def restamp_save(save_bytes: bytes, text: str) -> bytes:
    """Return a copy of a `.save` with its `screenshot.png` member restamped.

    All other members (log, json, ...) are preserved byte-for-byte with their
    original compression, so the save loads identically in-game.
    """
    src = zipfile.ZipFile(io.BytesIO(save_bytes))
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "screenshot.png":
                data = stamp_png(data, text)
            # Preserve each member's original compression method.
            dst.writestr(info, data, compress_type=info.compress_type)
    return out_buf.getvalue()


def optimize_save_thumbnail(
    save_bytes: bytes,
    max_width: int = 640,
    max_height: int = 360,
) -> bytes:
    """Downscale & optimize `screenshot.png` inside a `.save` zip to save Git commit storage.

    Resizes large full-screen screenshots down to standard slot thumbnail dimensions
    and optimizes compression. Preserves all other zip members (log, json, ...) intact.
    """
    try:
        src = zipfile.ZipFile(io.BytesIO(save_bytes))
        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w") as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "screenshot.png":
                    try:
                        img = Image.open(io.BytesIO(data))
                        w, h = img.size
                        if w > max_width or h > max_height:
                            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                        opt_buf = io.BytesIO()
                        img.convert("RGB").save(opt_buf, format="PNG", optimize=True)
                        data = opt_buf.getvalue()
                    except Exception:
                        pass
                dst.writestr(info, data, compress_type=info.compress_type)
        return out_buf.getvalue()
    except Exception:
        return save_bytes
