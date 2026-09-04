"""
Run this on ANY laptop with normal internet access - no GPU needed.
This is the easier weekend task compared to verify_unlimited_ocr.py.

Usage:
    pip install paddleocr
    python ml/verify_ppocr.py path/to/a/real/invoice.jpg

If this prints extracted text matching the invoice, PPOCRv6Backend in
app/engines/ocr_extract.py is confirmed working - update its docstring to
remove the "not independently verified" note. This has NOT been run by
Claude - this sandbox's network allowlist blocks the model weight
download (bcebos.com is not in the allowed domains), confirmed as a
network error, not a code error - see ocr_extract.py's PPOCRv6Backend
docstring for the exact error message received.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    if len(sys.argv) != 2:
        print("Usage: python ml/verify_ppocr.py <path_to_invoice_image>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not Path(image_path).exists():
        print(f"File not found: {image_path}")
        sys.exit(1)

    print("Loading PP-OCRv6 (downloads weights on first run, ~35MB for medium tier)...")
    from app.engines.ocr_extract import PPOCRv6Backend

    backend = PPOCRv6Backend()
    try:
        result = backend.extract(image_path)
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        print("\nIf this is a network/download error, check your internet connection.")
        print("If it's something else, PPOCRv6Backend needs a fix before relying on it.")
        sys.exit(1)

    print("\n--- PARSED FIELDS ---")
    print(f"invoice_amount: {result.invoice_amount}")
    print(f"po_number: {result.po_number}")
    print(f"invoice_date: {result.invoice_date}")
    print(f"warnings: {result.extraction_warnings}")
    print("\nIf the fields above look correct, update the docstring in")
    print("app/engines/ocr_extract.py to remove the 'not independently verified' note.")


if __name__ == "__main__":
    main()
