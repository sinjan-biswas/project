/* React result surface for the wizard finalize response.
   Renders: risk hero · extracted fields · liveness · tampering · CTA · case id.
   Merged data from app.js:
     - data.risk_assessment         (finalize)
     - data.tampering[]             (finalize)
     - data.liveness.{anti_spoof,face_match,blink_*} (finalize)
     - data.validation_summary       (finalize)
     - data.ocr_data.fields          (stitched from Stage 2)
     - data.validation               (stitched from Stage 2, first doc)
*/
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
  const titleCase = (s) => s
    ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : s;

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
          data?.loading ? "Running final checks…"
            : data?.error || "Complete Stages 1–3 to see the final decision."),
      ]);
    }

    // ---- normalise both response shapes ----
    const risk = data.risk_assessment || data.risk || {};
    const score = num(risk.score ?? risk.risk_score);
    const decision = String(risk.decision || risk.recommendation || "PENDING").replaceAll("_", " ");

    // tampering: array (finalize) or object (legacy)
    const tamperArr = Array.isArray(data.tampering) ? data.tampering : (data.tampering ? [data.tampering] : []);
    const worstTamper = tamperArr.reduce((acc, t) => Math.max(acc, num(t.tampering_score)), 0);
    const isTampered = worstTamper >= 65 || tamperArr.some((t) => t.is_tampered === true);

    // liveness
    const live = data.liveness || {};
    const anti = live.anti_spoof || null;
    const faceM = live.face_match || null;
    const matched = !!faceM?.passed || data.face_verification?.verified === true
      || data.biometrics?.verified === true;

    // validation
    const valSum = data.validation_summary || data.validation || {};
    const isValid = (valSum.errors?.length || 0) === 0
      && data.validation?.valid !== false;

    // fields
    const ex = data.ocr_data?.fields || data.ocr_data
      || data.extracted_fields || data.extracted
      || data.fields || {};
    const name = pick(ex, "name", "full_name", "holder_name", "holder");
    const dob = fmtDate(pick(ex, "dob", "date_of_birth", "birth_date"));
    const docNum = pick(ex, "document_number", "passport_number", "aadhaar_number",
      "pan_number", "id_number", "number", "doc_no");
    const nationality = pick(ex, "nationality", "country", "nationality_code");
    const expiry = fmtDate(pick(ex, "expiry", "date_of_expiry", "expiry_date", "valid_until"));
    const gender = pick(ex, "gender", "sex");
    const docType = pick(data, "document_type", "doc_type")
      || pick(data.ocr_data || {}, "document_type")
      || pick(ex, "document_type", "doc_type", "type");

    // CTA
    let cta = null, ctaTone = "info";
    if (isTampered)        { cta = `Tampering signals elevated (${worstTamper.toFixed(1)}). Flag for manual inspection.`; ctaTone = "fail"; }
    else if (!matched)     { cta = "Face did not match the document — request a new live photo or escalate."; ctaTone = "warn"; }
    else if (!isValid)     { cta = "Document validation failed — re-upload a clearer image."; ctaTone = "fail"; }
    else if (/DENY|REJECT/i.test(decision))       { cta = "Document denied. Do not proceed."; ctaTone = "fail"; }
    else if (/SECONDARY|REVIEW|MANUAL/i.test(decision)) { cta = "Manual review recommended before clearance."; ctaTone = "warn"; }
    else if (/APPROVE|ALLOW/i.test(decision))     { cta = "All checks passed — proceed with clearance."; ctaTone = "pass"; }

    const ctaColors = ctaTone === "pass"
      ? { bg: "#f0fdf4", border: "#bbf7d0", fg: "#166534", icon: "fas fa-circle-check" }
      : ctaTone === "fail"
        ? { bg: "#fef2f2", border: "#fecaca", fg: "#991b1b", icon: "fas fa-circle-xmark" }
        : ctaTone === "warn"
          ? { bg: "#fffbeb", border: "#fde68a", fg: "#92400e", icon: "fas fa-triangle-exclamation" }
          : { bg: "#eff6ff", border: "#bfdbfe", fg: "#1e40af", icon: "fas fa-circle-info" };

    return h("div", { style: { display: "flex", flexDirection: "column" } }, [

      // ── 1. Risk hero ────────────────────────────────────
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

      // ── 2. Extracted document info ──────────────────────
      h("div", { key: "doc", style: cardStyle }, [
        h("div", { key: "h", style: headerStyle }, docType ? `Document · ${titleCase(docType)}` : "Document Details"),
        h(InfoRow, { key: "n", label: "Name", value: name }),
        h(InfoRow, { key: "d", label: "Date of Birth", value: dob }),
        h(InfoRow, { key: "g", label: "Gender", value: gender ? titleCase(gender) : null }),
        h(InfoRow, { key: "id", label: "Document No.", value: docNum }),
        h(InfoRow, { key: "nat", label: "Nationality", value: nationality }),
        h(InfoRow, { key: "exp", label: "Expiry", value: expiry }),
        (!name && !dob && !docNum) && h("p", {
          key: "empty", style: { color: "#94a3b8", fontSize: "0.85rem", margin: "8px 0 0" },
        }, "No fields could be read from the document."),
      ]),

      // ── 3. Liveness + face match ────────────────────────
      (live.blink_count != null || anti || faceM) && h("div", { key: "live", style: cardStyle }, [
        h("div", { key: "h", style: headerStyle }, "Liveness Check"),
        h("div", { key: "b", style: rowStyle }, [
          h("span", { key: "l", style: labelStyle }, "Blink Challenge"),
          h("span", { key: "v", style: labelStyle }, `${num(live.blink_count)} / ${num(live.blink_target)}`),
          h(Pill, { key: "p", text: num(live.blink_count) >= num(live.blink_target) ? "PASS" : "FAIL",
                    tone: num(live.blink_count) >= num(live.blink_target) ? "pass" : "fail" }),
        ]),
        anti && h("div", { key: "a", style: rowStyle }, [
          h("span", { key: "l", style: labelStyle }, "Anti-Spoof"),
          h("span", { key: "v", style: { ...valueStyle, fontSize: "0.8rem" } }, `score ${num(anti.score).toFixed(3)}`),
          h(Pill, { key: "p", text: anti.passed ? "LIVE" : "SPOOF", tone: anti.passed ? "pass" : "fail" }),
        ]),
        faceM && h("div", { key: "f", style: { ...rowStyle, borderBottom: "none" } }, [
          h("span", { key: "l", style: labelStyle }, "Face Match"),
          h("span", { key: "v", style: { ...valueStyle, fontSize: "0.8rem" } }, `distance ${num(faceM.distance).toFixed(3)}`),
          h(Pill, { key: "p", text: faceM.passed ? "MATCH" : "MISMATCH", tone: faceM.passed ? "pass" : "fail" }),
        ]),
      ]),

      // ── 4. Tampering ────────────────────────────────────
      tamperArr.length > 0 && h("div", { key: "tamp", style: cardStyle }, [
        h("div", { key: "h", style: headerStyle }, `Tampering · ${tamperArr.length} document${tamperArr.length === 1 ? "" : "s"}`),
        tamperArr.map((t, i) => h("div", { key: i, style: rowStyle }, [
          h("span", { key: "l", style: labelStyle }, `Doc ${t.index ?? i}`),
          h("span", { key: "v", style: valueStyle }, num(t.tampering_score).toFixed(1)),
          h(Pill, { key: "p", text: t.is_tampered ? "TAMPERED" : "CLEAN", tone: t.is_tampered ? "fail" : "pass" }),
        ])),
      ]),

      // ── 5. Validation errors ────────────────────────────
      valSum.errors && valSum.errors.length > 0 && h("div", { key: "err", style: cardStyle }, [
        h("div", { key: "h", style: headerStyle }, "Validation"),
        valSum.errors.map((e, i) => h("p", {
          key: i,
          style: { margin: "4px 0", fontSize: "0.82rem", color: "#991b1b" },
        }, `• ${e}`)),
      ]),

      // ── 6. Next step ────────────────────────────────────
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

      // ── 7. Case id ──────────────────────────────────────
      data.blockchain?.screening_id && h("p", {
        key: "id",
        style: { marginTop: "10px", fontSize: "0.72rem", color: "#94a3b8", textAlign: "center", fontFamily: "monospace" },
      }, `Case ${data.blockchain.screening_id} · ${data.blockchain.recorded ? "on-chain" : "not recorded"}`),
    ]);
  }

  window.renderScreeningResults = (data) => root.render(h(Results, { data }));
  window.renderScreeningResults();
})();