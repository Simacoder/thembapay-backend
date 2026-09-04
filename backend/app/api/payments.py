import os
import uuid

from fastapi import APIRouter

from app.engines.document_check import check_document
from app.engines.route_optimizer import recommend_route
from app.engines.trust_score import TrustScoringEngine
from app.engines.verify import default_registry
from app.integrations.eclipse_client import EclipseAPIError, EclipseAuthError, EclipseClient
from app.ledger.hash_chain import AuditLedger
from app.schemas import (
    DocumentCheckOut, PaymentEvaluationRequest, PaymentEvaluationResponse,
    RiskFactorOut, RouteOut, TrustScoreOut,
)

router = APIRouter(prefix="/payments", tags=["payments"])

_trust_engine: TrustScoringEngine | None = None
_ledger: AuditLedger | None = None
_eclipse_client = EclipseClient()  # credentials read from ECLIPSE_* env vars, if set


def get_trust_engine() -> TrustScoringEngine:
    global _trust_engine
    if _trust_engine is None:
        _trust_engine = TrustScoringEngine()
    return _trust_engine


def get_ledger() -> AuditLedger:
    global _ledger
    if _ledger is None:
        _ledger = AuditLedger()
    return _ledger


DECISION_THRESHOLDS = {"block_below": 40, "flag_below": 70}


def decide(score: float) -> str:
    if score < DECISION_THRESHOLDS["block_below"]:
        return "block"
    if score < DECISION_THRESHOLDS["flag_below"]:
        return "flag"
    return "proceed"


@router.post("/evaluate", response_model=PaymentEvaluationResponse)
def evaluate_payment(request: PaymentEvaluationRequest) -> PaymentEvaluationResponse:
    transaction_id = str(uuid.uuid4())

    # 1. beneficiary verification
    verification = default_registry.verify(request.sender_id, request.beneficiary.beneficiary_id)

    # 2. document consistency check
    doc_result = check_document(
        beneficiary_name=request.beneficiary.name,
        invoice_name_on_document=request.invoice.name_on_document,
        payment_amount=request.amount,
        invoice_amount=request.invoice.invoice_amount,
        po_number=request.invoice.po_number,
        invoice_date=request.invoice.invoice_date,
    )

    # 3. trust score (combines both of the above + amount + history)
    trust_result = get_trust_engine().score(
        document_consistency_score=doc_result.consistency_score,
        is_new_beneficiary=verification.is_new_beneficiary,
        beneficiary_match_confidence=verification.match_confidence,
        amount=request.amount,
        prior_transaction_count=verification.prior_transaction_count,
    )

    # 4. route recommendation
    route = recommend_route(
        destination_country=request.beneficiary.country,
        risk_tier=trust_result.risk_tier,
        amount=request.amount,
    )

    decision = decide(trust_result.score)

    # only record beneficiary history for transactions that actually proceed
    rail_call_status = "not_attempted"
    eclipse_tenant_id = int(os.environ.get("ECLIPSE_TENANT_ID", "0"))

    if decision == "proceed":
        default_registry.record_transaction(request.sender_id, request.beneficiary.beneficiary_id)
        # real Eclipse sandbox call - see app/integrations/eclipse_client.py
        # for exactly what is verified vs. inferred about this integration.
        # Falls back gracefully if no sandbox credentials are configured,
        # rather than pretending the payment rail call succeeded.
        try:
            _eclipse_client.initiate_payment(
                tenant_id=eclipse_tenant_id,
                source_wallet_id=request.sender_id,
                amount=request.amount,
                currency=request.currency,
                payment_type="WALLET_TRANSFER",
                payment_data={
                    "destinationAccountNumber": request.beneficiary.account_number,
                    "destinationBankName": request.beneficiary.bank_name,
                },
            )
            rail_call_status = "sent_to_eclipse_sandbox"
        except EclipseAuthError:
            rail_call_status = "skipped_no_sandbox_credentials_configured"
        except EclipseAPIError as e:
            rail_call_status = f"eclipse_api_error_{e.status_code}"
    elif decision in ("block", "flag"):
        # publish the verdict to Eclipse's fraud-events endpoint when
        # credentials are available - see eclipse_client.py docstring for
        # what's verified about this endpoint vs. inferred
        try:
            _eclipse_client.publish_fraud_event(
                tenant_id=eclipse_tenant_id,
                transaction_reference=transaction_id,
                risk_tier=trust_result.risk_tier,
                reason="; ".join(doc_result.flags) or "trust score below threshold",
            )
            rail_call_status = "fraud_event_published_to_eclipse"
        except (EclipseAuthError, EclipseAPIError):
            rail_call_status = "skipped_no_sandbox_credentials_configured"

    # 5. write to the tamper-evident audit ledger - every evaluation, regardless of decision
    ledger_payload = {
        "sender_id": request.sender_id,
        "beneficiary_id": request.beneficiary.beneficiary_id,
        "amount": request.amount,
        "trust_score": trust_result.score,
        "risk_tier": trust_result.risk_tier,
        "decision": decision,
        "document_flags": doc_result.flags,
        "route": route.rail,
        "rail_call_status": rail_call_status,
    }
    ledger_record = get_ledger().append(transaction_id, ledger_payload)

    return PaymentEvaluationResponse(
        transaction_id=transaction_id,
        decision=decision,
        trust_score=TrustScoreOut(
            score=trust_result.score,
            fraud_probability=trust_result.fraud_probability,
            risk_tier=trust_result.risk_tier,
            top_factors=[RiskFactorOut(**vars(f)) for f in trust_result.top_factors],
        ),
        document_check=DocumentCheckOut(
            consistency_score=doc_result.consistency_score,
            flags=doc_result.flags,
        ),
        route=RouteOut(
            rail=route.rail,
            estimated_cost_zar=route.estimated_cost_zar,
            estimated_time_hours=route.estimated_time_hours,
            reliability_score=route.reliability_score,
            reason=route.reason,
            estimate_basis=route.estimate_basis,
        ),
        ledger_hash=ledger_record.this_hash,
    )
