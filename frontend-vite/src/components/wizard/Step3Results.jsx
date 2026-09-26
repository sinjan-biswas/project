import { useEffect, useRef, useState } from "react";
import {
  ShieldCheck, Loader2, AlertTriangle, CheckCircle2, XCircle,
  Fingerprint, Image as ImageIcon, ScanFace, Lock, ArrowLeft, RotateCcw,
  FileText,
} from "lucide-react";
import { api } from "../../api/client";

export default function Step3Results({
  screeningSessionId, livenessSessionId, stage1, stage2, onFinal, onBack, onRestart,
}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Guards against React StrictMode double-invoking the effect in dev.
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await api.finalize(screeningSessionId, livenessSessionId);
        setData(resp);
        onFinal?.(resp);
      } catch (e) {
        // Special case: the screening session is already at stage 'final'.
        // That means a previous finalize succeeded — fetch its stored result
        // instead of showing an error. Happens on StrictMode double-invoke,
        // browser refresh, or if the user navigates back to this step.
        const msg = String(e?.message || "");
        if (msg.includes("ocr_done") || msg.includes("final")) {
          try {
            const state = await api.getScreeningState(screeningSessionId);
            if (state?.final_result) {
              setData(state.final_result);
              onFinal?.(state.final_result);
              return;
            }
          } catch { /* fall through to error */ }
        }
        setError(msg || "Finalize failed");
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screeningSessionId, livenessSessionId]);

  if (loading) {
    return (
      <div className="rounded-2xl bg-surface-container-low p-12 border border-emerald-200 text-center">
        <Loader2 className="w-8 h-8 mx-auto text-primary animate-spin mb-3" />
        <div className="font-headline-sm text-lg font-bold text-on-surface">Running final screening…</div>
        <div className="font-mono text-xs text-on-surface-variant mt-1">
          Tampering · Risk fusion · Ledger write
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-error-container/40 p-8 border border-error/30 text-center">
        <AlertTriangle className="w-8 h-8 mx-auto text-error mb-3" />
        <div className="font-headline-sm text-lg font-bold text-on-error-container">{error}</div>
        <button onClick={onBack} className="mt-4 px-5 py-2 rounded-full bg-primary text-on-primary font-bold text-xs">
          Back to liveness
        </button>
      </div>
    );
  }

  const risk = data.risk_assessment || {};
  const score = Number(risk.score ?? 0);
  const decision = String(risk.decision || "PENDING").replace(/_/g, " ");
  const tamperList = Array.isArray(data.tampering) ? data.tampering : [];
  const worstTamper = tamperList.reduce((a, t) => Math.max(a, t.tampering_score || 0), 0);
  const live = data.liveness || {};
  const anti = live.anti_spoof || {};
  const fm = live.face_match || {};
  const blockchain = data.blockchain || {};

  const stage1Files = stage1?.files || [];
  const stage2Docs = stage2?.documents || [];
  const totalFields = stage2Docs.reduce((a, d) => a + Object.keys(d.fields || {}).length, 0);
  const totalErrors = stage2Docs.reduce((a, d) => a + (d.validation?.errors?.length || 0), 0);

  const decisionTone = /DENY|REJECT/i.test(decision)
    ? { bg: "bg-error/15", fg: "text-error", border: "border-error/30", dot: "bg-error" }
    : /SECONDARY|REVIEW|MANUAL/i.test(decision)
    ? { bg: "bg-amber-500/15", fg: "text-amber-700", border: "border-amber-400/30", dot: "bg-amber-500" }
    : { bg: "bg-emerald-500/15", fg: "text-emerald-800", border: "border-emerald-400/40", dot: "bg-emerald-600" };

  const primaryType = stage1Files[0]?.classification?.doc_type || stage2Docs[0]?.doc_type;

  return (
    <div className="rounded-2xl bg-surface-container p-6 md:p-8 shadow-xl border border-emerald-200">
      <div className="space-y-6">

        {/* ─── Header ─── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-surface-variant/30 gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-on-primary shadow-md">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="font-headline-sm text-lg font-bold text-on-surface">
                {primaryType
                  ? `${cap(primaryType)}${stage1Files.length > 1 ? ` + ${stage1Files.length - 1} more` : ""} · Forensic Verdict`
                  : "Forensic Verdict"}
              </div>
              <div className="font-mono text-xs text-on-surface-variant">
                Screening {data.screening_session_id} · {stage1Files.length} document{stage1Files.length === 1 ? "" : "s"}
              </div>
            </div>
          </div>
          <div className={`px-4 py-1.5 rounded-full font-label-sm text-xs font-bold flex items-center gap-1.5 border ${decisionTone.bg} ${decisionTone.fg} ${decisionTone.border}`}>
            <span className={`w-2 h-2 rounded-full ${decisionTone.dot}`} />
            {decision}
          </div>
        </div>

        {/* ─── 1. Overview: uploaded documents with thumbnails ─── */}
        {stage1Files.length > 0 && (
          <div className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-emerald-100">
            <div className="flex items-center justify-between mb-3">
              <div className="font-label-sm text-xs font-bold text-on-surface flex items-center gap-1.5">
                <ImageIcon className="w-4 h-4 text-primary" />
                Detected document types ({stage1Files.length})
              </div>
              <span className="font-mono text-[10px] text-secondary font-bold">
                {totalFields} fields · {totalErrors} warning{totalErrors === 1 ? "" : "s"}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {stage1Files.map((f) => {
                const doc = stage2Docs.find((d) => d.index === f.index);
                const hasErrors = (doc?.validation?.errors || []).length > 0;
                return (
                  <div key={f.index} className={`rounded-xl border overflow-hidden bg-surface-container-low flex flex-col ${
                    hasErrors ? "border-amber-300" : "border-emerald-200"
                  }`}>
                    <div className="relative">
                      <img
                        src={`/api/v2/documents/preview/${stage1.session_id}/${f.index}`}
                        alt={f.filename}
                        className="w-full h-32 object-cover bg-surface-container-high"
                        onError={(e) => {
                          e.target.src = `/api/v2/documents/preview/${stage1.session_id}/${f.index}?enhanced=false`;
                        }}
                      />
                      <span className={`absolute top-2 right-2 font-mono text-[9px] px-1.5 py-0.5 rounded font-bold ${
                        hasErrors ? "bg-amber-500 text-white" : "bg-emerald-600 text-white"
                      }`}>
                        #{f.index}
                      </span>
                    </div>
                    <div className="p-2.5">
                      <div className="font-label-sm text-sm font-bold text-on-surface truncate">
                        {cap(f.classification?.doc_type || "unknown")}
                      </div>
                      <div className="font-mono text-[10px] text-secondary font-semibold">
                        {typeof f.classification?.confidence === "number"
                          ? `${(f.classification.confidence * 100).toFixed(1)}% match`
                          : "—"}
                      </div>
                      <div className="font-mono text-[9px] text-on-surface-variant truncate mt-0.5">
                        {f.filename}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ─── 2. Per-document OCR fields ─── */}
        {stage2Docs.length > 0 && (
          <div className="space-y-3">
            <div className="font-label-sm text-xs font-bold text-on-surface flex items-center gap-1.5">
              <Fingerprint className="w-4 h-4 text-primary" />
              Extracted fields per document ({stage2Docs.length})
            </div>

            {stage2Docs.map((doc) => {
              const s1f = stage1Files.find((x) => x.index === doc.index);
              const fields = doc.fields || {};
              const fieldEntries = Object.entries(fields);
              const hasErrors = (doc.validation?.errors || []).length > 0;

              return (
                <div key={doc.index} className={`rounded-2xl bg-surface-container-lowest shadow-sm border-2 overflow-hidden ${
                  hasErrors ? "border-amber-300" : "border-emerald-200"
                }`}>
                  <div className="flex gap-3 p-3 bg-surface-container-low/50 border-b border-emerald-100">
                    <img
                      src={`/api/v2/documents/preview/${stage1.session_id}/${doc.index}`}
                      alt={doc.filename}
                      className="w-16 h-20 object-cover rounded-lg border border-emerald-200 shrink-0 bg-surface-container-high"
                      onError={(e) => {
                        e.target.src = `/api/v2/documents/preview/${stage1.session_id}/${doc.index}?enhanced=false`;
                      }}
                    />
                    <div className="min-w-0 flex-1 flex flex-col justify-center">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-[10px] text-on-surface-variant">#{doc.index}</span>
                        <span className="font-label-sm text-base font-bold text-on-surface">
                          {cap(doc.doc_type || s1f?.classification?.doc_type || "unknown")}
                        </span>
                        {s1f?.classification?.confidence != null && (
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
                            {(s1f.classification.confidence * 100).toFixed(1)}%
                          </span>
                        )}
                        {hasErrors ? (
                          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold">
                            {doc.validation.errors.length} warn
                          </span>
                        ) : (
                          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
                            valid
                          </span>
                        )}
                      </div>
                      <div className="font-mono text-[10px] text-on-surface-variant truncate mt-0.5">
                        {doc.filename}
                      </div>
                    </div>
                  </div>

                  <div className="p-3">
                    {fieldEntries.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {fieldEntries.map(([k, v]) => (
                          <div key={k} className="p-2.5 rounded-xl bg-surface-container-low border border-emerald-100">
                            <div className="font-mono text-[9px] text-on-surface-variant uppercase">
                              {k.replace(/_/g, " ")}
                            </div>
                            <div className="font-mono text-sm font-bold text-on-surface mt-0.5 truncate">
                              {String(v)}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-surface-container-low border border-emerald-100 text-center">
                        <FileText className="w-4 h-4 mx-auto text-on-surface-variant/40 mb-1" />
                        <div className="font-mono text-[10px] text-on-surface-variant">
                          {doc.ocr_failed
                            ? "OCR could not parse this document — try a clearer photo"
                            : "No structured fields extracted"}
                        </div>
                      </div>
                    )}

                    {doc.mrz?.raw && (
                      <div className="mt-2 p-2.5 rounded-lg bg-[#11261a] border border-emerald-900/60">
                        <div className="font-mono text-[9px] text-emerald-300 font-bold mb-1">MRZ RAW</div>
                        <div className="font-mono text-[10px] text-emerald-100 break-all leading-relaxed">
                          {Array.isArray(doc.mrz.raw) ? doc.mrz.raw.join("\n") : doc.mrz.raw}
                        </div>
                      </div>
                    )}

                    {hasErrors && (
                      <div className="mt-2 p-2.5 rounded-lg bg-error-container/40 border border-error/30">
                        <div className="font-mono text-[9px] text-error font-bold flex items-center gap-1 mb-1">
                          <AlertTriangle className="w-3 h-3" /> VALIDATION WARNINGS
                        </div>
                        <ul className="font-mono text-[10px] text-on-error-container space-y-0.5">
                          {doc.validation.errors.map((e, j) => <li key={j}>• {e}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ─── 3. Risk pillars ─── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Pillar label="Liveness Score" value={anti.score != null ? `${(anti.score * 100).toFixed(1)}%` : "—"} sub={anti.passed ? "Real person" : "Spoof suspected"} tone={anti.passed ? "ok" : "bad"} />
          <Pillar label="Tamper Score" value={`${worstTamper.toFixed(1)}/100`} sub={worstTamper >= 65 ? "Flagged" : worstTamper >= 30 ? "Moderate" : "Clean fusion"} tone={worstTamper >= 65 ? "bad" : worstTamper >= 30 ? "warn" : "ok"} />
          <Pillar label="Face Match" value={fm.distance != null ? fm.distance.toFixed(3) : "—"} sub={fm.passed ? "Matched" : "Mismatch"} tone={fm.passed ? "ok" : "bad"} />
          <Pillar label="Composite Risk" value={`${score.toFixed(1)}/100`} sub={score > 70 ? "Deny" : score >= 30 ? "Secondary" : "Approve"} tone={score > 70 ? "bad" : score >= 30 ? "warn" : "ok"} />
        </div>

        {/* ─── 4. Tampering breakdown ─── */}
        {tamperList.length > 0 && (
          <div className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-emerald-100">
            <div className="flex items-center justify-between mb-3">
              <div className="font-label-sm text-xs font-bold text-on-surface flex items-center gap-1.5">
                <ImageIcon className="w-4 h-4 text-primary" />
                Tampering breakdown · {tamperList.length} document{tamperList.length === 1 ? "" : "s"}
              </div>
              <span className="font-mono text-[10px] text-secondary font-bold">
                Worst: {worstTamper.toFixed(1)}
              </span>
            </div>
            <div className="space-y-2">
              {tamperList.map((t, i) => (
                <div key={i} className={`p-2.5 rounded-xl border flex items-center justify-between gap-3 ${
                  t.is_tampered ? "bg-error-container/30 border-error/30" : "bg-surface-container-low border-emerald-100"
                }`}>
                  <div className="font-mono text-xs font-bold text-on-surface whitespace-nowrap">
                    Doc #{t.index ?? i}
                  </div>
                  <div className="font-mono text-[10px] text-on-surface-variant flex-1 truncate">
                    {(t.risk_factors || []).join(" · ") || "no flags"}
                  </div>
                  <span className={`font-mono text-[10px] px-2 py-0.5 rounded font-bold ${
                    t.is_tampered ? "bg-error text-on-error" : "bg-emerald-100 text-emerald-800"
                  }`}>
                    {(t.tampering_score || 0).toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ─── 5. Liveness detail ─── */}
        <div className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-emerald-100">
          <div className="font-label-sm text-xs font-bold text-on-surface mb-3 flex items-center gap-1.5">
            <ScanFace className="w-4 h-4 text-primary" /> Liveness &amp; biometrics
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <KV label="Blink challenge" value={`${live.blink_count ?? 0} / ${live.blink_target ?? 0}`} pass={live.blink_count >= live.blink_target} />
            <KV label="Anti-spoof score" value={anti.score != null ? anti.score.toFixed(3) : "—"} pass={anti.passed} />
            <KV label="Face match distance" value={fm.distance != null ? fm.distance.toFixed(3) : "—"} pass={fm.passed} />
          </div>
        </div>

        {/* ─── 6. Blockchain ─── */}
        <div className="rounded-2xl bg-[#11261a] text-secondary-fixed p-4 shadow-md border border-emerald-900/60 font-mono text-[10px]">
          <div className="flex items-center justify-between pb-2 border-b border-emerald-800/60 mb-2">
            <span className="flex items-center gap-1.5 text-emerald-200 font-bold">
              <Lock className="w-4 h-4 text-emerald-400" /> Hyperledger Fabric Ledger
            </span>
            <span className={`font-bold px-2.5 py-0.5 rounded border ${
              blockchain.recorded
                ? "text-emerald-300 bg-emerald-950/80 border-emerald-500/30"
                : "text-amber-300 bg-amber-950/60 border-amber-500/30"
            }`}>
              {blockchain.recorded ? "RECORDED" : "OFFLINE"}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-emerald-100/80">
            <div>Channel: <span className="text-emerald-200 font-bold">screening-channel</span></div>
            <div>Screening ID: <span className="text-emerald-200 font-bold">{blockchain.screening_id || "—"}</span></div>
          </div>
        </div>

        {/* ─── 7. Verdict + actions ─── */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="font-mono text-xs text-on-surface-variant">
            {risk.reasons?.length
              ? <>Verdict: <strong className="text-on-surface">{risk.reasons.join(" · ")}</strong></>
              : "All checks passed."}
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button onClick={onBack} className="px-4 py-2 rounded-full bg-surface-container-high text-on-surface font-label-sm text-xs font-bold hover:bg-surface-container transition-all flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
            <button onClick={onRestart} className="px-4 py-2 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-sm text-xs font-bold transition-all flex items-center gap-1 shadow-md">
              <RotateCcw className="w-4 h-4" /> New screening
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Pillar({ label, value, sub, tone }) {
  const toneCls = tone === "ok" ? "text-secondary" : tone === "warn" ? "text-amber-600" : tone === "bad" ? "text-error" : "text-on-surface";
  const subCls = tone === "ok" ? "text-secondary" : tone === "warn" ? "text-amber-600" : tone === "bad" ? "text-error" : "text-on-surface-variant";
  return (
    <div className="rounded-2xl bg-surface-container-lowest p-4 shadow-sm border border-emerald-100">
      <div className="font-label-sm text-[10px] text-on-surface-variant uppercase font-bold tracking-wide">{label}</div>
      <div className={`font-headline-sm text-2xl font-mono font-bold mt-1 ${toneCls}`}>{value}</div>
      <div className={`font-mono text-[9px] font-semibold mt-0.5 ${subCls}`}>{sub}</div>
    </div>
  );
}

function KV({ label, value, pass }) {
  return (
    <div className="p-2.5 rounded-xl bg-surface-container-low border border-emerald-100">
      <div className="font-mono text-[9px] text-on-surface-variant">{label}</div>
      <div className="flex items-center justify-between mt-0.5">
        <span className="font-mono text-xs font-bold text-on-surface">{value}</span>
        {pass ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
               : <XCircle className="w-3.5 h-3.5 text-error" />}
      </div>
    </div>
  );
}

const cap = (s) => s ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : s;