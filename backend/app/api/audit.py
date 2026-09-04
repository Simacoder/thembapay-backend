import json

from fastapi import APIRouter, HTTPException

from app.api.payments import get_ledger
from app.schemas import AuditRecordOut, ChainIntegrityOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/{transaction_id}", response_model=AuditRecordOut)
def get_audit_record(transaction_id: str) -> AuditRecordOut:
    record = get_ledger().get(transaction_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No audit record for this transaction_id")
    return AuditRecordOut(
        transaction_id=record.transaction_id,
        timestamp=record.timestamp,
        payload=json.loads(record.payload_json),
        prev_hash=record.prev_hash,
        this_hash=record.this_hash,
    )


@router.get("/verify/chain", response_model=ChainIntegrityOut)
def verify_chain() -> ChainIntegrityOut:
    ledger = get_ledger()
    valid, broken_id = ledger.verify_chain()
    total = ledger._conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    return ChainIntegrityOut(chain_valid=valid, first_broken_record_id=broken_id, total_records=total)
