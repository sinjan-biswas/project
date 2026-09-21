/**
 * AI Border Screening System — Frontend Application
 * Backend API: http://localhost:8000
 */

const API = "http://localhost:8000";

document.addEventListener("DOMContentLoaded", () => {
  // ─── 1. API Status Check ─────────────────────────────────────
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const navIndicators = document.querySelectorAll(".api-indicator");

  async function checkHealth() {
    try {
      const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();

      if (data.status === "operational" || data.status === "ok") {
        setConnected(`Connected  v${data.version || "2.2.0"}`);
      } else {
        setDisconnected("Unexpected status");
      }
    } catch {
      setDisconnected("Disconnected");
    }
  }

  function setConnected(text) {
    if (statusDot) {
      statusDot.classList.add("connected");
      statusDot.classList.remove("disconnected");
    }
    if (statusText) {
      statusText.textContent = text;
      statusText.classList.add("connected");
      statusText.classList.remove("disconnected");
    }
    navIndicators.forEach((dot) => {
      dot.style.background = "transparent";
      dot.style.boxShadow = "none";
    });
  }

  function setDisconnected(text) {
    if (statusDot) {
      statusDot.classList.add("disconnected");
      statusDot.classList.remove("connected");
    }
    if (statusText) {
      statusText.textContent = text;
      statusText.classList.add("disconnected");
      statusText.classList.remove("connected");
    }
    navIndicators.forEach((dot) => {
      dot.style.background = "transparent";
      dot.style.boxShadow = "none";
    });
  }

  checkHealth();

  // ─── 2. Smooth Scroll Navigation ─────────────────────────────
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (e) => {
      const targetId = link.getAttribute("href");
      if (!targetId || targetId === "#") return;
      const target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        // Close mobile menu if open
        const navLinks = document.querySelector(".nav-links");
        if (navLinks) navLinks.classList.remove("active");
      }
    });
  });

  // CTA buttons: "Scan Document" → #dashboard, "Start Screening" → trigger or scroll
  document.querySelectorAll("[data-scroll-to]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.querySelector(btn.dataset.scrollTo);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // ─── 3. Document Upload ──────────────────────────────────────
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const uploadPreview = document.getElementById("uploadPreview");

  if (dropZone) {
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("drag-over");
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    dropZone.addEventListener("click", () => {
      if (fileInput) fileInput.click();
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      const file = fileInput.files[0];
      if (file) handleFile(file);
    });
  }

  function handleFile(file) {
    // Mirrors ALLOWED_MIME and MAX_UPLOAD_BYTES in the FastAPI service.
    const validTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!validTypes.includes(file.type)) {
      showToast("Invalid file type. Please upload a JPEG, PNG, or WebP image.", "error");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      showToast("File too large. Maximum size is 10 MB.", "error");
      return;
    }

    window._docFile = file;

    const reader = new FileReader();
    reader.onload = (e) => {
      if (uploadPreview) {
        uploadPreview.src = e.target.result;
        uploadPreview.style.display = "block";
      }
      // Hide the upload prompt text, show filename
      if (dropZone) {
        const prompt = dropZone.querySelector(".upload-prompt");
        if (prompt) prompt.style.display = "none";

        let nameTag = dropZone.querySelector(".file-name-tag");
        if (!nameTag) {
          nameTag = document.createElement("p");
          nameTag.className = "file-name-tag";
          nameTag.style.cssText =
            "margin-top:8px;font-size:0.85rem;color:#00e5ff;word-break:break-all;";
          dropZone.appendChild(nameTag);
        }
        nameTag.textContent = `📄 ${file.name}`;
      }
    };
    reader.onerror = () => showToast("Failed to read the file.", "error");
    reader.readAsDataURL(file);
  }

  // ─── 4. Camera / Face Capture ────────────────────────────────
  // The React camera component emits only the user-approved photo.
  window.addEventListener("camera-photo-ready", (event) => {
    window._livePhoto = event.detail;
    showToast("Face photo selected for screening.", "success");
  });

  // ─── 5. Run Screening ────────────────────────────────────────
  const screenBtn = document.getElementById("screenBtn");
  const resultsContainer = document.getElementById("results");

  async function runScreening() {
    if (!window._docFile) {
      showToast("Please upload a document first.", "error");
      return;
    }
    if (!window._livePhoto) {
      showToast("Please capture a face photo first.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("document", window._docFile);
    formData.append("live_photo", window._livePhoto, "live.jpg");

    // Show loading state
    await checkHealth();
    if (screenBtn) {
      screenBtn.disabled = true;
      screenBtn.dataset.originalText = screenBtn.textContent;
      screenBtn.innerHTML = `<span class="spinner-inline"></span> Screening…`;
    }
    window.renderScreeningResults?.({ loading: true });
    document.getElementById("resultState")?.replaceChildren(document.createTextNode("ANALYZING"));

    try {
      const res = await fetch(`${API}/api/v2/screen`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.detail || `Server error (${res.status})`);
      }

      const data = await res.json();
      renderResults(data);
    } catch (err) {
      window.renderScreeningResults?.({ error: err.message });
      document.getElementById("resultState")?.replaceChildren(document.createTextNode("FAILED"));
      showToast(`Screening failed: ${err.message}`, "error");
    } finally {
      if (screenBtn) {
        screenBtn.disabled = false;
        screenBtn.textContent = screenBtn.dataset.originalText || "Start Screening";
      }
    }
  }

  if (screenBtn) {
    screenBtn.addEventListener("click", runScreening);
  }

  // ─── 6. Render Results ───────────────────────────────────────
  function renderResults(data) {
    const risk = data.risk_assessment || {};
    const face = data.biometrics || data.face_verification || {};
    const tamper = data.tampering || {};
    const valid = data.validation || {};

    const isTampered = tamper.is_tampered === true;
    const tamperScore = typeof tamper.tampering_score === "number" ? tamper.tampering_score : 0;
    const isValid = valid.valid === true || valid.is_valid === true;
    const faceMatch = face.match === true || face.is_match === true;
    const similarity = typeof face.similarity === "number" ? face.similarity : (typeof face.confidence === "number" ? face.confidence : 0);

    const riskLevel = risk.risk_level || risk.level || deriveRiskLevel(tamperScore);
    const riskScore = typeof risk.score === "number" ? risk.score : (typeof risk.risk_score === "number" ? risk.risk_score : tamperScore);
    const riskDecision = risk.decision || risk.recommendation || (riskLevel === "HIGH" ? "DENY" : riskLevel === "MEDIUM" ? "REVIEW" : "ALLOW");

    // ── Signals Panel ──
    updateSignal("signalEla", !isTampered, "Error Level Analysis (ELA)");
    updateSignal(
      "signalMicroPrint",
      tamperScore < 0.5,
      "Micro-Print & Guilloche Waves"
    );
    updateSignal("signalMrz", isValid, "MRZ Optical Checksum Parity");

    // ── Tamper Risk Panel ──
    const tamperScoreEl = document.getElementById("tamperScore");
    const tamperLevelEl = document.getElementById("tamperLevel");
    const tamperDescEl = document.getElementById("tamperDesc");

    if (tamperScoreEl) tamperScoreEl.textContent = tamperScore.toFixed(2);
    if (tamperLevelEl) {
      tamperLevelEl.textContent = `${riskLevel.toUpperCase()} RISK`;
      tamperLevelEl.className = `risk-badge risk-${riskLevel.toLowerCase()}`;
    }
    if (tamperDescEl) {
      tamperDescEl.textContent = getRiskDescription(riskLevel, tamperScore);
    }

    window.renderScreeningResults?.(data);
    document.getElementById("resultState")?.replaceChildren(document.createTextNode("COMPLETE"));
  }

  function updateSignal(id, passed, label) {
    const el = document.getElementById(id);
    if (!el) return;

    const badge = el.querySelector(".signal-badge") || el;
    badge.className = `signal-badge ${passed ? "pass" : "fail"}`;
    badge.textContent = passed ? "PASS" : "FAIL";

    el.classList.remove("pass", "fail");
    el.classList.add(passed ? "pass" : "fail");
  }

  function buildCard(title, icon, body) {
    return `
      <div class="result-card fade-in-up visible">
        <div class="result-card-header">
          <span class="result-icon">${icon}</span>
          <h4>${title}</h4>
        </div>
        <div class="result-card-body">
          ${body}
        </div>
      </div>`;
  }

  function buildErrorList(errors) {
    if (!Array.isArray(errors) || errors.length === 0) return "";
    return `
      <ul class="error-list">
        ${errors.map((e) => `<li>${escapeHtml(typeof e === "string" ? e : e.message || JSON.stringify(e))}</li>`).join("")}
      </ul>`;
  }

  function deriveRiskLevel(score) {
    if (score >= 0.7) return "HIGH";
    if (score >= 0.4) return "MEDIUM";
    return "LOW";
  }

  function getRiskDescription(level, score) {
    if (level === "HIGH" || level === "high") {
      return `High tampering probability detected (${score.toFixed(2)}). Document should be flagged for manual review.`;
    }
    if (level === "MEDIUM" || level === "medium") {
      return `Moderate anomalies detected (${score.toFixed(2)}). Additional verification recommended.`;
    }
    return `No significant tampering indicators found (${score.toFixed(2)}). Document appears authentic.`;
  }

  function formatTimestamp(ts) {
    if (!ts) return new Date().toLocaleString();
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // ─── 7. Intersection Observer for Animations ─────────────────
  const observerOptions = {
    root: null,
    rootMargin: "0px 0px -60px 0px",
    threshold: 0.1,
  };

  const fadeObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        fadeObserver.unobserve(entry.target);
      }
    });
  }, observerOptions);

  document.querySelectorAll("section, .fade-in-up").forEach((el) => {
    if (!el.classList.contains("visible")) {
      el.classList.add("fade-in-up");
      fadeObserver.observe(el);
    }
  });

  // ─── 8. Mobile Menu Toggle ───────────────────────────────────
  const menuToggle = document.getElementById("menuToggle");
  const navLinks = document.querySelector(".nav-links");

  if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", () => {
      navLinks.classList.toggle("active");
      menuToggle.setAttribute(
        "aria-expanded",
        navLinks.classList.contains("active")
      );
    });

    // Close menu when clicking outside
    document.addEventListener("click", (e) => {
      if (
        navLinks.classList.contains("active") &&
        !navLinks.contains(e.target) &&
        !menuToggle.contains(e.target)
      ) {
        navLinks.classList.remove("active");
        menuToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  // ─── Toast Notification Helper ────────────────────────────────
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

    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateX(0)";
    });

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(40px)";
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  // Expose for inline onclick handlers if any
  window.runScreening = runScreening;
  window.showToast = showToast;
});
