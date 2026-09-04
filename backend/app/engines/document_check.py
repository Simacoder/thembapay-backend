"""
Document consistency engine.

Checks structured invoice fields against the payment instruction for
mismatches that commonly indicate fraud or error. This is deliberately
rule-based and explainable - each flag maps to a specific, named check
so the reasoning can be shown to a compliance reviewer, not hidden in
a model.

NOTE ON SCOPE: this operates on structured fields (amount, name, PO
number, date) rather than raw invoice images. A production version
would add OCR extraction upstream (e.g. via a document AI service) to
turn a PDF/photo into these same structured fields - that extraction
step is not implemented here and is flagged explicitly in the README
as a known gap, not silently assumed to exist.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher


@dataclass
class DocumentCheckResult:
    consistency_score: float  # 0.0 (fails everything) - 1.0 (clean)
    flags: list[str] = field(default_factory=list)


def _name_similarity(a: str, b: str) -> float:
    """Character-level similarity, penalized if the two names use the same
    words in a different order (SequenceMatcher alone scores reordered
    words as highly similar, which misses a real fraud pattern)."""
    char_sim = SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    same_tokens_different_order = (
        tokens_a == tokens_b and a.lower().strip() != b.lower().strip()
    )
    if same_tokens_different_order:
        return 0.0  # force a mismatch flag - reordering is a fraud signal, not noise
    return char_sim


def _po_number_looks_valid(po_number: str) -> bool:
    return bool(re.match(r"^PO-\d{4,6}$", po_number.strip()))


def check_document(
    beneficiary_name: str,
    invoice_name_on_document: str,
    payment_amount: float,
    invoice_amount: float,
    po_number: str,
    invoice_date: date,
    today: date | None = None,
) -> DocumentCheckResult:
    today = today or date.today()
    flags: list[str] = []
    penalties = 0.0

    name_sim = _name_similarity(beneficiary_name, invoice_name_on_document)
    if name_sim < 0.95:
        flags.append(f"beneficiary_name_mismatch (similarity={name_sim:.2f})")
        penalties += 0.35

    if invoice_amount <= 0 or payment_amount <= 0:
        flags.append("non_positive_amount")
        penalties += 0.4
    else:
        diff_ratio = abs(invoice_amount - payment_amount) / max(invoice_amount, payment_amount)
        if diff_ratio > 0.05:
            flags.append(f"amount_mismatch (diff={diff_ratio:.1%})")
            penalties += 0.35

    if not _po_number_looks_valid(po_number):
        flags.append("po_number_invalid_format")
        penalties += 0.15

    if invoice_date > today:
        flags.append("invoice_date_in_future")
        penalties += 0.2
    elif (today - invoice_date) > timedelta(days=180):
        flags.append("invoice_date_stale")
        penalties += 0.1

    score = max(0.0, 1.0 - penalties)
    return DocumentCheckResult(consistency_score=round(score, 3), flags=flags)
