import re
from dataclasses import dataclass, field
from datetime import date, datetime

@dataclass
class ExtractedInvoiceFields:
    raw_text: str
    invoice_amount: object
    po_number: object
    invoice_date: object
    name_on_document: object
    extraction_warnings: list = field(default_factory=list)

# --- Amount: now handles both "R 5000.00" (2-decimal) and "$4050" (whole numbers) ---
_AMOUNT_RE = re.compile(
    r"(?:total|amount due|amount|sub\s*total)[:\s]*[A-Za-z]{0,3}\s*\$?\s*([\d,]+(?:\.\d{2})?)",
    re.IGNORECASE
)

# --- PO number: now handles 4-8 digits, with or without a dash/space separator ---
_PO_RE = re.compile(r"\bPO[-\s]?(\d{4,8})\b", re.IGNORECASE)

# --- Date: now handles ISO (2026-08-18), slash (05/08/2024), and written-out (20th July 2024) ---
_DATE_ISO_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DATE_WRITTEN_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE
)

def parse_fields_from_text(raw_text):
    warnings = []

    amount_match = _AMOUNT_RE.search(raw_text)
    amount = None
    if amount_match:
        raw_amount = amount_match.group(1).replace(",", "")
        try:
            amount = float(raw_amount)
        except ValueError:
            pass
    if amount is None:
        warnings.append("could_not_extract_amount")

    po_match = _PO_RE.search(raw_text)
    po_number = f"PO-{po_match.group(1)}" if po_match else None
    if po_number is None:
        warnings.append("could_not_extract_po_number")

    invoice_date = None
    iso_match = _DATE_ISO_RE.search(raw_text)
    if iso_match:
        try:
            invoice_date = datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    if invoice_date is None:
        slash_match = _DATE_SLASH_RE.search(raw_text)
        if slash_match:
            day, month, year = slash_match.groups()
            try:
                invoice_date = date(int(year), int(month), int(day))
            except ValueError:
                try:
                    invoice_date = date(int(year), int(day), int(month))  # try MM/DD if DD/MM failed
                except ValueError:
                    pass
    if invoice_date is None:
        written_match = _DATE_WRITTEN_RE.search(raw_text)
        if written_match:
            day, month_name, year = written_match.groups()
            try:
                invoice_date = datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").date()
            except ValueError:
                pass
    if invoice_date is None:
        warnings.append("could_not_extract_date")

    return ExtractedInvoiceFields(raw_text=raw_text, invoice_amount=amount, po_number=po_number,
                                   invoice_date=invoice_date, name_on_document=None, extraction_warnings=warnings)

class TesseractOCRBackend:
    def extract_text(self, image_path):
        import pytesseract
        from PIL import Image
        # Windows-specific: point pytesseract directly at the installed
        # tesseract.exe, since it's often not on PATH even after installing.
        # Harmless no-op on Linux/Mac where tesseract IS on PATH - the
        # override only matters if this exact path exists.
        import platform
        if platform.system() == "Windows":
            default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            import os
            if os.path.exists(default_win_path):
                pytesseract.pytesseract.tesseract_cmd = default_win_path
        return pytesseract.image_to_string(Image.open(image_path))
    def extract(self, image_path):
        return parse_fields_from_text(self.extract_text(image_path))