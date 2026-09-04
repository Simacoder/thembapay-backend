"""
Synthetic data generator for ThembaPay trust-scoring model.

Generates:
  - beneficiaries.json   : a mock beneficiary registry (some "known", some not)
  - transactions.csv     : payment transactions with invoice fields and a
                            fraud label, built from explicit, documented rules
                            (not invented at random) so every row is explainable.

This is SYNTHETIC data for MVP training only. It is not real transaction
data and is explicitly labeled as such everywhere it's used downstream.
"""
import json
import random
import uuid
from datetime import datetime, timedelta

from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

N_BENEFICIARIES = 200
N_TRANSACTIONS = 600
FRAUD_RATE = 0.15  # 15% of transactions carry at least one fraud pattern

COUNTRIES = ["South Africa", "Kenya", "Nigeria", "Ghana", "Botswana", "Zambia", "United Kingdom", "United States"]
BANKS = ["Absa", "Standard Bank", "FNB", "Nedbank", "Capitec", "Equity Bank", "GTBank", "Ecobank"]


def make_beneficiaries(n):
    beneficiaries = []
    for _ in range(n):
        beneficiaries.append({
            "beneficiary_id": str(uuid.uuid4()),
            "name": fake.company() if random.random() < 0.4 else fake.name(),
            "account_number": fake.bban(),
            "bank_name": random.choice(BANKS),
            "country": random.choice(COUNTRIES),
        })
    return beneficiaries


def mangle_name(name: str) -> str:
    """Simulate a genuine name mismatch between invoice and beneficiary
    record. Only variants that change the underlying identity are used -
    case changes alone are not a real fraud signal and were dropped after
    testing showed they produced mislabeled "fraud" rows."""
    variants = [
        " ".join(reversed(name.split())) if len(name.split()) > 1 else name + " Holdings",
        name[:-2] + "xx" if len(name) > 4 else name + "-xx",
        fake.company(),  # completely different entity
    ]
    variant = random.choice(variants)
    # guard against a no-op mangle slipping through and mislabeling the row
    if variant.lower().strip() == name.lower().strip():
        variant = fake.company()
    return variant


def make_transactions(beneficiaries, n, fraud_rate):
    rows = []
    known_history = {}  # sender_id -> set of beneficiary_ids seen before

    # Give each sender a small, fixed set of "regular" beneficiaries they
    # pay repeatedly (3-6 each) - this is what makes realistic repeat-
    # payment history possible at all. Without this, senders draw from the
    # full 200-beneficiary pool every time and essentially never see the
    # same beneficiary twice at this sample size (verified: <1 expected
    # collision across 600 draws from a 200,000-combination space) -
    # which would make "new beneficiary" 100% by construction, not by any
    # meaningful signal.
    sender_ids = [f"SND-{i}" for i in range(1000, 1000 + max(20, n // 15))]
    sender_regulars = {
        sid: random.sample(beneficiaries, k=random.randint(3, 6))
        for sid in sender_ids
    }

    for _ in range(n):
        sender_id = random.choice(sender_ids)
        is_fraud = random.random() < fraud_rate

        # 80% of the time, pay one of this sender's regular beneficiaries
        # (building real repeat history); 20% of the time, pay someone new
        if random.random() < 0.8:
            beneficiary = random.choice(sender_regulars[sender_id])
        else:
            beneficiary = random.choice(beneficiaries)

        history = known_history.setdefault(sender_id, set())
        is_new_beneficiary = beneficiary["beneficiary_id"] not in history

        pattern = None
        if is_fraud:
            pattern = random.choice(["amount_mismatch", "name_mismatch", "new_high_value", "bad_po", "stacked"])

        # decide base_amount FIRST (including the new_high_value override) so
        # later fields build on top of it, rather than a fraud pattern
        # silently leaking into a field it shouldn't touch
        if pattern in ("new_high_value", "stacked"):
            base_amount = round(random.uniform(30000, 80000), 2)
            is_new_beneficiary = True
        else:
            base_amount = round(random.uniform(500, 50000), 2)

        invoice_amount = base_amount
        invoice_name = beneficiary["name"]
        po_number = f"PO-{random.randint(10000, 99999)}"
        invoice_date = fake.date_between(start_date="-30d", end_date="today")

        fraud_patterns = []
        if pattern is not None:
            if pattern in ("amount_mismatch", "stacked"):
                invoice_amount = round(base_amount * random.choice([1.4, 1.8, 0.5]), 2)
                fraud_patterns.append("amount_mismatch")
            if pattern in ("name_mismatch", "stacked"):
                invoice_name = mangle_name(beneficiary["name"])
                fraud_patterns.append("name_mismatch")
            if pattern in ("new_high_value", "stacked"):
                # base_amount/is_new_beneficiary already set above, before
                # invoice_amount was derived - this pattern is deliberately
                # left with a CONSISTENT invoice, so document checks alone
                # cannot catch it, only the beneficiary-history feature can
                fraud_patterns.append("new_high_value")
            if pattern in ("bad_po", "stacked"):
                # avoid strings pandas treats as NaN (e.g. "N/A", "NULL") - use
                # clearly-malformed but non-null values instead
                po_number = random.choice(["MISSING", "0000", "PO-1"])
                fraud_patterns.append("bad_po")

        # record this transaction into history AFTER deciding is_new_beneficiary
        # from it - matches how the live BeneficiaryRegistry records after
        # scoring, not before (app/engines/verify.py)
        history.add(beneficiary["beneficiary_id"])

        rows.append({
            "transaction_id": str(uuid.uuid4()),
            "sender_id": sender_id,
            "beneficiary_id": beneficiary["beneficiary_id"],
            "beneficiary_name": beneficiary["name"],
            "invoice_name_on_document": invoice_name,
            "destination_country": beneficiary["country"],
            "payment_amount": base_amount,
            "invoice_amount": invoice_amount,
            "currency": "ZAR",
            "po_number": po_number,
            "invoice_date": str(invoice_date),
            "is_new_beneficiary": is_new_beneficiary,
            "fraud_label": int(is_fraud),
            "fraud_patterns": ";".join(fraud_patterns) if fraud_patterns else "",
        })
    return rows


if __name__ == "__main__":
    import pandas as pd
    from pathlib import Path

    out_dir = Path(__file__).resolve().parent.parent / "data" / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)

    beneficiaries = make_beneficiaries(N_BENEFICIARIES)
    with open(out_dir / "beneficiaries.json", "w") as f:
        json.dump(beneficiaries, f, indent=2)

    transactions = make_transactions(beneficiaries, N_TRANSACTIONS, FRAUD_RATE)
    df = pd.DataFrame(transactions)
    df.to_csv(out_dir / "transactions.csv", index=False)

    print(f"Wrote {len(beneficiaries)} beneficiaries -> {out_dir/'beneficiaries.json'}")
    print(f"Wrote {len(df)} transactions -> {out_dir/'transactions.csv'}")
    print(f"Fraud rate in generated data: {df['fraud_label'].mean():.1%}")
