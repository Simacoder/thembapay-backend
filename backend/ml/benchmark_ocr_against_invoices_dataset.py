"""
Standalone script referenced by notebooks/thembapay_insights.ipynb Section 6.
Run this on a machine with real internet access to reproduce the verified
results reported in the notebook's fallback path.

Usage:
    pip install datasets rouge-score pillow pytesseract
    python ml/benchmark_ocr_against_invoices_dataset.py --n 100
"""
import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def parse_double_encoded_field(raw_value):
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return None


def get_invoice_fields(parsed_data_raw):
    outer = parse_double_encoded_field(parsed_data_raw)
    if not outer or "json" not in outer:
        return None, None
    try:
        inner = ast.literal_eval(outer["json"])
    except (ValueError, SyntaxError):
        return None, None
    header = inner.get("header", {}) if isinstance(inner, dict) else {}
    return header.get("invoice_no"), header.get("invoice_date")


def get_ground_truth_words(raw_data_raw):
    outer = parse_double_encoded_field(raw_data_raw)
    if not outer or "ocr_words" not in outer:
        return None
    try:
        words = ast.literal_eval(outer["ocr_words"])
    except (ValueError, SyntaxError):
        return None
    return " ".join(str(w) for w in words) if isinstance(words, list) else None


def normalize_for_comparison(text):
    return "" if text is None else str(text).strip().lower().replace(" ", "")


def run_benchmark(n_samples, tmp_dir):
    from datasets import load_dataset
    from rouge_score import rouge_scorer
    from app.engines.ocr_extract import TesseractOCRBackend

    print(f"Streaming {n_samples} samples (does not download the full dataset)...")
    ds = load_dataset("mychen76/invoices-and-receipts_ocr_v1", split="train", streaming=True)
    backend = TesseractOCRBackend()
    scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)
    tmp_dir.mkdir(exist_ok=True)

    rouge_scores, no_match, no_total, date_match, date_total = [], 0, 0, 0, 0
    for i, example in enumerate(ds.take(n_samples)):
        img_path = tmp_dir / f"sample_{i}.png"
        example["image"].save(img_path)
        extracted = backend.extract_text(str(img_path))

        gt_text = get_ground_truth_words(example.get("raw_data", ""))
        if gt_text:
            rouge_scores.append(scorer.score(gt_text, extracted)["rouge1"].fmeasure)

        gt_no, gt_date = get_invoice_fields(example.get("parsed_data", ""))
        if gt_no:
            no_total += 1
            if normalize_for_comparison(gt_no) in normalize_for_comparison(extracted):
                no_match += 1
        if gt_date:
            date_total += 1
            if normalize_for_comparison(gt_date) in normalize_for_comparison(extracted):
                date_match += 1
        print(f"  sample {i}: processed")

    print(f"\nAvg ROUGE-1 F1: {sum(rouge_scores)/len(rouge_scores):.3f}")
    print(f"Invoice number: {no_match}/{no_total} ({no_match/no_total:.0%})")
    print(f"Invoice date: {date_match}/{date_total} ({date_match/date_total:.0%})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    args = parser.parse_args()
    run_benchmark(args.n, Path(__file__).resolve().parent / "_benchmark_tmp")
