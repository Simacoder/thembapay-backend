from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
import json
import hashlib
import re
from PIL import Image
import pytesseract
import numpy as np

router = APIRouter(prefix="/qr", tags=["QR"])

class QRPaymentRequest(BaseModel):
    sender_id: str
    amount: float
    currency: str = "ZAR"
    beneficiary_id: str
    beneficiary_name: str
    invoice_number: str
    po_number: Optional[str] = None
    purpose: Optional[str] = None

class QRTrustResponse(BaseModel):
    qr_code: str  # base64 encoded QR
    payment_id: str
    trust_score: float
    verification_status: str
    qr_data: Dict[str, Any]
    expires_at: str

class QRScanResult(BaseModel):
    payment_id: str
    trust_score: float
    decision: str  # proceed, flag, block
    verification_details: Dict[str, Any]
    seller_history: Dict[str, Any]
    buyer_history: Dict[str, Any]
    optimised_route: Dict[str, Any]

# In-memory storage (replace with database in production)
qr_sessions = {}
transaction_history = {
    "SND-DEMO-1": {
        "transactions": 45,
        "avg_amount": 12500,
        "success_rate": 0.98,
        "disputes": 1,
        "trust_level": 0.95
    },
    "BEN-DEMO-1": {
        "transactions": 30,
        "avg_amount": 8900,
        "success_rate": 0.97,
        "disputes": 0,
        "trust_level": 0.94
    }
}

@router.post("/generate")
async def generate_qr(request: QRPaymentRequest):
    """Generate a Universal QR code for payment with trust scoring"""
    
    # Generate unique payment ID
    payment_id = f"QR-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(json.dumps(request.dict()).encode()).hexdigest()[:8].upper()}"
    
    # Calculate trust score based on history
    trust_score = calculate_trust_score(request.sender_id, request.beneficiary_id, request.amount)
    
    # Prepare QR data
    qr_data = {
        "payment_id": payment_id,
        "sender_id": request.sender_id,
        "amount": request.amount,
        "currency": request.currency,
        "beneficiary_id": request.beneficiary_id,
        "beneficiary_name": request.beneficiary_name,
        "invoice_number": request.invoice_number,
        "po_number": request.po_number,
        "purpose": request.purpose,
        "timestamp": datetime.now().isoformat(),
        "trust_score": trust_score,
        "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        "version": "1.0"
    }
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps(qr_data))
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    # Store session
    qr_sessions[payment_id] = {
        "data": qr_data,
        "created_at": datetime.now(),
        "status": "active",
        "scanned": False
    }
    
    return QRTrustResponse(
        qr_code=img_str,
        payment_id=payment_id,
        trust_score=trust_score,
        verification_status="ready",
        qr_data=qr_data,
        expires_at=qr_data["expires_at"]
    )

@router.post("/scan")
async def scan_qr(
    file: UploadFile = File(...),
    sender_id: Optional[str] = Form(None)
):
    """Scan and verify a QR code payment"""
    
    # Read and decode QR
    try:
        contents = await file.read()
        image = Image.open(BytesIO(contents))
        
        # Use QR code decoding
        import pyzbar.pyzbar as pyzbar
        decoded = pyzbar.decode(image)
        
        if not decoded:
            raise HTTPException(status_code=400, detail="No QR code found in image")
        
        # Parse QR data
        qr_data = json.loads(decoded[0].data.decode('utf-8'))
        payment_id = qr_data.get("payment_id")
        
        if payment_id not in qr_sessions:
            raise HTTPException(status_code=404, detail="Payment session not found")
        
        session = qr_sessions[payment_id]
        session["scanned"] = True
        
        # Verify trust
        trust_result = verify_trust(qr_data, sender_id)
        
        # OCR verification of document if provided
        ocr_verification = await verify_ocr_document(file)
        
        # Get buyer and seller history
        buyer_history = get_buyer_history(qr_data.get("sender_id"))
        seller_history = get_seller_history(qr_data.get("beneficiary_id"))
        
        # Optimise route
        optimised_route = optimise_route(qr_data, trust_result)
        
        return QRScanResult(
            payment_id=payment_id,
            trust_score=trust_result["score"],
            decision=trust_result["decision"],
            verification_details={
                "ocr_verified": ocr_verification,
                "trust_check": trust_result,
                "timestamp": datetime.now().isoformat()
            },
            seller_history=seller_history,
            buyer_history=buyer_history,
            optimised_route=optimised_route
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QR scanning failed: {str(e)}")

@router.get("/verify/{payment_id}")
async def verify_qr_payment(payment_id: str):
    """Verify a QR payment's trust status"""
    
    if payment_id not in qr_sessions:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    session = qr_sessions[payment_id]
    
    return {
        "payment_id": payment_id,
        "status": session["status"],
        "scanned": session["scanned"],
        "trust_score": session["data"]["trust_score"],
        "created_at": session["created_at"].isoformat()
    }

def calculate_trust_score(sender_id: str, beneficiary_id: str, amount: float) -> float:
    """Calculate trust score based on historical data"""
    
    base_score = 50.0  # Start neutral
    
    # Sender history
    sender_history = transaction_history.get(sender_id, {})
    if sender_history:
        base_score += sender_history.get("trust_level", 0) * 20
        if sender_history.get("disputes", 0) > 0:
            base_score -= min(20, sender_history.get("disputes", 0) * 5)
        base_score += min(10, (sender_history.get("success_rate", 0.5) - 0.5) * 20)
    
    # Beneficiary history
    beneficiary_history = transaction_history.get(beneficiary_id, {})
    if beneficiary_history:
        base_score += beneficiary_history.get("trust_level", 0) * 15
        if beneficiary_history.get("disputes", 0) > 0:
            base_score -= min(15, beneficiary_history.get("disputes", 0) * 4)
    
    # Amount risk adjustment
    if amount > 50000:
        base_score -= 10
    elif amount > 100000:
        base_score -= 20
    elif amount < 1000:
        base_score += 5  # Small payments are lower risk
    
    # Normalize to 0-100
    return max(0, min(100, base_score))

def verify_trust(qr_data: Dict, sender_id: Optional[str]) -> Dict:
    """Verify trust based on multiple factors"""
    
    trust_score = qr_data.get("trust_score", 50)
    
    # Check if payment is expired
    expires_at = datetime.fromisoformat(qr_data.get("expires_at", "2000-01-01T00:00:00"))
    if datetime.now() > expires_at:
        return {"score": 0, "decision": "block", "reason": "QR code expired"}
    
    # Verify sender matches
    if sender_id and qr_data.get("sender_id") != sender_id:
        return {"score": trust_score * 0.5, "decision": "flag", "reason": "Sender mismatch"}
    
    # Decision based on trust score
    if trust_score >= 70:
        decision = "proceed"
        reason = "High trust score"
    elif trust_score >= 40:
        decision = "flag"
        reason = "Moderate trust score - requires review"
    else:
        decision = "block"
        reason = "Low trust score - payment blocked"
    
    return {
        "score": trust_score,
        "decision": decision,
        "reason": reason,
        "expires_at": qr_data.get("expires_at")
    }

async def verify_ocr_document(file: UploadFile) -> Dict:
    """Verify document using OCR"""
    
    try:
        # This is a placeholder - in production, you'd use proper OCR
        # and document verification
        
        # Check if it's an image
        if file.content_type.startswith('image/'):
            return {
                "verified": True,
                "method": "ocr",
                "confidence": 0.85,
                "extracted_fields": {
                    "document_type": "invoice",
                    "fields_found": ["amount", "date", "reference"]
                }
            }
        else:
            return {
                "verified": False,
                "method": "ocr",
                "confidence": 0.0,
                "error": "Invalid file type for OCR"
            }
    except:
        return {
            "verified": False,
            "method": "ocr",
            "confidence": 0.0,
            "error": "OCR processing failed"
        }

def get_buyer_history(sender_id: str) -> Dict:
    """Get buyer transaction history"""
    
    history = transaction_history.get(sender_id, {})
    return {
        "id": sender_id,
        "total_transactions": history.get("transactions", 0),
        "avg_transaction_value": history.get("avg_amount", 0),
        "success_rate": history.get("success_rate", 0) * 100,
        "disputes": history.get("disputes", 0),
        "trust_level": history.get("trust_level", 0) * 100
    }

def get_seller_history(beneficiary_id: str) -> Dict:
    """Get seller transaction history"""
    
    history = transaction_history.get(beneficiary_id, {})
    return {
        "id": beneficiary_id,
        "total_transactions": history.get("transactions", 0),
        "avg_transaction_value": history.get("avg_amount", 0),
        "success_rate": history.get("success_rate", 0) * 100,
        "disputes": history.get("disputes", 0),
        "trust_level": history.get("trust_level", 0) * 100
    }

def optimise_route(qr_data: Dict, trust_result: Dict) -> Dict:
    """Optimise payment routing based on trust and other factors"""
    
    amount = qr_data.get("amount", 0)
    trust_score = trust_result.get("score", 50)
    
    # Base routing logic
    if amount < 1000:
        rail = "Instant EFT"
        cost = amount * 0.001  # 0.1%
        time_hours = 0.1  # ~6 minutes
        reason = "Small amount - best for Instant EFT"
    elif amount < 50000:
        if trust_score > 70:
            rail = "Faster Payment"
            cost = amount * 0.005  # 0.5%
            time_hours = 0.5
            reason = "Medium amount, high trust - Faster Payment"
        else:
            rail = "SWIFT gpi"
            cost = amount * 0.015  # 1.5%
            time_hours = 2
            reason = "Medium amount, moderate trust - SWIFT with tracking"
    else:
        if trust_score > 80:
            rail = "RTGS"
            cost = amount * 0.01  # 1%
            time_hours = 0.25
            reason = "High value, high trust - Real-time settlement"
        else:
            rail = "SWIFT gpi + Manual Review"
            cost = amount * 0.02  # 2%
            time_hours = 24
            reason = "High value, lower trust - Enhanced verification"
    
    return {
        "rail": rail,
        "estimated_cost": round(cost, 2),
        "estimated_time_hours": time_hours,
        "reason": reason,
        "currency": qr_data.get("currency", "ZAR")
    }