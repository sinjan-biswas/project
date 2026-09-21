/* React result surface: risk hero + extracted fields + verification checks + CTA. */
(function () {
  const rootElement = document.getElementById("results");
  if (!rootElement || !window.React || !window.ReactDOM) return;

  const h = window.React.createElement;
  const root = window.ReactDOM.createRoot(rootElement);

  const num = (v) => (typeof v === "number" ? v : 0);
  const pick = (obj, ...keys) => {
    if (!obj) return null;
    for (const k of keys) {
      const v = obj[k];
      if (v != null && v !== "" && v !== "null" && v !== "undefined") return v;
    }
    return null;
  };
  const fmtDate = (v) => {
    if (!v) return null;
    const s = String(v);
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : s;
  };
  const titleCase = (s) => s ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : s;

  const labelStyle = { color: "#6b7280", fontSize: "0.74rem", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600 };
  const valueStyle = { fontWeight: 600, color: "#0f172a", fontSize: "0.95rem", textAlign: "right" };
  const rowStyle = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid #f1f5f9", gap: "12px" };
  const cardStyle = { padding: "14px 16px", background: "#fff", border: "1px solid #e2e8f0", borderRadius: "10px", marginTop: "12px" };
  const headerStyle = { fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "#64748b", marginBottom: "8px", fontWeight: 700 };

  function Pill({ text, tone }) {
    const s = tone === "pass"
      ? { bg: "#dcfce7", fg: "#166534" }
      : tone === "fail"
        ? { bg: "#fee2e2", fg: "#991b1b" }
        : { bg: "#fef3c7", fg: "#92400e" };
    return h("span", {
      style: { background: s.bg, color: s.fg, borderRadius: "999px", padding: "3px 10px", fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.04em" }
    }, text);
  }

  function InfoRow({ label, value }) {
    if (value == null || value === "") return null;
    return h("div", { style: rowStyle }, [
      h("span", { key: "l", style: labelStyle }, label),
      h("span", { key: "v", style: valueStyle }, String(value)),
    ]);
  }

  function decisionStyle(d) {
    const s = String(d || "").toUpperCase();
    if (s.includes("DENY") || s.includes("REJECT")) return { background: "#fee2e2", color: "#991b1b", border: "1px solid #fecaca" };
    if (s.includes("SECONDARY") || s.includes("REVIEW") || s.includes("MANUAL")) return { background: "#fef3c7", color: "#92400e", border: "1px solid #fde68a" };
    if (s.includes("APPROVE") || s.includes("ALLOW") || s.includes("PASS")) return { background: "#dcfce7", color: "#166534", border: "1px solid #bbf7d0" };
    return { background: "#e0e7ff", color: "#3730a3", border: "1px solid #c7d2fe" };
  }
  const riskColor = (score) => score > 70 ? "#dc2626" : score >= 30 ? "#d97706" : "#16a34a";

  function Results({ data }) {
    if (!data || data.loading || data.error) {
      const isErr = !!data?.error;
      return h("div", {
        style: { textAlign: "center", padding: "40px 12px", color: isErr ? "#991b1b" : "#64748b" }
      }, [
        h("i", {
          key: "i",
          className: data?.loading ? "fas fa-spinner fa-spin" : isErr ? "fas fa-triangle-exclamation" : "fas fa-clipboard-check",
          style: { fontSize: "28px", marginBottom: "10px", display: "block" },
        }),
        h("p", { key: "p", style: { margin: 0, fontSize: "0.9rem" } },
          data?.loading ? "Analyzing identity and document integrity…"
            : data?.error || "Upload a document and capture a live photo to begin."),
      ]);
    }

    const risk = data.risk_assessment || data.risk || {};
    const face = data.biometrics || data.face_verification || {};
    const tamper = data.tampering || {};
    const validation = data.validation || {};

    const score = num(risk.score ?? risk.risk_score);
    const decision = (risk.decision || risk.recommendation || "PENDING").replaceAll("_", " ");
    const matched = face.match === true || face.is_match === true || face.verified === true;
    const isTampered = tamper.is_tampered === true || tamper.tampered === true;
    const isValid = validation.valid === true || validation.is_valid === true;

    const ex = data.ocr_data?.fields || data.ocr_data || data.ocr?.fields || data.ocr
      || data.extracted_fields || data.extracted || data.fields
      || data.document_fields || data.document || {};

    const name = pick(ex, "name", "full_name", "holder_name", "holder");
    const dob = fmtDate(pick(ex, "dob", "date_of_birth", "birth_date"));
    const docNum = pick(ex, "document_number", "passport_number", "aadhaar_number",
      "pan_number", "id_number", "number", "doc_no");
    const nationality = pick(ex, "nationality", "country", "nationality_code");
    const expiry = fmtDate(pick(ex, "expiry", "date_of_expiry", "expiry_date", "valid_until"));
    const gender = pick(ex, "gender", "sex");
    const docType = pick(data, "document_type", "doc_type")
      || pick(ex, "document_type", "doc_type", "type")
      || pick(data.ocr_data || {}, "document_type");

    let cta = null, ctaTone = "info";
    if (isTampered) { cta = "Tampering detected — flag for manual inspection, do not proceed."; ctaTone = "fail"; }
    else if (!isValid) { cta = "Document validation failed — ask the traveller to reupload a clearer, uncropped image."; ctaTone = "fail"; }
    else if (!matched) { cta = "Face does not match the document — request a new live photo or escalate."; ctaTone = "warn"; }
    else if (/DENY|REJECT/i.test(decision)) { cta = "Document denied. Do not proceed."; ctaTone = "fail"; }
    else if (/SECONDARY|REVIEW|MANUAL/i.test(decision)) { cta = "Manual review recommended before clearance."; ctaTone = "warn"; }
    else if (/APPROVE|ALLOW/i.test(decision)) { cta = "All checks passed — proceed with clearance."; ctaTone = "pass"; }

    const ctaColors = ctaTone === "pass"
      ? { bg: "#f0fdf4", border: "#bbf7d0", fg: "#166534", icon: "fas fa-circle-check" }
      : ctaTone === "fail"
        ? { bg: "#fef2f2", border: "#fecaca", fg: "#991b1b", icon: "fas fa-circle-xmark" }
        : ctaTone === "warn"
          ? { bg: "#fffbeb", border: "#fde68a", fg: "#92400e", icon: "fas fa-triangle-exclamation" }
          : { bg: "#eff6ff", border: "#bfdbfe", fg: "#1e40af", icon: "fas fa-circle-info" };

    return h("div", { style: { display: "flex", flexDirection: "column" } }, [

      // ── 1. Risk score hero ─────────────────────────────
      h("div", {
        key: "hero",
        style: {
          textAlign: "center", padding: "18px 12px 16px", borderRadius: "12px",
          background: "linear-gradient(135deg, #f8fafc 0%, #eef2f7 100%)",
          border: "1px solid #e2e8f0",
        },
      }, [
        h("div", { key: "l", style: { ...labelStyle, marginBottom: "4px" } }, "Risk Score"),
        h("div", {
          key: "s",
          style: { fontSize: "46px", fontWeight: 800, lineHeight: 1, color: riskColor(score), fontFamily: "inherit" },
        }, score.toFixed(1)),
        h("div", { key: "d", style: { marginTop: "12px" } },
          h("span", {
            style: {
              display: "inline-block", padding: "6px 14px", borderRadius: "999px",
              fontSize: "0.78rem", fontWeight: 700, letterSpacing: "0.06em",
              ...decisionStyle(decision),
            },
          }, decision)),
      ]),

      // ── 2. Extracted document info ─────────────────────
      h("div", { key: "doc", style: cardStyle }, [
        h("div", { key: "h", style: headerStyle }, docType ? `Document · ${titleCase(docType)}` : "Document Details"),
        h(InfoRow, { key: "n", label: "Name", value: name }),
        h(InfoRow, { key: "d", label: "Date of Birth", value: dob }),
        h(InfoRow, { key: "g", label: "Gender", value: gender ? titleCase(gender) : null }),
        h(InfoRow, { key: "id", label: "Document No.", value: docNum }),
        h(InfoRow, { key: "nat", label: "Nationality", value: nationality }),
        h(InfoRow, { key: "exp", label: "Expiry", value: expiry }),
        (!name && !dob && !docNum) && h("p", {
          key: "empty",
          style: { color: "#94a3b8", fontSize: "0.85rem", margin: "8px 0 0" },
        }, "No fields could be read from the document. Reupload a clearer image."),
      ]),

      // ── 3. Verification checks ─────────────────────────
      h("div", { key: "checks", style: cardStyle }, [
        h("div", { key: "h", style: headerStyle }, "Verification Checks"),
        h("div", { key: "f", style: rowStyle }, [
          h("span", { key: "l", style: labelStyle }, "Face Verified"),
          h(Pill, { key: "v", text: matched ? "YES" : "NO", tone: matched ? "pass" : "fail" }),
        ]),
        h("div", { key: "t", style: rowStyle }, [
          h("span", { key: "l", style: labelStyle }, "Tampering Detected"),
          h(Pill, { key: "v", text: isTampered ? "YES" : "NO", tone: isTampered ? "fail" : "pass" }),
        ]),
        h("div", { key: "val", style: { ...rowStyle, borderBottom: "none" } }, [
          h("span", { key: "l", style: labelStyle }, "Validation"),
          h(Pill, { key: "v", text: isValid ? "VALID" : "INVALID", tone: isValid ? "pass" : "fail" }),
        ]),
      ]),

      // ── 4. Action / next step ──────────────────────────
      cta && h("div", {
        key: "cta",
        style: {
          marginTop: "12px", padding: "12px 14px",
          background: ctaColors.bg, border: `1px solid ${ctaColors.border}`,
          borderRadius: "10px", color: ctaColors.fg,
          fontSize: "0.85rem", fontWeight: 600, lineHeight: 1.5,
        },
      }, [
        h("i", { key: "i", className: ctaColors.icon, style: { marginRight: "8px" } }),
        h("span", { key: "t" }, cta),
      ]),

      // ── 5. Case ID ─────────────────────────────────────
      data.screening_id && h("p", {
        key: "id",
        style: { marginTop: "10px", fontSize: "0.72rem", color: "#94a3b8", textAlign: "center", fontFamily: "monospace" },
      }, `Case ${data.screening_id}`),
    ]);
  }

  window.renderScreeningResults = (data) => root.render(h(Results, { data }));
  window.renderScreeningResults();
})();