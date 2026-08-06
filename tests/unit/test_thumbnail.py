"""Unit tests for thumbnail image stamping."""

import io
import pytest
from PIL import Image
from renpy_save_graph.thumbnail import stamp_png, restamp_save


@pytest.mark.unit
def test_stamp_png():
    img = Image.new("RGBA", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    stamped = stamp_png(png_bytes, "@commit_123")
    assert isinstance(stamped, bytes)
    assert stamped.startswith(b"\x89PNG")

    # Verify stamped image is valid PNG
    stamped_img = Image.open(io.BytesIO(stamped))
    assert stamped_img.size == (100, 100)


@pytest.mark.unit
def test_stamp_png_invalid_input():
    # Stamping invalid non-PNG bytes returns original bytes safely
    bad_bytes = b"not a png image"
    res = stamp_png(bad_bytes, "@commit_123")
    assert res == bad_bytes
