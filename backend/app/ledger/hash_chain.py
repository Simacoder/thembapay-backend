"""
Hash-chained audit ledger.

Every payment decision is written here as a record containing a hash of
its own payload PLUS the hash of the previous record. If any past record
is edited after the fact, its stored hash no longer matches a recomputed
hash of its contents, AND every record after it breaks too - so tampering
is detectable, not just logged and hoped nobody notices.

This is intentionally NOT a real blockchain (no consensus, no
distributed nodes) - it's the minimum mechanism that gives tamper
EVIDENCE, backed by SQLite for real persistence across restarts.
"""
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ledger.db"

GENESIS_HASH = "0" * 64


@dataclass
class LedgerRecord:
    id: int
    transaction_id: str
    timestamp: str
    payload_json: str
    prev_hash: str
    this_hash: str


def _hash_record(transaction_id: str, timestamp: str, payload_json: str, prev_hash: str) -> str:
    material = f"{transaction_id}|{timestamp}|{payload_json}|{prev_hash}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


class AuditLedger:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                this_hash TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def _last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT this_hash FROM ledger ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else GENESIS_HASH

    def append(self, transaction_id: str, payload: dict) -> LedgerRecord:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, sort_keys=True)
        prev_hash = self._last_hash()
        this_hash = _hash_record(transaction_id, timestamp, payload_json, prev_hash)

        cursor = self._conn.execute(
            "INSERT INTO ledger (transaction_id, timestamp, payload_json, prev_hash, this_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            (transaction_id, timestamp, payload_json, prev_hash, this_hash),
        )
        self._conn.commit()
        return LedgerRecord(cursor.lastrowid, transaction_id, timestamp, payload_json, prev_hash, this_hash)

    def get(self, transaction_id: str) -> LedgerRecord | None:
        row = self._conn.execute(
            "SELECT id, transaction_id, timestamp, payload_json, prev_hash, this_hash "
            "FROM ledger WHERE transaction_id = ? ORDER BY id DESC LIMIT 1",
            (transaction_id,),
        ).fetchone()
        return LedgerRecord(*row) if row else None

    def verify_chain(self) -> tuple[bool, int | None]:
        """Recomputes every hash from scratch and confirms the chain is
        intact. Returns (is_valid, first_broken_record_id_or_None)."""
        rows = self._conn.execute(
            "SELECT id, transaction_id, timestamp, payload_json, prev_hash, this_hash "
            "FROM ledger ORDER BY id ASC"
        ).fetchall()

        expected_prev = GENESIS_HASH
        for row in rows:
            rec_id, tx_id, ts, payload_json, prev_hash, this_hash = row
            if prev_hash != expected_prev:
                return False, rec_id
            recomputed = _hash_record(tx_id, ts, payload_json, prev_hash)
            if recomputed != this_hash:
                return False, rec_id
            expected_prev = this_hash
        return True, None

    def _tamper_for_testing(self, record_id: int, new_payload: dict) -> None:
        """Deliberately corrupts a record's stored payload WITHOUT
        recomputing its hash - simulates an attacker editing the database
        directly. Used only to demonstrate that verify_chain() detects it."""
        self._conn.execute(
            "UPDATE ledger SET payload_json = ? WHERE id = ?",
            (json.dumps(new_payload, sort_keys=True), record_id),
        )
        self._conn.commit()
