# ThembaPay — Backend

Trust-scoring and route-recommendation engine for cross-border payments.
Built for the EDHE Studentpreneurs Indaba FinTech Hackathon (Absa),
9 September 2026. Team NexaPay.

This README is written so every claim in it can be checked by running a
command, not taken on faith. If a step doesn't produce the output shown,
something is broken — stop and fix it before moving to the next step.

---

## What's actually verified vs. what isn't

**Verified by running real code against real inputs, in this build:**
- Synthetic data generation (600 transactions, documented fraud patterns)
- Document consistency checker (rule-based, 100% precision / 81% recall alone on synthetic data)
- Trust-scoring model (XGBoost + SHAP), holdout-evaluated, catches the case document checks structurally can't
- Route optimizer (transparent lookup table)
- Hash-chained audit ledger — including a real simulated tamper attack that it correctly detected
- Full FastAPI app, tested end-to-end over real HTTP
- Tesseract OCR extraction — a real image round-tripped through OCR into correct structured fields
- **Eclipse (EFT Corp) sandbox client** — JWT parsing and request-building logic tested against Eclipse's own *documented* sample response and field names (see `tests/test_eclipse_client.py`). The endpoint paths, auth flow, and payment/fraud-event field names are real, sourced from developer.eftcorp.com. **Not yet tested against a live Eclipse sandbox — we don't have onboarded credentials.** Set `ECLIPSE_BASE_URL`, `ECLIPSE_IDENTITY`, `ECLIPSE_PASSWORD`, `ECLIPSE_TENANT_ID` env vars once you have them; without them the API correctly reports `rail_call_status: "skipped_no_sandbox_credentials_configured"` rather than pretending success — confirmed by running the app live with no credentials set.

**Explicitly NOT verified — do not present these as working without doing the step described:**
- **Unlimited-OCR (baidu/Unlimited-OCR) integration** — written against the model's published card, but never executed. Needs a CUDA GPU and internet access to huggingface.co, neither available in the environment this was built in. **Run `ml/verify_unlimited_ocr.py` on real GPU hardware before claiming this works in a demo or pitch.**
- **Absa Access integration** — the earlier mock (`app/integrations/absa_mock.py`) has been superseded by a real client against **Eclipse (EFT Corp)'s** documented sandbox (`app/integrations/eclipse_client.py`), because Absa's developer portal has no visible self-serve signup. Eclipse's sandbox is publicly documented and notably supports Absa-linked test accounts (bank code 632005), so the demo tests real rail behavior involving Absa accounts today. Absa Access remains the named production target for the pitch — swapping clients later is a contained change since both implement the same interface. **Get real sandbox credentials from Eclipse before demo day and set the `ECLIPSE_*` env vars — this has only been tested against their documented response shapes with mocked HTTP, not a live server.**
- **PP-OCRv6 (paddleocr)** — pip package confirmed to install and import cleanly. Weight download fails in this sandbox specifically due to a network-allowlist restriction (`bcebos.com` blocked) — **confirmed as a network issue, not a code issue**, and unlike Unlimited-OCR this needs no GPU, so any team laptop with normal internet can verify it via `ml/verify_ppocr.py`.
- **The 100% holdout accuracy on the trust model is a synthetic-data artifact**, not a real-world performance claim. The fraud patterns in the training data are cleanly rule-based, so a model can learn them perfectly. Say this out loud to judges rather than letting a slide imply real-world 100% accuracy — it will read as more credible, not less.
- **The insights notebook found and fixed two real bugs during development** — worth knowing about, not just the fixed numbers: (1) a stale-registry bug made "new beneficiary" show 0%/100% depending on ordering, fixed by using a fresh registry per measurement; (2) an early economic model used the synthetic training fraud rate (~15%, deliberately inflated for ML training) as if it were a real-world fraud rate, producing an impossible "R1 billion prevented against R600M processed" result — replaced with a labeled sensitivity range (0.1%-1% loss rate) and a standing sanity-check assertion.

---

## Step-by-step setup (each step has a verification command)

### 1. Environment
```bash
cd backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```
**Verify:**
```bash
./venv/bin/python -c "import fastapi, xgboost, pandas, faker, shap, pytesseract; print('all imports OK')"
```
Expected: `all imports OK`

### 2. Generate synthetic data
```bash
./venv/bin/python ml/generate_synthetic_data.py
```
**Verify:** should print `Fraud rate in generated data: ~13%` and create `data/synthetic/transactions.csv` and `beneficiaries.json`. Open the CSV yourself and spot-check a few rows against their `fraud_patterns` column.

### 3. Train the trust-scoring model
```bash
./venv/bin/python ml/train_trust_model.py
```
**Verify:** prints a holdout classification report (not training-set numbers) and saves `ml/model/trust_model.json`. If precision/recall look suspiciously perfect, that's expected on this synthetic data — see caveats above.

### 4. Run the automated test suite
```bash
rm -f data/ledger.db   # start from a clean ledger
./venv/bin/python -m pytest tests/ -v
```
**Verify:** all tests pass, including `test_new_beneficiary_high_amount_clean_invoice_is_still_caught` — this is the specific test proving the ML layer catches something the rule-based checker can't.

### 5. Start the API and hit it for real
```bash
./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```
In another terminal:
```bash
curl http://127.0.0.1:8000/health
```
Expected: `{"status":"ok","service":"thembapay-api"}`

### 6. Evaluate a real payment
```bash
curl -s -X POST http://127.0.0.1:8000/payments/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "SND-DEMO-1",
    "amount": 5000,
    "currency": "ZAR",
    "beneficiary": {
      "beneficiary_id": "BEN-DEMO-1",
      "name": "Thabo Nkosi",
      "account_number": "9988776655",
      "bank_name": "Absa",
      "country": "South Africa"
    },
    "invoice": {
      "invoice_number": "INV-DEMO-1",
      "po_number": "PO-55210",
      "invoice_amount": 5000,
      "invoice_date": "2026-08-18",
      "name_on_document": "Thabo Nkosi"
    }
  }' | python3 -m json.tool
```
**Verify:** `decision: "proceed"`, `route.rail: "PayShap"`, a `ledger_hash` that's a 64-character hex string.

### 7. Check the audit trail
```bash
curl http://127.0.0.1:8000/audit/verify/chain
```
Expected: `{"chain_valid": true, ...}`

---

### 8. Run the insights notebook (economic + social impact analysis)
```bash
./venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/thembapay_insights.ipynb
```
**Verify:** executes with zero errors and includes a sanity-check `assert` that would fail loudly if a projected fraud-prevention figure ever exceeded total value processed (it caught exactly this bug once during development — see the notebook's Section 7 comments). Figures are saved to `notebooks/figures/` for direct use in the pitch deck.

## Project structure
```
backend/
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── schemas.py                # API contract (Pydantic)
│   ├── api/
│   │   ├── payments.py           # POST /payments/evaluate — orchestrates everything below
│   │   └── audit.py               # GET /audit/{tx_id}, GET /audit/verify/chain
│   ├── engines/
│   │   ├── verify.py              # beneficiary history check
│   │   ├── document_check.py      # rule-based invoice consistency check
│   │   ├── ocr_extract.py         # OCR: Tesseract (verified) + Unlimited-OCR (spec'd, untested)
│   │   ├── trust_score.py         # XGBoost + SHAP wrapper
│   │   └── route_optimizer.py     # PayShap / PAPSS / SWIFT lookup table
│   ├── ledger/
│   │   └── hash_chain.py          # tamper-evident audit log
│   └── integrations/
│       └── absa_mock.py           # MOCK - clearly labeled, no real credentials
├── ml/
│   ├── generate_synthetic_data.py
│   ├── train_trust_model.py
│   ├── verify_ppocr.py            # run on ANY laptop, no GPU needed
│   ├── verify_unlimited_ocr.py    # run this on GPU hardware before demo day
│   └── model/trust_model.json     # trained model artifact
├── notebooks/
│   ├── thembapay_insights.ipynb   # economic + social impact analysis - source of truth for pitch numbers
│   ├── build_notebook.py          # regenerates the notebook structure from source
│   └── figures/                   # PNG charts exported for the pitch deck
├── data/synthetic/                # generated data (gitignored in a real repo)
├── tests/
│   ├── test_api.py
│   └── test_ocr.py
└── requirements.txt
```

## Decision thresholds (in `app/api/payments.py`)
- Trust score < 40 → **block**
- Trust score 40–70 → **flag** for manual review
- Trust score ≥ 70 → **proceed**

These are starting values for the demo, not tuned against real fraud-loss data — say so if asked.

## Check list
1. The document checker alone gets 100% precision / 81% recall on synthetic data — the 19% it misses is exactly why the trust-score model exists on top.
2. The trust model's 100% holdout score reflects clean synthetic fraud patterns, not real-world performance.
3. Route cost/speed figures are illustrative placeholders, not live rail pricing.
4. Absa integration is a mock matching Absa Access's likely shape — the ask is sandbox credentials, not "already built."
5. Unlimited-OCR is written to spec but unverified — run `ml/verify_unlimited_ocr.py` on GPU hardware first, or demo with Tesseract, which is verified.
