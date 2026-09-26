import { useEffect, useState } from "react";
import {
  History, Loader2, AlertTriangle, ChevronRight, ChevronDown,
  ShieldCheck, Lock, RefreshCw,
} from "lucide-react";

const fmtDate = (iso) => {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
};

const decisionTone = (d) => {
  const s = String(d || "").toUpperCase();
  if (s.includes("DENY") || s.includes("REJECT"))
    return "text-error bg-error/10 border-error/30";
  if (s.includes("SECONDARY") || s.includes("REVIEW") || s.includes("MANUAL"))
    return "text-amber-700 bg-amber-500/10 border-amber-400/30";
  if (s.includes("APPROVE"))
    return "text-emerald-800 bg-emerald-500/10 border-emerald-400/30";
  return "text-on-surface-variant bg-surface-container-high border-outline-variant";
};

const riskTone = (s) => {
  const n = Number(s || 0);
  if (n > 70) return "text-error";
  if (n >= 30) return "text-amber-600";
  return "text-emerald-700";
};

export default function ScreeningHistory() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v2/history?checkpoint=JFK_01&limit=50");
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      setRows(data.screenings || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggleRow = async (sid) => {
    if (expanded === sid) { setExpanded(null); setDetail(null); return; }
    setExpanded(sid);
    setDetail(null);
    try {
      const res = await fetch(`/api/v2/history/${sid}`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      setDetail(await res.json());
    } catch (e) {
      setDetail({ error: e.message });
    }
  };

  return (
    <section id="history" className="w-full bg-surface py-20 px-6 md:px-12 border-t border-emerald-100">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-6">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-secondary-container text-primary font-label-sm uppercase tracking-wider mb-2 border border-emerald-200">
              <History className="w-3.5 h-3.5" />
              Audit Trail
            </div>
            <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface">
              Screening History
            </h2>
            <p className="font-body-sm text-on-surface-variant mt-1 max-w-xl">
              Every verification is committed to the Hyperledger Fabric ledger.
              This list reads directly from the chain — no cached copies.
            </p>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="px-4 py-2 rounded-full bg-surface-container-high hover:bg-surface-container text-on-surface font-label-sm text-xs font-bold transition-all flex items-center gap-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Body */}
        <div className="rounded-2xl bg-surface-container-lowest border border-emerald-200 shadow-sm overflow-hidden">
          {loading && (
            <div className="p-12 text-center">
              <Loader2 className="w-8 h-8 mx-auto text-primary animate-spin mb-3" />
              <div className="font-mono text-xs text-on-surface-variant">Querying ledger…</div>
            </div>
          )}

          {!loading && error && (
            <div className="p-6">
              <div className="rounded-xl bg-error-container/40 border border-error/30 p-4 flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-error shrink-0 mt-0.5" />
                <div>
                  <div className="font-label-sm text-xs font-bold text-on-error-container mb-1">
                    Could not read history
                  </div>
                  <div className="font-mono text-[11px] text-on-error-container">{error}</div>
                  <div className="font-mono text-[10px] text-on-surface-variant mt-2">
                    Hint: uvicorn must be started from a shell with <b>fabric-samples/bin</b> on PATH.
                  </div>
                </div>
              </div>
            </div>
          )}

          {!loading && !error && rows.length === 0 && (
            <div className="p-12 text-center">
              <ShieldCheck className="w-8 h-8 mx-auto text-on-surface-variant/40 mb-3" />
              <div className="font-headline-sm text-base font-bold text-on-surface">
                No screenings yet
              </div>
              <div className="font-mono text-xs text-on-surface-variant mt-1">
                Run the wizard above — every completed screening will appear here.
              </div>
            </div>
          )}

          {!loading && !error && rows.length > 0 && (
            <div className="divide-y divide-emerald-100">
              {/* Table header */}
              <div className="hidden md:grid grid-cols-12 gap-3 px-4 py-3 bg-surface-container-low/60 font-mono text-[10px] font-bold text-on-surface-variant uppercase tracking-wide">
                <div className="col-span-1"></div>
                <div className="col-span-3">Screening ID</div>
                <div className="col-span-3">Timestamp</div>
                <div className="col-span-2">Decision</div>
                <div className="col-span-1 text-right">Risk</div>
                <div className="col-span-2 text-right">Checkpoint</div>
              </div>

              {/* Rows */}
              {rows.map((r) => {
                const sid = r.screening_id || "—";
                const open = expanded === sid;
                return (
                  <div key={sid} className="bg-surface-container-lowest">
                    <button
                      onClick={() => toggleRow(sid)}
                      className="w-full grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-3 px-4 py-3 text-left hover:bg-surface-container-low/40 transition-colors items-center"
                    >
                      <div className="md:col-span-1 flex items-center">
                        {open
                          ? <ChevronDown className="w-4 h-4 text-primary" />
                          : <ChevronRight className="w-4 h-4 text-on-surface-variant" />}
                      </div>
                      <div className="md:col-span-3 font-mono text-xs font-bold text-on-surface truncate">
                        {sid}
                      </div>
                      <div className="md:col-span-3 font-mono text-[11px] text-on-surface-variant">
                        {fmtDate(r.timestamp)}
                      </div>
                      <div className="md:col-span-2">
                        <span className={`inline-block font-mono text-[10px] font-bold px-2 py-0.5 rounded-full border ${decisionTone(r.decision)}`}>
                          {String(r.decision || "—").replace(/_/g, " ")}
                        </span>
                      </div>
                      <div className={`md:col-span-1 md:text-right font-mono text-sm font-bold ${riskTone(r.risk_score)}`}>
                        {Number(r.risk_score ?? 0).toFixed(1)}
                      </div>
                      <div className="md:col-span-2 md:text-right font-mono text-[11px] text-on-surface-variant truncate">
                        {r.checkpoint_id || "—"}
                      </div>
                    </button>

                    {/* Expanded detail */}
                    {open && (
                      <div className="px-4 pb-4 pt-1 bg-surface-container-low/40 border-t border-emerald-100">
                        {!detail && (
                          <div className="flex items-center gap-2 py-3 text-on-surface-variant font-mono text-xs">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Loading full record…
                          </div>
                        )}
                        {detail?.error && (
                          <div className="py-3 font-mono text-xs text-error">
                            {detail.error}
                          </div>
                        )}
                        {detail?.screening && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                            <Field label="Document hash" value={detail.screening.document_hash} mono />
                            <Field label="Passport hash" value={detail.screening.passport_hash} mono />
                            <Field label="Agent signature" value={detail.screening.agent_signature || "(empty)"} />
                            <Field label="Recorded at" value={fmtDate(detail.screening.timestamp)} />
                            {detail.pii && (
                              <>
                                <Field label="Holder name" value={detail.pii.name} />
                                <Field label="Passport number" value={detail.pii.passport_number} />
                                <Field label="Date of birth" value={detail.pii.date_of_birth} />
                                <Field label="Father name" value={detail.pii.father_name} />
                              </>
                            )}
                            {!detail.pii && (
                              <div className="md:col-span-2 font-mono text-[10px] text-on-surface-variant italic">
                                Private PII collection unavailable (expired or not readable from this org).
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer note */}
        <div className="mt-4 flex items-center justify-center gap-2 font-mono text-[10px] text-on-surface-variant">
          <Lock className="w-3 h-3" />
          Read directly from <span className="text-secondary font-bold">screening-channel</span> ·
          Chaincode <span className="text-secondary font-bold">screening v2.0</span>
        </div>
      </div>
    </section>
  );
}

function Field({ label, value, mono }) {
  return (
    <div className="p-2.5 rounded-lg bg-surface-container-lowest border border-emerald-100">
      <div className="font-mono text-[9px] text-on-surface-variant uppercase">{label}</div>
      <div className={`text-xs font-bold text-on-surface mt-0.5 break-all ${mono ? "font-mono" : ""}`}>
        {value || "—"}
      </div>
    </div>
  );
}