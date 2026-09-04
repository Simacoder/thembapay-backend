"""
Beneficiary verification engine.

Deliberately simple and rule-based: given a sender + beneficiary, checks
whether this beneficiary has a prior confirmed transaction history with
this sender. This is the same signal a bank's own fraud team would check
first ("have we paid this person before?") - we're not claiming anything
more sophisticated than that at MVP stage.
"""
from dataclasses import dataclass


@dataclass
class VerificationResult:
    is_new_beneficiary: bool
    prior_transaction_count: int
    match_confidence: float  # 0.0-1.0, heuristic confidence in the beneficiary match


class BeneficiaryRegistry:
    """In-memory registry of (sender_id, beneficiary_id) -> transaction count.

    In production this would be a real query against the bank's own
    transaction history via the Absa Access API, not an in-memory dict.
    """

    def __init__(self):
        self._history: dict[tuple[str, str], int] = {}

    def record_transaction(self, sender_id: str, beneficiary_id: str) -> None:
        key = (sender_id, beneficiary_id)
        self._history[key] = self._history.get(key, 0) + 1

    def load_bulk(self, pairs: list[tuple[str, str, int]]) -> None:
        for sender_id, beneficiary_id, count in pairs:
            self._history[(sender_id, beneficiary_id)] = count

    def verify(self, sender_id: str, beneficiary_id: str) -> VerificationResult:
        count = self._history.get((sender_id, beneficiary_id), 0)
        is_new = count == 0
        # confidence rises with prior successful transactions, capped at 0.99
        confidence = min(0.99, 0.35 + 0.15 * count) if not is_new else 0.30
        return VerificationResult(
            is_new_beneficiary=is_new,
            prior_transaction_count=count,
            match_confidence=confidence,
        )


# module-level default registry used by the API; tests can construct their own
default_registry = BeneficiaryRegistry()
