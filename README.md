# ThembaPay

**The intelligence payment acceptance orchestration API for African merchants.**

ThembaPay is an API layer that sits between a merchant and every payment rail available to them. Merchants integrate once — through one Universal QR code — and ThembaPay orchestrates every transaction across every available rail (PayShap, bank apps, mobile wallets, and future PAPSS rails), routing each payment through the cheapest, fastest, safest option in real time.

> Not a payment app. Not another wallet. Infrastructure.

Built for the **EDHE Absa Studentpreneurs Indaba FinTech Hackathon** (September 2026) — Team UNISA.

---

## Why ThembaPay exists

Small businesses lose margin every time a customer pays them:

- **2–3%** of every transaction goes to card fees for small SA merchants — large retailers pay under 1% for the same underlying interchange *(Launchworks, 2026)*
- A 3% turnover fee can consume **~30% of real profit**, not just revenue *(Launchworks, 2026)*
- Merchants in South Africa are **not allowed to pass card fees to customers** as a surcharge — the cost must be absorbed *(PASА, via Vutivi 2026)*
- Accepting payment at all often means **multiple separate integrations** — a card machine, a QR provider, a bank EFT link

**ThembaPay fixes this with one integration and one QR code.**

---

## Key features

| Feature | What it does |
|---|---|
| **Universal QR** | One QR code accepts PayShap, Absa, FNB, Nedbank, Capitec, mobile wallets — and future PAPSS wallets. The merchant never cares which method was used. |
| **AI Trust Engine** | XGBoost + SHAP scores every transaction in real time. Every score ships with a feature-level explanation — auditable, not a black box. |
| **OCR document verification** | Validates invoices and receipts for fraud signals (name mismatches, amount tampering, bad PO numbers). |
| **Smart payment router** | Picks the cheapest, fastest available rail per transaction — cost, speed and reliability compared instantly. |
| **Hash-chained audit ledger** | Every decision is appended to a tamper-evident, hash-chained log in O(1) time. |
| **No funds custody** | ThembaPay evaluates and recommends only. Settlement happens on the rails; ThembaPay never holds money. |

### Validated results (measured, not claimed)

- **98.1%** average OCR text agreement — live-verified across 200 real invoice images
- **100% / 100%** invoice number / date extraction accuracy (199/199 valid samples)
- **1.000 ROC-AUC** trust-scoring model on held-out test split (synthetic fraud patterns)
- **21 vs 99 / 100** trust score: hard fraud case (new beneficiary + high value + clean invoice) vs clean transaction
- **<400 ms** end-to-end response target — a hard design constraint for pre-authorisation use
- **Zero** card credentials ever stored — by architecture, not just policy

---

## Architecture

```
Merchant                     ThembaPay                        Rails
────────                     ─────────                        ─────
Universal QR  ───────────▶   FastAPI (auth + validation)
                             │
                             ▼
                             AI Trust Engine  ──▶  XGBoost score + SHAP explanation
                             │                        OCR document check
                             ▼
                             Payment Router ──────▶  cheapest/fastest rail
                             │
                             ▼
                             Audit Ledger (hash-chained, tamper-evident)
                                                       │
                             ◀─────────────────────────┘
                        Merchant gets paid
```

Engineering choices, deliberately:

- **XGBoost, not deep learning** — strongest performer on small tabular data; scores in milliseconds on a CPU, no GPU needed
- **Stateless API** — every `/payments/evaluate` call is independent; scales horizontally
- **Rule-based checks first** — cheap, instant checks catch obvious fraud before the ML model is invoked
- **O(1) audit append** — the tamper-evident ledger never slows down as history grows

---

## Tech stack

- **Backend:** FastAPI (Python)
- **ML:** XGBoost + SHAP (TreeExplainer)
- **OCR:** document verification pipeline
- **Ledger:** hash-chained append-only audit log
- **Frontend:** demo UI (`frontend/`)
- **Data:** 600 synthetic training transactions (200 unique beneficiaries, ~16% deliberately elevated fraud rate, 5 engineered features); OCR benchmarked live against 200 real invoice images (`mychen76/invoices-and-receipts_ocr_v1`)

> **Honest caveat:** model metrics reflect clean, rule-based synthetic fraud patterns — proof the pipeline works end-to-end, not a real-world accuracy claim. Rail cost/speed figures are illustrative placeholders; the routing *logic* is real and testable. Real performance needs pilot validation on live data.

---

## Project structure

```
thembapay-backend/
├── backend/          # FastAPI trust engine, ML pipeline, routing, audit ledger
├── frontend/         # Demo UI — clean payment → approval; risky payment → flagged
├── .vscode/          # Editor configuration
└── README.md
```

---

## Quickstart (runs in under 5 minutes)

### 1. Clone the repo

```bash
git clone https://github.com/Simacoder/thembapay-backend.git
cd thembapay-backend
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API is now running at `http://localhost:8000` — interactive docs at `http://localhost:8000/docs`.

### 3. Frontend demo

```bash
cd frontend
# follow the frontend README / serve statically, e.g.:
python -m http.server 3000
```

Open `http://localhost:3000` — try a **clean payment → instant approval**, then a **risky payment → correctly flagged, live**.

---

## API

### `POST /payments/evaluate`

Pre-authorisation check: verifies the beneficiary, runs document checks, scores the transaction, and recommends a route.

```json
{
  "beneficiary": "Acme Suppliers Pty Ltd",
  "amount_zar": 12500.00,
  "is_new_beneficiary": true,
  "document": { "invoice_number": "INV-2026-0412", ... }
}
```

**Response:**

```json
{
  "trust_score": 21,
  "risk_tier": "high",
  "explanation": { "document_consistency_score": -1.8, "amount_log": -0.9, ... },
  "recommended_rail": "SWIFT + manual compliance review",
  "audit_hash": "a91f...e7"
}
```

**Routing logic (real, testable — figures are illustrative until live rail integration):**

| Condition | Route |
|---|---|
| Domestic (South Africa) | PayShap — fastest, cheapest |
| PAPSS corridor (Kenya, Nigeria, Ghana, Zambia, Botswana) | PAPSS — avoids correspondent banking |
| Elsewhere | SWIFT fallback |
| High risk tier — regardless of destination | SWIFT + **manual compliance review** — speed is never prioritised over safety |

The bank/merchant decides: **proceed, flag, or block**. ThembaPay never touches the money.

---

## Roadmap

1. **Today** — PayShap: live, domestic South African rail
2. **Tomorrow** — PAPSS: pan-African settlement interoperability
3. **Next** — Visa, Mastercard, Apple Pay, Google Pay, M-Pesa, MoMo: every major rail, same merchant integration

---

## Team UNISA

| Member | Role |
|---|---|
| **Patience Mabuza** | Business & Insight |
| **Tshepo Mhlaba** | Software Engineer |
| **Simanga Mchunu** | ML Engineer |

---

## References

- Launchworks — *The true cost of credit card fees in South Africa*: https://www.launchworks.co.za/articles/true-cost-credit-card-fees-south-africa
- Payment Association of South Africa (PASA) — FAQ: https://pasa.org.za/about-payments/pasa-faq/
- Vutivi Business — *Small businesses anticipate steady economic gains in 2026*: https://vutivibusiness.co.za/business/small-businesses-anticipate-steady-economic-gains-in-2026/

## License

MIT (or as specified in the repository)
