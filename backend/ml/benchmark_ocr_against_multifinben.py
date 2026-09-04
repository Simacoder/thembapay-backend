"""
Benchmarks the OCR layer against real financial-document images from a
published dataset, instead of only synthetic test invoices.

*** WHAT THIS TESTS, PRECISELY ***
TheFinAI/MultiFinBen-EnglishOCR (huggingface.co/datasets/TheFinAI/MultiFinBen-EnglishOCR)
contains pages from SEC EDGAR regulatory filings (10-K/10-Q exhibits,
insider trading policies, powers of attorney) - NOT invoices. It has no
PO numbers, invoice amounts, or beneficiary names for our
document_check.py parser to extract.

What this DOES prove: whether TesseractOCRBackend's raw text extraction
holds up on real, professionally-typeset financial documents, not just
synthetic test images with a clean font (see tests/test_ocr.py for that
narrower, invoice-specific test).

What this does NOT prove: invoice field-extraction accuracy. That claim
still rests only on the synthetic invoice tests - don't conflate the two
in the pitch. Say "OCR text extraction benchmarked on real SEC filings"
and "invoice field parsing tested on synthetic invoices" as two separate,
accurate claims, not one combined overstated one.

*** NOT EXECUTED BY CLAUDE - run this yourself ***
This needs network access to huggingface.co, which the sandbox this was
built in does not have. Structural logic (base64 decode, Tesseract call,
ROUGE scoring) was verified against a small fabricated sample matching
the dataset's exact real schema (image: base64 PNG string, text: string) -
see the __main__ block's self-test. The actual dataset was never fetched
or scored by Claude.

Usage:
    pip install datasets rouge-score pillow
    python ml/benchmark_ocr_against_multifinben.py [--n 20]
"""
import argparse
import base64
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def decode_and_save_temp_image(base64_png_string: str, tmp_path: Path) -> str:
    """The dataset's 'image' field is a base64-encoded PNG string (per its
    own dataset card). Decode it and write to a temp file, since
    TesseractOCRBackend.extract() takes a file path, matching how it's
    called everywhere else in this project."""
    image_bytes = base64.b64decode(base64_png_string)
    tmp_path.write_bytes(image_bytes)
    return str(tmp_path)


def run_benchmark(n_samples: int, tmp_dir: Path):
    from datasets import load_dataset
    from rouge_score import rouge_scorer
    from app.engines.ocr_extract import TesseractOCRBackend

    print(f"Streaming first {n_samples} samples from TheFinAI/MultiFinBen-EnglishOCR "
          f"(streaming=True, so this does NOT download the full 3.51GB dataset)...")
    ds = load_dataset("TheFinAI/MultiFinBen-EnglishOCR", split="train", streaming=True)

    backend = TesseractOCRBackend()
    scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)

    scores = []
    tmp_dir.mkdir(exist_ok=True)

    for i, example in enumerate(ds.take(n_samples)):
        img_path = decode_and_save_temp_image(example["image"], tmp_dir / f"sample_{i}.png")
        extracted_text = backend.extract_text(img_path)
        ground_truth = example["text"]

        result = scorer.score(ground_truth, extracted_text)
        rouge1_f1 = result["rouge1"].fmeasure
        scores.append(rouge1_f1)
        print(f"  sample {i}: ROUGE-1 F1 = {rouge1_f1:.3f}  "
              f"(ground truth {len(ground_truth)} chars, extracted {len(extracted_text)} chars)")

    avg_score = sum(scores) / len(scores)
    print(f"\n=== RESULT ===")
    print(f"Average ROUGE-1 F1 across {n_samples} real SEC filing pages: {avg_score:.3f}")
    print(f"This measures raw OCR text-extraction quality on REAL financial documents,")
    print(f"not invoice field-parsing accuracy (that's tested separately on synthetic data).")
    return avg_score


def self_test():
    """Structural verification WITHOUT network access - proves the
    decode/OCR/score pipeline is wired correctly using a small fabricated
    sample matching the dataset's exact real schema (base64 PNG + ground
    truth text), so the logic above is trustworthy even though it's never
    been run against the real remote dataset."""
    import tempfile
    from PIL import Image, ImageDraw, ImageFont
    from rouge_score import rouge_scorer
    from app.engines.ocr_extract import TesseractOCRBackend

    print("Running self-test (no network needed) to verify the pipeline logic...")

    font_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "DejaVuSans.ttf"
    img = Image.new("RGB", (600, 150), color="white")
    draw = ImageDraw.Draw(img)
    ground_truth_text = "EXHIBIT 24 LIMITED POWER OF ATTORNEY FOR SECTION 16 REPORTING PURPOSES"
    font = ImageFont.truetype(str(font_path), 20) if font_path.exists() else ImageFont.load_default()
    draw.text((10, 10), ground_truth_text, fill="black", font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    fake_base64 = base64.b64encode(buf.getvalue()).decode("ascii")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "self_test.png"
        img_path = decode_and_save_temp_image(fake_base64, tmp_path)
        backend = TesseractOCRBackend()
        extracted = backend.extract_text(img_path)

        scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)
        result = scorer.score(ground_truth_text, extracted)

        print(f"  ground truth: {ground_truth_text!r}")
        print(f"  extracted:    {extracted.strip()!r}")
        print(f"  ROUGE-1 F1:   {result['rouge1'].fmeasure:.3f}")

        assert result["rouge1"].fmeasure > 0.5, "Self-test FAILED: pipeline logic is broken"
        print("SELF-TEST PASSED: decode -> OCR -> ROUGE pipeline logic is correct.")
        print("(This does not confirm the real dataset works - only that this script's own logic does.)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20, help="Number of samples to benchmark")
    parser.add_argument("--self-test", action="store_true", help="Run structural self-test only, no network needed")
    args = parser.parse_args()

    if args.self_test:
        self_test()
    else:
        run_benchmark(args.n, Path(__file__).resolve().parent / "_benchmark_tmp")
