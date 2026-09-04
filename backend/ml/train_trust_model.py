"""
Trains the ThembaPay trust-scoring model on synthetic data and reports
holdout precision/recall/F1 - not training-set numbers, which would be
misleadingly optimistic.

Run: python ml/train_trust_model.py
Requires: data/synthetic/transactions.csv (from generate_synthetic_data.py)
Produces: ml/model/trust_model.json
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.engines.document_check import check_document
from app.engines.verify import BeneficiaryRegistry

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "transactions.csv"
MODEL_DIR = Path(__file__).resolve().parent / "model"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Recomputes the exact same features the live API will compute at
    inference time, using the same engine code (not a separate copy) so
    training/serving skew cannot silently creep in.
    """
    registry = BeneficiaryRegistry()
    rows = []
    # replay transactions in order so beneficiary history builds up exactly
    # as it would in production (a beneficiary is "known" only after a
    # PRIOR transaction, not the current one)
    for _, row in df.iterrows():
        verification = registry.verify(row["sender_id"], row["beneficiary_id"])
        doc_result = check_document(
            beneficiary_name=row["beneficiary_name"],
            invoice_name_on_document=row["invoice_name_on_document"],
            payment_amount=row["payment_amount"],
            invoice_amount=row["invoice_amount"],
            po_number=row["po_number"],
            invoice_date=date.fromisoformat(row["invoice_date"]),
        )
        rows.append({
            "document_consistency_score": doc_result.consistency_score,
            "is_new_beneficiary": 1.0 if verification.is_new_beneficiary else 0.0,
            "beneficiary_match_confidence": verification.match_confidence,
            "amount_log": np.log1p(row["payment_amount"]),
            "prior_transaction_count": verification.prior_transaction_count,
            "fraud_label": row["fraud_label"],
        })
        # NOTE: registry only learns this beneficiary AFTER scoring it here,
        # matching how a real "first time we've seen this pair" check works
        registry.record_transaction(row["sender_id"], row["beneficiary_id"])
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = pd.read_csv(DATA_PATH)
    features = build_features(df)

    X = features.drop(columns=["fraud_label"])
    y = features["fraud_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print("=== Holdout evaluation (25% test split, not seen during training) ===")
    print(classification_report(y_test, y_pred, target_names=["legit", "fraud"]))
    print(f"ROC-AUC: {roc_auc_score(y_test, y_proba):.3f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_DIR / "trust_model.json"))
    print(f"\nModel saved -> {MODEL_DIR / 'trust_model.json'}")
