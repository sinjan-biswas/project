/* Stage 2 — OCR details island. Mounts into #stageDetailsRoot. */
(function () {
  const mount = document.getElementById("stageDetailsRoot");
  if (!mount || !window.React || !window.ReactDOM) return;

  const { createElement: h, useEffect, useState } = window.React;
  const root = window.ReactDOM.createRoot(mount);

  const titleCase = s => s ? String(s).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) : s;

  const labelStyle = { color: "#94a3b8", fontSize: "0.72rem", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600, minWidth: "110px" };
  const valueStyle = { fontWeight: 600, color: "#e7eaf0", fontSize: "0.95rem", textAlign: "right", flex: 1 };
  const rowStyle = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.06)", gap: "12px" };
  const cardStyle = { padding: "16px 20px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "10px", marginTop: "12px" };

  function Row({ label, value }) {
    if (value == null || value === "") return null;
    return h("div", { style: rowStyle }, [
      h("span", { key: "l", style: labelStyle }, label),
      h("span", { key: "v", style: valueStyle }, String(value)),
    ]);
  }

  function ValidationPill({ v }) {
    if (!v) return null;
    const ok = v.valid === true;
    return h("span", {
      style: {
        display: "inline-block", padding: "3px 10px", borderRadius: "999px",
        fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.04em",
        background: ok ? "rgba(46,125,50,0.25)" : "rgba(211,47,47,0.25)",
        color: ok ? "#7fe3a0" : "#ff9a9a",
      },
    }, ok ? "VALID" : "INVALID");
  }

  function Details({ sessionId, api }) {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
      if (!sessionId) return;
      let cancelled = false;
      (async () => {
        setLoading(true); setError(null);
        try {
          const res = await fetch(`${api}/api/v2/documents/details`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
          });
          if (!res.ok) {
            const b = await res.json().catch(() => ({}));
            throw new Error(b.detail || `Server error ${res.status}`);
          }
          const json = await res.json();
          if (!cancelled) {
            setData(json);
            window.dispatchEvent(new CustomEvent("stage-2-ready", { detail: { data: json } }));
          }
        } catch (e) {
          if (!cancelled) setError(e.message);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => { cancelled = true; };
    }, [sessionId, api]);

    if (loading) return h("p", { style: { color: "#94a3b8" } }, "Reading documents…");
    if (error)   return h("p", { style: { color: "#ff9a9a" } }, `Failed: ${error}`);

    return h("div", { style: { display: "flex", flexDirection: "column", gap: "4px" } },
      (data.documents || []).map((d, i) =>
        h("div", { key: i, style: cardStyle }, [
          h("div", { key: "h", style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" } }, [
            h("span", { key: "t", style: { fontSize: "0.78rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "#64748b", fontWeight: 700 } },
              `${titleCase(d.doc_type) || "Unknown"} · ${d.filename}`),
            h(ValidationPill, { key: "v", v: d.validation }),
          ]),
          d.fields && Object.keys(d.fields).length > 0
            ? Object.entries(d.fields).map(([k, v], idx) =>
                h(Row, { key: `${k}-${idx}`, label: titleCase(k), value: v }))
            : h("p", { style: { color: "#94a3b8", fontSize: "0.85rem" } }, "No fields extracted."),
          d.mrz && d.mrz.raw && h("div", { key: "mrz", style: { ...rowStyle, flexDirection: "column", alignItems: "flex-start" } }, [
            h("span", { key: "l", style: labelStyle }, "MRZ"),
            h("code", { key: "v", style: { fontFamily: "monospace", fontSize: "0.82rem", color: "#7fe3a0", wordBreak: "break-all" } },
              Array.isArray(d.mrz.raw) ? d.mrz.raw.join("\n") : d.mrz.raw),
          ]),
          d.validation?.errors?.length > 0 && h("div", {
            key: "err",
            style: { marginTop: "10px", padding: "8px 12px", background: "rgba(211,47,47,0.12)", borderLeft: "3px solid #d32f2f", borderRadius: "4px", fontSize: "0.78rem", color: "#ffb5b5" },
          }, d.validation.errors.join(" · ")),
        ])
      )
    );
  }

  let activeSession = null;
  window.addEventListener("stage-2-enter", (e) => {
    const { sessionId, api } = e.detail || {};
    if (!sessionId) return;
    activeSession = sessionId;
    root.render(h(Details, { key: sessionId, sessionId, api }));
  });

  root.render(h("p", { style: { color: "#94a3b8" } }, "Waiting to read documents…"));
})();