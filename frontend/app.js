// API_BASE is relative by default, since the frontend is served BY the
// same FastAPI app it talks to (see app/main.py). If you ever host the
// frontend separately from the backend, change this to the backend's
// full URL, e.g. "https://thembapay-api.onrender.com"
const API_BASE = "";

const PRESETS = {
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

const form = document.getElementById("payment-form");
const submitBtn = document.getElementById("submit-btn");
const pipeline = document.getElementById("pipeline");
const emptyState = document.getElementById("empty-state");
const resultContent = document.getElementById("result-content");
const errorState = document.getElementById("error-state");
const errorMessage = document.getElementById("error-message");

document.querySelectorAll(".preset-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const preset = PRESETS[btn.dataset.preset];
    Object.entries(preset).forEach(([key, value]) => {
      const field = form.elements.namedItem(key);
      if (field) field.value = value;
    });
  });
});

const uploadInput = document.getElementById("invoice-upload");
const uploadStatus = document.getElementById("upload-status");
const uploadLabelText = document.getElementById("upload-label-text");

uploadInput.addEventListener("change", async () => {
  const file = uploadInput.files[0];
  if (!file) return;

  uploadLabelText.textContent = file.name;
  uploadStatus.textContent = "Reading invoice with OCR...";
  uploadStatus.className = "upload-status loading";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/ocr/extract`, { method: "POST", body: formData });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errBody.detail || `Server returned ${res.status}`);
    }
    const result = await res.json();

    const filledFields = [];
    const missedFields = [];

    if (result.invoice_amount !== null) {
      form.elements.namedItem("invoice_amount").value = result.invoice_amount;
      filledFields.push("amount");
    } else {
      missedFields.push("amount");
    }

    if (result.po_number !== null) {
      form.elements.namedItem("po_number").value = result.po_number;
      filledFields.push("PO number");
    } else {
      missedFields.push("PO number");
    }

    if (result.invoice_date !== null) {
      form.elements.namedItem("invoice_date").value = result.invoice_date;
      filledFields.push("date");
    } else {
      missedFields.push("date");
    }

    if (missedFields.length === 0) {
      uploadStatus.textContent = `OCR filled in: ${filledFields.join(", ")}. Review below, then add the beneficiary name and invoice number (those aren't auto-extracted yet).`;
      uploadStatus.className = "upload-status success";
    } else {
      uploadStatus.textContent = `OCR filled in: ${filledFields.join(", ") || "nothing"}. Could not read: ${missedFields.join(", ")} \u2014 please enter those manually.`;
      uploadStatus.className = "upload-status warning";
    }
  } catch (err) {
    uploadStatus.textContent = `Could not process this image: ${err.message}`;
    uploadStatus.className = "upload-status error";
  }
});


function formToPayload(formEl) {
  const data = new FormData(formEl);
  return {
    sender_id: data.get("sender_id"),
    amount: parseFloat(data.get("amount")),
    currency: data.get("currency"),
    beneficiary: {
      beneficiary_id: data.get("beneficiary_id"),
      name: data.get("beneficiary_name"),
      account_number: data.get("account_number"),
      bank_name: data.get("bank_name"),
      country: data.get("country"),
    },
    invoice: {
      invoice_number: data.get("invoice_number"),
      po_number: data.get("po_number"),
      invoice_amount: parseFloat(data.get("invoice_amount")),
      invoice_date: data.get("invoice_date"),
      name_on_document: data.get("name_on_document"),
    },
  };
}

function setPipelineStage(stageName, state) {
  // state: "active" | "done"
  const stages = ["verify", "check", "score", "route", "send"];
  const targetIndex = stages.indexOf(stageName);
  stages.forEach((s, i) => {
    const li = pipeline.querySelector(`[data-stage="${s}"]`);
    li.classList.remove("active", "done");
    if (i < targetIndex) li.classList.add("done");
    if (i === targetIndex) li.classList.add(state);
  });
}

function resetPipeline() {
  pipeline.querySelectorAll("li").forEach((li) => li.classList.remove("active", "done"));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function animatePipeline(finalDecision) {
  const stages = ["verify", "check", "score", "route"];
  for (const stage of stages) {
    setPipelineStage(stage, "active");
    await sleep(220);
    setPipelineStage(stage, "done");
  }
  setPipelineStage("send", finalDecision === "proceed" ? "done" : "active");
}

function formatFactorName(name) {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function renderResult(result) {
  const banner = document.getElementById("decision-banner");
  const label = document.getElementById("decision-label");
  const score = document.getElementById("decision-score");

  banner.className = "decision-banner " + result.decision;
  const decisionText = { proceed: "Proceed", flag: "Flagged for review", block: "Blocked" };
  label.textContent = decisionText[result.decision] || result.decision;
  score.textContent = `${result.trust_score.score.toFixed(1)} / 100`;

  const factorList = document.getElementById("factor-list");
  factorList.innerHTML = "";
  result.trust_score.top_factors.forEach((f) => {
    const li = document.createElement("li");
    const contribClass = f.contribution >= 0 ? "positive" : "negative";
    const sign = f.contribution >= 0 ? "+" : "";
    li.innerHTML = `<span class="factor-name">${formatFactorName(f.feature)}</span>` +
      `<span class="factor-contribution ${contribClass}">${sign}${f.contribution.toFixed(2)}</span>`;
    factorList.appendChild(li);
  });

  document.getElementById("doc-score").textContent =
    `${(result.document_check.consistency_score * 100).toFixed(0)}% consistent`;
  const flagList = document.getElementById("flag-list");
  flagList.innerHTML = "";
  if (result.document_check.flags.length === 0) {
    flagList.innerHTML = '<li class="no-flags">No issues found</li>';
  } else {
    result.document_check.flags.forEach((flag) => {
      const li = document.createElement("li");
      li.textContent = flag;
      flagList.appendChild(li);
    });
  }

  document.getElementById("route-rail").textContent = result.route.rail;
  document.getElementById("route-detail").textContent =
    `R${result.route.estimated_cost_zar.toFixed(2)} \u2022 ~${result.route.estimated_time_hours < 1
      ? Math.round(result.route.estimated_time_hours * 60) + " min"
      : result.route.estimated_time_hours + " hrs"}`;
  document.getElementById("route-reason").textContent = result.route.reason;

  document.getElementById("audit-hash").textContent = `Ledger hash: ${result.ledger_hash}`;
  document.getElementById("chain-status").textContent = "";
  document.getElementById("chain-status").className = "chain-status";
}

async function checkChainIntegrity() {
  const statusEl = document.getElementById("chain-status");
  statusEl.textContent = "Checking...";
  statusEl.className = "chain-status";
  try {
    const res = await fetch(`${API_BASE}/audit/verify/chain`);
    const data = await res.json();
    if (data.chain_valid) {
      statusEl.textContent = `Chain valid \u2014 ${data.total_records} records, no tampering detected`;
      statusEl.className = "chain-status valid";
    } else {
      statusEl.textContent = `Chain broken at record ${data.first_broken_record_id}`;
      statusEl.className = "chain-status invalid";
    }
  } catch (err) {
    statusEl.textContent = "Could not reach audit endpoint";
    statusEl.className = "chain-status invalid";
  }
}

document.getElementById("verify-chain-btn").addEventListener("click", checkChainIntegrity);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = "Evaluating...";
  emptyState.classList.add("hidden");
  errorState.classList.add("hidden");
  resultContent.classList.add("hidden");
  resetPipeline();

  const payload = formToPayload(form);
  const pipelineAnim = animatePipeline("pending");

  try {
    const res = await fetch(`${API_BASE}/payments/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errBody = await res.text();
      throw new Error(`Server returned ${res.status}: ${errBody}`);
    }

    const result = await res.json();
    await pipelineAnim;
    setPipelineStage("send", result.decision === "proceed" ? "done" : "active");
    renderResult(result);
    resultContent.classList.remove("hidden");
  } catch (err) {
    await pipelineAnim;
    errorMessage.textContent = `Could not evaluate this payment: ${err.message}`;
    errorState.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Evaluate payment";
  }
});
