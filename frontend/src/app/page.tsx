'use client';

import { useState, ChangeEvent, FormEvent } from 'react';

const API_BASE = "http://127.0.0.1:8000";

const PRESETS: Record<string, any> = {
  clean: {
    sender_id: "SND-DEMO-1",
    amount: 5000,
    currency: "ZAR",
    beneficiary_id: "BEN-DEMO-1",
    beneficiary_name: "Thabo Nkosi",
    account_number: "9988776655",
    bank_name: "Absa",
    country: "South Africa",
    invoice_number: "INV-DEMO-1",
    po_number: "PO-55210",
    invoice_amount: 5000,
    invoice_date: "2026-08-18",
    name_on_document: "Thabo Nkosi",
  },
  hard: {
    sender_id: "SND-DEMO-1",
    amount: 70000,
    currency: "ZAR",
    beneficiary_id: "BEN-NEW-999",
    beneficiary_name: "Coastal Trading Co",
    account_number: "1234567890",
    bank_name: "Absa",
    country: "South Africa",
    invoice_number: "INV-999",
    po_number: "PO-88213",
    invoice_amount: 70000,
    invoice_date: "2026-08-18",
    name_on_document: "Coastal Trading Co",
  },
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function Home() {
  const [formData, setFormData] = useState({
    sender_id: '', amount: '', currency: 'ZAR',
    beneficiary_id: '', beneficiary_name: '', account_number: '', bank_name: '', country: '',
    invoice_number: '', po_number: '', invoice_amount: '', invoice_date: '', name_on_document: ''
  });

  const [uploadStatus, setUploadStatus] = useState({ text: 'Click to choose an invoice image (PNG, JPEG, WEBP)', status: 'idle' });
  
  // Pipeline and result state
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [activeStage, setActiveStage] = useState<string>('');
  const [doneStages, setDoneStages] = useState<string[]>([]);
  const [chainStatus, setChainStatus] = useState({ text: '', valid: false });

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const applyPreset = (type: 'clean' | 'hard') => {
    setFormData((prev) => ({ ...prev, ...PRESETS[type] }));
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus({ text: 'Reading invoice with OCR...', status: 'loading' });

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/ocr/extract`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();

      const filled: string[] = [];
      const missed: string[] = [];

      const updates: any = {};
      if (data.invoice_amount) { updates.invoice_amount = data.invoice_amount; filled.push("amount"); } else missed.push("amount");
      if (data.po_number) { updates.po_number = data.po_number; filled.push("PO number"); } else missed.push("PO number");
      if (data.invoice_date) { updates.invoice_date = data.invoice_date; filled.push("date"); } else missed.push("date");

      setFormData(prev => ({ ...prev, ...updates }));

      if (missed.length === 0) {
        setUploadStatus({ text: `OCR filled: ${filled.join(", ")}. Review below.`, status: 'success' });
      } else {
        setUploadStatus({ text: `OCR missed: ${missed.join(", ")}. Please enter manually.`, status: 'warning' });
      }
    } catch (err: any) {
      setUploadStatus({ text: `Failed to process: ${err.message}`, status: 'error' });
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsEvaluating(true);
    setError(null);
    setResult(null);
    setDoneStages([]);
    setChainStatus({ text: '', valid: false });

    const payload = {
      sender_id: formData.sender_id,
      amount: parseFloat(formData.amount),
      currency: formData.currency,
      beneficiary: {
        beneficiary_id: formData.beneficiary_id,
        name: formData.beneficiary_name,
        account_number: formData.account_number,
        bank_name: formData.bank_name,
        country: formData.country,
      },
      invoice: {
        invoice_number: formData.invoice_number,
        po_number: formData.po_number,
        invoice_amount: parseFloat(formData.invoice_amount),
        invoice_date: formData.invoice_date,
        name_on_document: formData.name_on_document,
      },
    };

    // Simulate pipeline animation
    const stages = ["verify", "check", "score", "route"];
    let currentDone: string[] = [];
    for (const stage of stages) {
      setActiveStage(stage);
      await sleep(220);
      currentDone.push(stage);
      setDoneStages([...currentDone]);
    }
    setActiveStage("send");

    try {
      const res = await fetch(`${API_BASE}/payments/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      
      setResult(data);
      if (data.decision === "proceed") {
        setDoneStages([...currentDone, "send"]);
        setActiveStage("");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsEvaluating(false);
    }
  };

  const verifyChain = async () => {
    setChainStatus({ text: 'Checking...', valid: false });
    try {
      const res = await fetch(`${API_BASE}/audit/verify/chain`);
      const data = await res.json();
      if (data.chain_valid) {
        setChainStatus({ text: `Chain valid — ${data.total_records} records, no tampering`, valid: true });
      } else {
        setChainStatus({ text: `Chain broken at record ${data.first_broken_record_id}`, valid: false });
      }
    } catch {
      setChainStatus({ text: "Could not reach audit endpoint", valid: false });
    }
  };

  // Pipeline helper
  const isDone = (stage: string) => doneStages.includes(stage);
  const isActive = (stage: string) => activeStage === stage;

  return (
    <div className="min-h-screen bg-white text-[#1B2A41] font-sans">
      <header className="bg-[#13294B] text-white px-8 py-6 flex flex-wrap items-baseline gap-5">
        <div className="flex items-center gap-3">
          <span className="bg-[#2E6DA4] font-serif font-bold h-9 w-9 flex items-center justify-center rounded-full text-sm">TP</span>
          <span className="font-serif font-bold text-2xl tracking-wide">ThembaPay</span>
        </div>
        <p className="italic text-[#8FBDE0] text-sm m-0">Every payment takes the safest route, at the lowest cost, in the shortest time.</p>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 md:grid-cols-[420px_1fr] gap-6">
        
        {/* Left Form Panel */}
        <section className="bg-white border border-[#C9D9EA] rounded-xl p-6">
          <h1 className="font-serif text-[#13294B] text-2xl mb-1">Send a payment</h1>
          <p className="text-[#5B7089] text-sm mb-4">Fill in the details, or load a scenario to see the system respond instantly.</p>

          <div className="grid grid-cols-2 gap-3 mb-6">
            <button onClick={() => applyPreset('clean')} className="text-left border border-[#C9D9EA] bg-[#D9E9F8] rounded-lg p-3 hover:shadow-md transition">
              <div className="font-bold text-[#13294B] text-sm">Clean payment</div>
              <div className="text-xs text-[#5B7089]">Known beneficiary, matching invoice</div>
            </button>
            <button onClick={() => applyPreset('hard')} className="text-left border border-[#C9D9EA] bg-[#D9E9F8] rounded-lg p-3 hover:shadow-md transition">
              <div className="font-bold text-[#13294B] text-sm">Hard case</div>
              <div className="text-xs text-[#5B7089]">New beneficiary, high value</div>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <fieldset className="border-t border-[#C9D9EA] pt-3">
              <legend className="font-serif font-bold text-[#2E6DA4] pr-2 text-sm">Payment</legend>
              <label className="flex flex-col gap-1 text-xs text-[#5B7089] mb-3">Sender ID
                <input name="sender_id" value={formData.sender_id} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
              </label>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Amount
                  <input type="number" name="amount" value={formData.amount} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Currency
                  <input name="currency" value={formData.currency} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
              </div>
            </fieldset>

            <fieldset className="border-t border-[#C9D9EA] pt-3">
              <legend className="font-serif font-bold text-[#2E6DA4] pr-2 text-sm">Beneficiary</legend>
              <label className="flex flex-col gap-1 text-xs text-[#5B7089] mb-3">Beneficiary ID
                <input name="beneficiary_id" value={formData.beneficiary_id} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
              </label>
              <label className="flex flex-col gap-1 text-xs text-[#5B7089] mb-3">Name
                <input name="beneficiary_name" value={formData.beneficiary_name} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
              </label>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Account number
                  <input name="account_number" value={formData.account_number} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Bank
                  <input name="bank_name" value={formData.bank_name} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
              </div>
              <label className="flex flex-col gap-1 text-xs text-[#5B7089] mb-3">Country
                <input name="country" value={formData.country} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
              </label>
            </fieldset>

            <fieldset className="bg-[#D9E9F8] border border-dashed border-[#2E6DA4] rounded-lg p-4">
              <legend className="font-serif font-bold text-[#2E6DA4] pr-2 text-sm">Invoice image (optional)</legend>
              <label className="flex flex-col items-center justify-center p-3 mt-2 border border-[#C9D9EA] bg-white rounded cursor-pointer hover:bg-gray-50 text-sm font-bold text-[#2E6DA4] text-center">
                <input type="file" onChange={handleFileUpload} accept="image/*" className="hidden" />
                {uploadStatus.text}
              </label>
            </fieldset>

            <fieldset className="border-t border-[#C9D9EA] pt-3">
              <legend className="font-serif font-bold text-[#2E6DA4] pr-2 text-sm">Invoice Details</legend>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Invoice number
                  <input name="invoice_number" value={formData.invoice_number} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">PO number
                  <input name="po_number" value={formData.po_number} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Invoice amount
                  <input type="number" name="invoice_amount" value={formData.invoice_amount} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Invoice date
                  <input type="date" name="invoice_date" value={formData.invoice_date} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
                </label>
              </div>
              <label className="flex flex-col gap-1 text-xs text-[#5B7089]">Name on document
                <input name="name_on_document" value={formData.name_on_document} onChange={handleInputChange} required className="text-sm p-2 border border-[#C9D9EA] rounded text-[#1B2A41]" />
              </label>
            </fieldset>

            <button type="submit" disabled={isEvaluating} className="w-full bg-[#13294B] hover:bg-[#2E6DA4] text-white font-bold py-3 rounded-lg disabled:bg-[#5B7089]">
              {isEvaluating ? 'Evaluating...' : 'Evaluate payment'}
            </button>
          </form>
        </section>

        {/* Right Result Panel */}
        <section className="bg-white border border-[#C9D9EA] rounded-xl p-6">
          <h1 className="font-serif text-[#13294B] text-2xl mb-4">Evaluation</h1>

          <ul className="flex justify-between relative mb-8">
            {['verify', 'check', 'score', 'route', 'send'].map((stage) => (
              <li key={stage} className="flex flex-col items-center flex-1 z-10 text-xs text-[#5B7089]">
                <div className={`h-4 w-4 rounded-full mb-1 transition-all duration-300 ${isDone(stage) ? 'bg-[#2E8B57]' : isActive(stage) ? 'bg-[#2E6DA4] scale-125' : 'bg-[#C9D9EA]'}`} />
                <span className={isDone(stage) || isActive(stage) ? 'font-bold text-[#13294B]' : ''}>{stage.charAt(0).toUpperCase() + stage.slice(1)}</span>
              </li>
            ))}
            <div className="absolute top-2 left-[10%] right-[10%] h-0.5 bg-[#C9D9EA] -z-10" />
          </ul>

          {!result && !error && (
            <div className="text-center text-[#5B7089] italic py-8">
              Submit a payment on the left to see it evaluated in real time.
            </div>
          )}

          {error && (
            <div className="bg-[#FBEAEA] border border-[#B23A48] text-[#B23A48] rounded-lg p-4 text-sm">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-4">
              <div className={`rounded-lg p-4 text-white flex justify-between items-center ${result.decision === 'proceed' ? 'bg-[#2E8B57]' : result.decision === 'flag' ? 'bg-[#C98A2B]' : 'bg-[#B23A48]'}`}>
                <span className="font-serif font-bold text-xl uppercase tracking-wider">{result.decision === 'flag' ? 'Flagged for review' : result.decision}</span>
                <span className="text-2xl font-bold">{result.trust_score.score.toFixed(1)} / 100</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-[#D9E9F8] p-4 rounded-lg">
                  <h2 className="font-serif text-[#2E6DA4] font-bold text-sm mb-3">Trust factors</h2>
                  <ul className="text-sm space-y-2">
                    {result.trust_score.top_factors.map((f: any, i: number) => (
                      <li key={i} className="flex justify-between border-b border-black/5 pb-1">
                        <span>{f.feature.replace(/_/g, " ")}</span>
                        <span className={`font-bold ${f.contribution >= 0 ? 'text-[#B23A48]' : 'text-[#2E8B57]'}`}>
                          {f.contribution >= 0 ? '+' : ''}{f.contribution.toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-[#D9E9F8] p-4 rounded-lg">
                  <h2 className="font-serif text-[#2E6DA4] font-bold text-sm mb-3">Document check</h2>
                  <div className="font-serif text-2xl font-bold text-[#13294B] mb-2">{(result.document_check.consistency_score * 100).toFixed(0)}%</div>
                  <ul className="text-sm space-y-1">
                    {result.document_check.flags.length === 0 ? (
                      <li className="font-bold text-[#2E8B57]">No issues found</li>
                    ) : (
                      result.document_check.flags.map((flag: string, i: number) => <li key={i} className="border-b border-black/5 pb-1">{flag}</li>)
                    )}
                  </ul>
                </div>

                <div className="bg-[#D9E9F8] p-4 rounded-lg">
                  <h2 className="font-serif text-[#2E6DA4] font-bold text-sm mb-3">Route</h2>
                  <div className="font-serif text-xl font-bold text-[#13294B] mb-1">{result.route.rail}</div>
                  <div className="text-sm mb-1">R{result.route.estimated_cost_zar.toFixed(2)} • ~{result.route.estimated_time_hours} hrs</div>
                  <div className="text-xs text-[#5B7089]">{result.route.reason}</div>
                </div>

                <div className="bg-[#D9E9F8] p-4 rounded-lg flex flex-col justify-between">
                  <div>
                    <h2 className="font-serif text-[#2E6DA4] font-bold text-sm mb-2">Audit trail</h2>
                    <div className="font-mono text-[0.65rem] break-all text-[#5B7089] mb-3">Hash: {result.ledger_hash}</div>
                  </div>
                  <div>
                    <button onClick={verifyChain} className="bg-[#13294B] hover:bg-[#2E6DA4] text-white text-xs px-3 py-2 rounded">Verify chain integrity</button>
                    {chainStatus.text && (
                      <div className={`text-xs font-bold mt-2 ${chainStatus.valid ? 'text-[#2E8B57]' : 'text-[#B23A48]'}`}>{chainStatus.text}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}