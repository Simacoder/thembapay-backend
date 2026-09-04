"""
Trust scoring engine.

Wraps a trained XGBoost classifier. Deliberately NOT a black box: every
prediction ships with SHAP feature attributions so the score can be
explained to a compliance reviewer or a judge, not just asserted.

Features (must match ml/train_trust_model.py exactly):
  1. document_consistency_score  - from engines.document_check
  2. is_new_beneficiary          - from engines.verify
  3. beneficiary_match_confidence- from engines.verify
  4. amount                      - payment amount (log-scaled)
  5. prior_transaction_count     - from engines.verify
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import shap
import xgboost as xgb

FEATURE_NAMES = [
    "document_consistency_score",
    "is_new_beneficiary",
    "beneficiary_match_confidence",
    "amount_log",
    "prior_transaction_count",
]

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "model"


@dataclass
class RiskFactor:
    feature: str
    value: float
    contribution: float  # SHAP value: positive = pushes toward fraud


@dataclass
class TrustScoreResult:
    score: float  # 0-100, higher = more trustworthy
    fraud_probability: float
    risk_tier: str  # "low" | "medium" | "high"
    top_factors: list[RiskFactor] = field(default_factory=list)


def build_feature_vector(
    document_consistency_score: float,
    is_new_beneficiary: bool,
    beneficiary_match_confidence: float,
    amount: float,
    prior_transaction_count: int,
) -> np.ndarray:
    return np.array([[
        document_consistency_score,
        1.0 if is_new_beneficiary else 0.0,
        beneficiary_match_confidence,
        np.log1p(amount),
        prior_transaction_count,
    ]], dtype=float)


class TrustScoringEngine:
    def __init__(self, model_path: Path | None = None):
        self.model_path = model_path or (MODEL_DIR / "trust_model.json")
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(self.model_path))
        self.explainer = shap.TreeExplainer(self.model)

    def score(
        self,
        document_consistency_score: float,
        is_new_beneficiary: bool,
        beneficiary_match_confidence: float,
        amount: float,
        prior_transaction_count: int,
    ) -> TrustScoreResult:
        x = build_feature_vector(
            document_consistency_score, is_new_beneficiary,
            beneficiary_match_confidence, amount, prior_transaction_count,
        )
        fraud_prob = float(self.model.predict_proba(x)[0][1])
        trust_score = round((1.0 - fraud_prob) * 100, 1)

        shap_values = self.explainer.shap_values(x)[0]
        factors = sorted(
            [
                RiskFactor(feature=name, value=float(x[0][i]), contribution=float(shap_values[i]))
                for i, name in enumerate(FEATURE_NAMES)
            ],
            key=lambda f: abs(f.contribution),
            reverse=True,
        )

        if trust_score >= 70:
            tier = "low"
        elif trust_score >= 40:
            tier = "medium"
        else:
            tier = "high"

        return TrustScoreResult(
            score=trust_score,
            fraud_probability=round(fraud_prob, 4),
            risk_tier=tier,
            top_factors=factors[:3],
        )
