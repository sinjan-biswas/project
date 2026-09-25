/**
 * AI Border Screening System — Wizard Orchestrator
 * Backend API: http://localhost:8000
 *
 * Stages:
 *   1. Upload + validate (POST /api/v2/documents/validate)
 *   2. Get details      (POST /api/v2/documents/details)
 *   3. Liveness         (via liveness-widget.js — untouched)
 *      → Final          (POST /api/v2/screening/finalize, dispatched by listener)
 */

const API = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {

  // ═══════════════════════════════════════════════════════════════
  // 1. API Status Check  (unchanged)
  // ═══════════════════════════════════════════════════════════════
  const statusDot  = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const navIndicators = document.querySelectorAll(".api-indicator");

  async function checkHealth() {
    try {
      const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      setConnected(`Connected  v${data.version || "3.0.0"}`);
    } catch {
      setDisconnected("Disconnected");
    }
  }
  function setConnected(text) {
    statusDot?.classList.add("connected");
    statusDot?.classList.remove("disconnected");
    if (statusText) {
      statusText.textContent = text;
      statusText.classList.add("connected");
      statusText.classList.remove("disconnected");
    }
    navIndicators.forEach(d => { d.style.background = "transparent"; d.style.boxShadow = "none"; });
  }
  function setDisconnected(text) {
    statusDot?.classList.add("disconnected");
    statusDot?.classList.remove("connected");
    if (statusText) {
      statusText.textContent = text;
      statusText.classList.add("disconnected");
      statusText.classList.remove("connected");
    }
  }
  checkHealth();

  // ═══════════════════════════════════════════════════════════════
  // 2. Smooth Scroll + Mobile Menu  (unchanged)
  // ═══════════════════════════════════════════════════════════════
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener("click", e => {
      const id = link.getAttribute("href");
      if (!id || id === "#") return;
      const target = document.querySelector(id);
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: "smooth", block: "start" }); }
    });
  });

  const menuToggle = document.getElementById("menuToggle");
  const navLinks = document.querySelector(".nav-links");
  if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", () => {
      navLinks.classList.toggle("active");
      menuToggle.setAttribute("aria-expanded", navLinks.classList.contains("active"));
    });
  }

  // ═══════════════════════════════════════════════════════════════
  // 3. Wizard State + Stage Transitions
  // ═══════════════════════════════════════════════════════════════
  const wizard = {
    stage: 1,
    files: [],               // [{id, file, previewUrl}]
    screeningSessionId: null,
    stage1Response: null,    // raw /documents/validate response
    stage2Response: null,    // raw /documents/details response
    livenessSessionId: null, // set by listener
  };
  window._wizard = wizard;   // expose for debugging + other islands

  function goToStage(n) {
    wizard.stage = n;
    document.querySelectorAll(".wizard-stage").forEach(el => {
      el.hidden = Number(el.dataset.stage) !== n;
    });
    const lbl = document.getElementById("wizardStageLabel");
    if (lbl) lbl.textContent = `${n} / 3`;
    document.getElementById("dashboard")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ═══════════════════════════════════════════════════════════════
  // 4. Stage 1 — Upload + Validate
  // ═══════════════════════════════════════════════════════════════
  const dropZone      = document.getElementById("dropZone");
  const fileInput     = document.getElementById("fileInput");
  const previewGrid   = document.getElementById("stage1PreviewGrid");
  const stage1Btn     = document.getElementById("stage1ValidateBtn");
  const stage1Result  = document.getElementById("stage1Result");
  const stage1State   = document.getElementById("stage1State");

  const ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp"];
  const MAX_FILE_BYTES = 15 * 1024 * 1024;
  const MAX_FILES = 10;

  function addFiles(incoming) {
    for (const f of incoming) {
      if (wizard.files.length >= MAX_FILES) { showToast(`Max ${MAX_FILES} files.`, "error"); break; }
      if (!ALLOWED_MIME.includes(f.type))   { showToast(`Skipped ${f.name}: unsupported type.`, "error"); continue; }
      if (f.size > MAX_FILE_BYTES)          { showToast(`Skipped ${f.name}: exceeds 15 MB.`, "error"); continue; }
      const dupe = wizard.files.some(x => x.file.name === f.name && x.file.size === f.size);
      if (dupe) continue;
      wizard.files.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        file: f,
        previewUrl: URL.createObjectURL(f),
      });
    }
    renderStage1Preview();
  }

  function removeFile(id) {
    const i = wizard.files.findIndex(x => x.id === id);
    if (i < 0) return;
    URL.revokeObjectURL(wizard.files[i].previewUrl);
    wizard.files.splice(i, 1);
    renderStage1Preview();
  }

  function renderStage1Preview() {
    if (!previewGrid) return;
    if (!wizard.files.length) {
      previewGrid.hidden = true;
      previewGrid.innerHTML = "";
      if (stage1Btn) stage1Btn.disabled = true;
      return;
    }
    previewGrid.hidden = false;
    previewGrid.innerHTML = wizard.files.map(f => `
      <div class="spg-card" data-id="${f.id}">
        <img src="${f.previewUrl}" alt="">
        <button type="button" class="spg-remove" aria-label="Remove">×</button>
        <div class="spg-meta">
          <span class="spg-name" title="${f.file.name}">${f.file.name}</span>
          <span class="spg-size">${(f.file.size / 1024).toFixed(0)} KB</span>
        </div>
      </div>
    `).join("");
    previewGrid.querySelectorAll(".spg-remove").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        removeFile(btn.closest(".spg-card").dataset.id);
      });
    });
    if (stage1Btn) stage1Btn.disabled = false;
  }

  if (dropZone) {
    dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
    dropZone.addEventListener("drop", e => {
      e.preventDefault();
      dropZone.classList.remove("drag-over");
      addFiles(e.dataTransfer.files);
    });
    dropZone.addEventListener("click", () => fileInput?.click());
  }
  fileInput?.addEventListener("change", () => {
    addFiles(fileInput.files);
    fileInput.value = "";
  });

  async function validateStage1() {
    if (!wizard.files.length) return;
    if (stage1Btn) { stage1Btn.disabled = true; stage1Btn.innerHTML = `<span class="spinner-inline"></span> Validating…`; }
    if (stage1State) stage1State.textContent = "ANALYZING";
    if (stage1Result) stage1Result.innerHTML = `<p class="text-muted">Running quality gate, enhancement, and classification…</p>`;

    const form = new FormData();
    wizard.files.forEach(f => form.append("files", f.file, f.file.name));

    try {
      const res = await fetch(`${API}/api/v2/documents/validate`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      wizard.screeningSessionId = data.session_id;
      wizard.stage1Response = data;

      renderStage1Result(data);
      if (stage1State) stage1State.textContent = data.blocked ? "BLOCKED" : "COMPLETE";

      // Convenience: expose first file for the liveness widget's legacy path
      window._docFile = wizard.files[0]?.file || null;

      // Auto-advance if everything is clean
      if (!data.blocked) {
        setTimeout(() => startStage2(), 600);
      }
    } catch (e) {
      if (stage1State) stage1State.textContent = "FAILED";
      if (stage1Result) stage1Result.innerHTML = `<p class="stage-error">${e.message}</p>`;
      showToast(`Validation failed: ${e.message}`, "error");
    } finally {
      if (stage1Btn) {
        stage1Btn.disabled = false;
        stage1Btn.innerHTML = `<i class="fas fa-play"></i> Validate Documents`;
      }
    }
  }

  function renderStage1Result(data) {
    if (!stage1Result) return;
    stage1Result.innerHTML = `
      <div class="stage1-summary ${data.blocked ? "is-blocked" : "is-ok"}">
        ${data.blocked
          ? `<i class="fas fa-triangle-exclamation"></i> Some files need attention. Remove or re-upload them, then validate again.`
          : `<i class="fas fa-circle-check"></i> All ${data.files.length} file${data.files.length===1?"":"s"} validated — advancing…`}
      </div>
      <div class="stage1-list">
        ${data.files.map(f => `
          <div class="stage1-row ${f.blocked ? "is-blocked" : ""}">
            <div class="stage1-row-body">
              <div class="stage1-row-name" title="${f.filename}">${f.filename}</div>
              <div class="stage1-row-meta">
                <span class="wz-pill wz-pill-${f.quality?.decision || "unknown"}">${f.quality?.decision || "?"}</span>
                <span>${f.classification?.doc_type ?? "unknown"}</span>
                <span class="stage1-conf">${f.classification?.confidence ? (f.classification.confidence * 100).toFixed(1) + "%" : "—"}</span>
                ${f.enhanced ? `<span class="stage1-tag">enhanced</span>` : ""}
              </div>
              ${f.blocked && f.block_reason ? `<div class="stage1-reason">${f.block_reason}</div>` : ""}
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  stage1Btn?.addEventListener("click", validateStage1);

  // ═══════════════════════════════════════════════════════════════
  // 5. Stage 2 — Get Details
  // ═══════════════════════════════════════════════════════════════
  const stage2State = document.getElementById("stage2State");

  async function startStage2() {
    if (!wizard.screeningSessionId) {
      showToast("No screening session — validate first.", "error");
      return;
    }
    goToStage(2);
    if (stage2State) stage2State.textContent = "ANALYZING";

    // Notify the details island to fetch and render
    window.dispatchEvent(new CustomEvent("stage-2-enter", {
      detail: { sessionId: wizard.screeningSessionId, api: API },
    }));
  }

  // The details island will dispatch this when it has finished rendering
  window.addEventListener("stage-2-ready", (e) => {
    wizard.stage2Response = e.detail?.data || null;
    if (stage2State) stage2State.textContent = "COMPLETE";
  });

  document.getElementById("stage2BackBtn")?.addEventListener("click", () => goToStage(1));
  document.getElementById("stage2ContinueBtn")?.addEventListener("click", () => goToStage(3));

  // ═══════════════════════════════════════════════════════════════
  // 6. Stage 3 — Liveness → Finalize
  // ═══════════════════════════════════════════════════════════════
  const resultState = document.getElementById("resultState");

  // Fired by liveness-widget.js when the user completes the check.
  // We then call /screening/finalize and hand the result to results-react.js
  window.addEventListener("liveness-verified", async (event) => {
    const detail = event.detail || {};
    wizard.livenessSessionId = detail.livenessSessionId || null;

    // Legacy fallback for the widget's internal blob — harmless
    window._livePhoto = detail.livePhoto || null;

    if (detail.unverified) {
      showToast("Liveness completed without face match — finalizing anyway.", "info");
    } else {
      showToast("Liveness verified.", "success");
    }

    if (!wizard.screeningSessionId || !wizard.livenessSessionId) {
      showToast("Missing session ids — cannot finalize.", "error");
      return;
    }

    if (resultState) resultState.textContent = "FINALIZING";
    window.renderScreeningResults?.({ loading: true });

    try {
      const res = await fetch(`${API}/api/v2/screening/finalize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          screening_session_id: wizard.screeningSessionId,
          liveness_session_id: wizard.livenessSessionId,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const final = await res.json();

      // Stitch Stage 2 OCR into the final payload so results-react.js can
      // render extracted fields alongside the risk assessment.
      if (wizard.stage2Response?.documents) {
        const first = wizard.stage2Response.documents[0] || {};
        final.ocr_data = { fields: first.fields || {}, document_type: first.doc_type };
        final.validation = first.validation || {};
      }

      window.renderScreeningResults?.(final);
      if (resultState) resultState.textContent = "COMPLETE";
      renderTamperPanel(final);
    } catch (e) {
      window.renderScreeningResults?.({ error: e.message });
      if (resultState) resultState.textContent = "FAILED";
      showToast(`Finalize failed: ${e.message}`, "error");
    }
  });

  // Simple right-side panel fill from the finalize response
  function renderTamperPanel(data) {
    const risk = data.risk_assessment || {};
    const tamps = data.tampering || [];
    const worst = tamps.reduce((acc, t) => Math.max(acc, t.tampering_score || 0), 0);

    const scoreEl = document.getElementById("tamperScore");
    const levelEl = document.getElementById("tamperLevel");
    const descEl  = document.getElementById("tamperDesc");

    if (scoreEl) scoreEl.textContent = worst.toFixed(1);
    if (levelEl) {
      const level = worst >= 70 ? "HIGH" : worst >= 30 ? "MEDIUM" : "LOW";
      levelEl.textContent = `${level} RISK`;
      levelEl.className = `risk-level-badge risk-${level.toLowerCase()}`;
    }
    if (descEl) descEl.textContent = `${tamps.length} document(s) analyzed. Decision: ${(risk.decision || "PENDING").replace("_", " ")}.`;

    // Signals
    const isValid = !(data.validation_summary?.errors?.length);
    updateSignal("signalEla", worst < 70, "Error Level Analysis (ELA)");
    updateSignal("signalMicroPrint", worst < 70, "Micro-Print & Guilloche Waves");
    updateSignal("signalMrz", isValid, "MRZ Optical Checksum Parity");
  }

  function updateSignal(id, passed) {
    const el = document.getElementById(id);
    if (!el) return;
    const badge = el.querySelector(".signal-badge") || el;
    badge.className = `signal-badge ${passed ? "pass" : "fail"}`;
    badge.textContent = passed ? "PASS" : "FAIL";
  }

  document.getElementById("stage3RestartBtn")?.addEventListener("click", () => {
    wizard.files.forEach(f => URL.revokeObjectURL(f.previewUrl));
    Object.assign(wizard, {
      files: [],
      screeningSessionId: null,
      stage1Response: null,
      stage2Response: null,
      livenessSessionId: null,
    });
    window._docFile = null;
    renderStage1Preview();
    if (stage1Result) stage1Result.innerHTML = `<p class="text-muted">Add document images and click Validate.</p>`;
    if (stage1State) stage1State.textContent = "READY";
    if (resultState) resultState.textContent = "READY";
    window.renderScreeningResults?.();
    goToStage(1);
  });

  // ═══════════════════════════════════════════════════════════════
  // 7. Intersection Observer for Animations  (unchanged)
  // ═══════════════════════════════════════════════════════════════
  const fadeObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add("visible"); fadeObserver.unobserve(entry.target); }
    });
  }, { rootMargin: "0px 0px -60px 0px", threshold: 0.1 });

  document.querySelectorAll("section, .fade-in-up").forEach(el => {
    if (!el.classList.contains("visible")) {
      el.classList.add("fade-in-up");
      fadeObserver.observe(el);
    }
  });

  // ═══════════════════════════════════════════════════════════════
  // Toast  (unchanged)
  // ═══════════════════════════════════════════════════════════════
  function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.style.cssText =
        "position:fixed;top:20px;right:20px;z-index:10000;display:flex;flex-direction:column;gap:10px;pointer-events:none;";
      document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.style.cssText = `
      pointer-events:auto;padding:14px 22px;border-radius:8px;color:#fff;
      font-size:0.9rem;font-family:inherit;max-width:380px;word-break:break-word;
      box-shadow:0 4px 20px rgba(0,0,0,0.4);opacity:0;transform:translateX(40px);
      transition:opacity .3s,transform .3s;
      background:${type === "error" ? "#d32f2f" : type === "success" ? "#2e7d32" : "#1565c0"};
    `;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = "1"; toast.style.transform = "translateX(0)"; });
    setTimeout(() => {
      toast.style.opacity = "0"; toast.style.transform = "translateX(40px)";
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }
  window.showToast = showToast;
});