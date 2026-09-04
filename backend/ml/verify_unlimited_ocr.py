"""
Run this on an actual CUDA machine (Colab GPU runtime, a cloud GPU box,
or similar) BEFORE relying on Unlimited-OCR in the demo. It has not been
run by Claude - this sandbox has no GPU and no network route to
huggingface.co. This script exists so verification is a single command,
not a leap of faith.

Usage:
    pip install torch==2.10.0 torchvision==0.25.0 transformers==4.57.1 \
        Pillow==12.1.1 einops==0.8.2 addict==2.4.0 easydict==1.13
    python ml/verify_unlimited_ocr.py path/to/a/real/invoice.jpg

If this prints extracted text that matches the invoice, the integration
in app/engines/ocr_extract.py::UnlimitedOCRBackend is confirmed working
and the "UNTESTED" warnings in that file's docstring can be removed.
If it errors or produces garbage, that's important to know NOW, not on
stage - fall back to TesseractOCRBackend, which is already verified.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    if len(sys.argv) != 2:
        print("Usage: python ml/verify_unlimited_ocr.py <path_to_invoice_image>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not Path(image_path).exists():
        print(f"File not found: {image_path}")
        sys.exit(1)

    print("Loading baidu/Unlimited-OCR (this downloads weights on first run - expect several minutes)...")
    from app.engines.ocr_extract import UnlimitedOCRBackend

    backend = UnlimitedOCRBackend()
    try:
        result = backend.extract(image_path)
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        print("\nThis means UnlimitedOCRBackend is NOT ready for the demo.")
        print("Use TesseractOCRBackend (already verified) instead.")
        sys.exit(1)

    print("\n--- RAW OUTPUT ---")
    print(result.raw_text[:2000])
    print("\n--- PARSED FIELDS ---")
    print(f"invoice_amount: {result.invoice_amount}")
    print(f"po_number: {result.po_number}")
    print(f"invoice_date: {result.invoice_date}")
    print(f"warnings: {result.extraction_warnings}")
    print("\nIf the fields above look correct, this integration is verified.")
    print("Update the docstring in app/engines/ocr_extract.py to remove the UNTESTED warning.")


if __name__ == "__main__":
    main()
