import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.engines.ocr_extract import TesseractOCRBackend
from app.schemas import OCRExtractionOut

router = APIRouter(prefix="/ocr", tags=["ocr"])

_backend = TesseractOCRBackend()

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB - generous for a phone photo, small enough to reject accidents


@router.post("/extract", response_model=OCRExtractionOut)
async def extract_invoice_fields(file: UploadFile = File(...)) -> OCRExtractionOut:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Upload a PNG, JPEG, or WEBP image.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large - max 10MB.")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    suffix = Path(file.filename or "invoice.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = _backend.extract(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return OCRExtractionOut(
        invoice_amount=result.invoice_amount,
        po_number=result.po_number,
        invoice_date=str(result.invoice_date) if result.invoice_date else None,
        extraction_warnings=result.extraction_warnings,
        raw_text_preview=result.raw_text[:500],
    )
