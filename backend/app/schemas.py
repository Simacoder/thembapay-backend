from datetime import date
from pydantic import BaseModel, Field


class Beneficiary(BaseModel):
    beneficiary_id: str
    name: str
    account_number: str
    bank_name: str
    country: str


class InvoiceDetails(BaseModel):
    invoice_number: str
    po_number: str
    invoice_amount: float
    invoice_date: date
    name_on_document: str


class PaymentEvaluationRequest(BaseModel):
    sender_id: str
    amount: float = Field(gt=0)
    currency: str = "ZAR"
    beneficiary: Beneficiary
    invoice: InvoiceDetails


class RiskFactorOut(BaseModel):
    feature: str
    value: float
    contribution: float


class TrustScoreOut(BaseModel):
    score: float
    fraud_probability: float
    risk_tier: str
    top_factors: list[RiskFactorOut]


class DocumentCheckOut(BaseModel):
    consistency_score: float
    flags: list[str]


class RouteOut(BaseModel):
    rail: str
    estimated_cost_zar: float
    estimated_time_hours: float
    reliability_score: float
    reason: str
    estimate_basis: str


class PaymentEvaluationResponse(BaseModel):
    transaction_id: str
    decision: str  # "proceed" | "flag" | "block"
    trust_score: TrustScoreOut
    document_check: DocumentCheckOut
    route: RouteOut
    ledger_hash: str


class AuditRecordOut(BaseModel):
    transaction_id: str
    timestamp: str
    payload: dict
    prev_hash: str
    this_hash: str


class ChainIntegrityOut(BaseModel):
    chain_valid: bool
    first_broken_record_id: int | None
    total_records: int


class OCRExtractionOut(BaseModel):
    invoice_amount: float | None
    po_number: str | None
    invoice_date: str | None
    extraction_warnings: list[str]
    raw_text_preview: str
