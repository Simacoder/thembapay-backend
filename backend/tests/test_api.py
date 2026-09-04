"""
Run: pytest tests/ -v
Uses FastAPI's TestClient - spins the app up in-process, no server needed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def _payload(**overrides):
    base = {
        "sender_id": "SND-PYTEST-1",
        "amount": 5000,
        "currency": "ZAR",
        "beneficiary": {
            "beneficiary_id": "BEN-PYTEST-1",
            "name": "Test Supplier Ltd",
            "account_number": "1112223334",
            "bank_name": "Absa",
            "country": "South Africa",
        },
        "invoice": {
            "invoice_number": "INV-PYTEST-1",
            "po_number": "PO-12345",
            "invoice_amount": 5000,
            "invoice_date": "2026-08-15",
            "name_on_document": "Test Supplier Ltd",
        },
    }
    base.update(overrides)
    return base


def test_clean_payment_proceeds_and_gets_payshap():
    r = client.post("/payments/evaluate", json=_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "proceed"
    assert body["route"]["rail"] == "PayShap"
    assert body["trust_score"]["score"] > 70


def test_document_mismatch_is_flagged_by_document_check():
    payload = _payload(sender_id="SND-PYTEST-2")
    payload["beneficiary"]["beneficiary_id"] = "BEN-PYTEST-2"
    payload["beneficiary"]["name"] = "Real Beneficiary Ltd"
    payload["invoice"]["name_on_document"] = "Completely Different Entity"
    r = client.post("/payments/evaluate", json=payload)
    body = r.json()
    assert len(body["document_check"]["flags"]) > 0
    assert body["decision"] in ("flag", "block")


def test_new_beneficiary_high_amount_clean_invoice_is_still_caught():
    """The hard case: document checks alone can't catch this - only the
    trust model's beneficiary-history + amount features can."""
    payload = _payload(sender_id="SND-PYTEST-3", amount=70000)
    payload["beneficiary"]["beneficiary_id"] = "BEN-PYTEST-NEW"
    payload["beneficiary"]["name"] = "Brand New Beneficiary"
    payload["invoice"]["invoice_amount"] = 70000
    payload["invoice"]["name_on_document"] = "Brand New Beneficiary"
    r = client.post("/payments/evaluate", json=payload)
    body = r.json()
    assert body["document_check"]["flags"] == []  # invoice IS clean
    assert body["trust_score"]["risk_tier"] in ("medium", "high")  # but model still catches it


def test_audit_record_is_retrievable_after_evaluation():
    r1 = client.post("/payments/evaluate", json=_payload(sender_id="SND-PYTEST-4"))
    tx_id = r1.json()["transaction_id"]
    r2 = client.get(f"/audit/{tx_id}")
    assert r2.status_code == 200
    assert r2.json()["transaction_id"] == tx_id


def test_audit_record_missing_returns_404():
    r = client.get("/audit/does-not-exist")
    assert r.status_code == 404


def test_chain_integrity_endpoint_reports_valid():
    client.post("/payments/evaluate", json=_payload(sender_id="SND-PYTEST-5"))
    r = client.get("/audit/verify/chain")
    assert r.status_code == 200
    assert r.json()["chain_valid"] is True
