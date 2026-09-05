from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import hashlib
import json

router = APIRouter(prefix="/bank", tags=["Bank Integration"])

class BankAPIIntegration:
    """Integration with bank payment systems"""
    
    def __init__(self):
        self.bank_endpoints = {
            "absa": "https://api.absa.co.za/payments",
            "standard": "https://api.standardbank.co.za/payments",
            "nedbank": "https://api.nedbank.co.za/payments",
            "fnb": "https://api.fnb.co.za/payments"
        }
    
    async def process_payment(self, payment_data: Dict, rail: str) -> Dict:
        """Process payment through appropriate bank API"""
        
        # Map rail to bank API
        bank_mapping = {
            "Instant EFT": "absa",
            "Faster Payment": "standard",
            "RTGS": "nedbank",
            "SWIFT gpi": "fnb"
        }
        
        bank = bank_mapping.get(rail, "absa")
        endpoint = self.bank_endpoints.get(bank)
        
        if not endpoint:
            raise HTTPException(status_code=400, detail="Unsupported payment rail")
        
        # Prepare bank API request
        bank_request = {
            "sender_id": payment_data.get("sender_id"),
            "beneficiary_id": payment_data.get("beneficiary_id"),
            "amount": payment_data.get("amount"),
            "currency": payment_data.get("currency", "ZAR"),
            "reference": payment_data.get("invoice_number"),
            "rail": rail,
            "timestamp": datetime.now().isoformat()
        }
        
        # In production, make actual API call
        # For demo, simulate successful response
        return {
            "status": "success",
            "transaction_id": f"TXN-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(json.dumps(bank_request).encode()).hexdigest()[:8]}",
            "bank": bank,
            "rail": rail,
            "processed_at": datetime.now().isoformat(),
            "receipt": {
                "amount": payment_data.get("amount"),
                "currency": payment_data.get("currency", "ZAR"),
                "beneficiary": payment_data.get("beneficiary_name"),
                "sender": payment_data.get("sender_id")
            }
        }

@router.post("/process")
async def process_bank_payment(payment_data: Dict[str, Any]):
    """Process payment through bank system"""
    
    integration = BankAPIIntegration()
    result = await integration.process_payment(
        payment_data,
        payment_data.get("rail", "Instant EFT")
    )
    return result