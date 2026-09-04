"""
Run: pytest tests/test_ocr.py -v

Only tests TesseractOCRBackend - the backend actually verified in this
build. UnlimitedOCRBackend is intentionally NOT tested here (no GPU in
this environment); see ml/verify_unlimited_ocr.py for the script that
should be run on real GPU hardware to verify it before demo day.

FONT: uses a font file bundled at tests/fixtures/DejaVuSans.ttf rather
than a system font path. The earlier version of this file hardcoded
'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', which only exists on
Linux - it failed with "OSError: cannot open resource" on Windows/Mac.
Bundling the font file removes the OS dependency entirely instead of
swapping one hardcoded path for another.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

from app.engines.ocr_extract import TesseractOCRBackend

FONT_PATH = Path(__file__).resolve().parent / "fixtures" / "DejaVuSans.ttf"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    if not FONT_PATH.exists():
        raise FileNotFoundError(
            f"Bundled test font not found at {FONT_PATH}. "
            f"It should ship with the repo under tests/fixtures/ - if it's "
            f"missing, re-download the project zip rather than trying to "
            f"substitute a system font path."
        )
    return ImageFont.truetype(str(FONT_PATH), size)


def _make_test_invoice(tmp_path, po_number="PO-88213", amount="65000.00", inv_date="2026-08-15") -> str:
    img = Image.new("RGB", (900, 500), color="white")
    draw = ImageDraw.Draw(img)
    font = _load_font(28)
    lines = [
        "INVOICE", "",
        "Supplier: Coastal Trading Co",
        po_number, "",
        f"Invoice Date: {inv_date}", "",
        "Description: Consulting services", "",
        f"Total: R {amount}",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black", font=font)
        y += 45
    path = str(tmp_path / "invoice.png")
    img.save(path)
    return path


def test_tesseract_extracts_correct_fields_from_clean_invoice(tmp_path):
    image_path = _make_test_invoice(tmp_path)
    backend = TesseractOCRBackend()
    result = backend.extract(image_path)

    assert result.invoice_amount == 65000.0
    assert result.po_number == "PO-88213"
    assert str(result.invoice_date) == "2026-08-15"
    assert result.extraction_warnings == []


def test_tesseract_flags_when_fields_are_missing(tmp_path):
    img = Image.new("RGB", (400, 100), color="white")
    ImageDraw.Draw(img).text((10, 10), "blank document", fill="black", font=_load_font(20))
    path = str(tmp_path / "blank.png")
    img.save(path)

    backend = TesseractOCRBackend()
    result = backend.extract(path)

    assert result.invoice_amount is None
    assert "could_not_extract_amount" in result.extraction_warnings
