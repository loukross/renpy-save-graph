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


def stamp_png(
    png_bytes: bytes,
    text: str,
    *,
    warning_text: str | None = None,
) -> bytes:
    """Return a PNG with provenance burned into a bar at the top.

    ``text`` (the hash / branch) is always shown: dark bar, blue text.
    If ``warning_text`` is given, a red band is drawn below it in yellow text,
    sized to fit however many lines the string contains.
    """
    try:
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception:
        return png_bytes
    w, h = img.size
    row_h = max(20, h // 9)
    font = _load_font(row_h - 8)

    warn_lines = warning_text.splitlines() if warning_text else []
    warn_font = _load_font(max(9, row_h - 12)) if warn_lines else None
    warn_line_h = max(9, row_h - 12) + 3
    warn_band_h = len(warn_lines) * warn_line_h + 4 if warn_lines else 0

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Hash / branch row (always present).
    draw.rectangle([0, 0, w, row_h], fill=(0, 0, 0, 170))
    draw.text((6, 3), text, fill=(120, 220, 255, 255), font=font)

    # Warning band (anomaly only) — sized to content.
    if warn_lines:
        draw.rectangle([0, row_h, w, row_h + warn_band_h], fill=(180, 30, 30, 200))
        for i, line in enumerate(warn_lines):
            draw.text(
                (6, row_h + 2 + i * warn_line_h),
                line,
                fill=(255, 240, 80, 255),
                font=warn_font,
            )

    out = io.BytesIO()
    Image.alpha_composite(img, overlay).convert("RGB").save(out, format="PNG")
    return out.getvalue()


def restamp_save(
    save_bytes: bytes,
    text: str,
    *,
    warning_text: str | None = None,
) -> bytes:
    """Return a copy of a `.save` with its `screenshot.png` member restamped.

    All other members (log, json, ...) are preserved byte-for-byte with their
    original compression, so the save loads identically in-game.
    Pass ``warning_text`` to add a red anomaly band below the hash row.
    """
    src = zipfile.ZipFile(io.BytesIO(save_bytes))
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "screenshot.png":
                data = stamp_png(data, text, warning_text=warning_text)
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
