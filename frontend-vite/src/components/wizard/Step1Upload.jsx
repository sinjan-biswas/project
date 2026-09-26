import { useCallback, useRef, useState } from "react";
import {
  CloudUpload, X, CheckCircle2, AlertCircle, Loader2, ArrowRight,
  ShieldCheck, Wand2, FileSearch, Image as ImageIcon, Fingerprint,
  FileText, AlertTriangle,
} from "lucide-react";
import { api } from "../../api/client";

const MAX_FILES = 10;
const MAX_MB = 15;
const ALLOWED = ["image/jpeg", "image/png", "image/webp"];

export default function Step1Upload({ onComplete }) {
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [phase, setPhase] = useState("idle"); // idle | validating | fetching | done | error
  const [error, setError] = useState(null);
  const [stage1, setStage1] = useState(null);
  const [stage2, setStage2] = useState(null);
  const inputRef = useRef(null);

  const addFiles = useCallback((incoming) => {
    const arr = Array.from(incoming || []);
    if (!arr.length) return;
    const errs = [];
    setFiles((prev) => {
      const next = [...prev];
      for (const f of arr) {
        if (next.length >= MAX_FILES) { errs.push(`Max ${MAX_FILES} files`); break; }
        if (!ALLOWED.includes(f.type)) { errs.push(`Skipped ${f.name}: unsupported type`); continue; }
        if (f.size > MAX_MB * 1024 * 1024) { errs.push(`Skipped ${f.name}: exceeds ${MAX_MB}MB`); continue; }
        const dupe = next.some((x) => x.file.name === f.name && x.file.size === f.size);
        if (dupe) { errs.push(`Skipped duplicate: ${f.name}`); continue; }
        next.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          file: f,
          previewUrl: URL.createObjectURL(f),
        });
      }
      return next;
    });
    setTimeout(() => setError(errs.length ? errs.join(" · ") : null), 0);
  }, []);

  const removeFile = (id) => {
    setFiles((prev) => {
      const hit = prev.find((f) => f.id === id);
      if (hit) URL.revokeObjectURL(hit.previewUrl);
      return prev.filter((f) => f.id !== id);
    });
  };

  const clearAll = () => {
    files.forEach((f) => URL.revokeObjectURL(f.previewUrl));
    setFiles([]); setStage1(null); setStage2(null); setError(null); setPhase("idle");
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer?.files || []);
    if (dropped.length) addFiles(dropped);
  };

  const submit = async () => {
    if (!files.length) return;
    setPhase("validating");
    setError(null);
    setStage1(null);
    setStage2(null);

    try {
      const validResp = await api.validateDocuments(files.map((f) => f.file));
      setStage1(validResp);

      if (validResp.blocked) {
        setPhase("error");
        setError("Some files need attention. Remove the blocked files or re-upload.");
        return;
      }

      setPhase("fetching");
      const details = await api.getDetails(validResp.session_id);
      setStage2(details);
      setPhase("done");
      // ← NO auto-advance. User reviews OCR results, then clicks Continue.
    } catch (e) {
      setPhase("error");
      setError(e.message || "Validation failed");
    }
  };

  const proceed = () => {
    if (stage1 && stage2) {
      onComplete(stage1, stage2, stage1.session_id);
    }
  };

  const busy = phase === "validating" || phase === "fetching";

  return (
    <div className="rounded-2xl bg-surface-container-low p-6 md:p-8 shadow-sm border border-emerald-200">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* ─── LEFT: dropzone + queue ─── */}
        <div className="lg:col-span-5 flex flex-col">
          <div className="flex items-center justify-between mb-1">
            <div className="font-label-lg font-bold text-on-surface">
              Autonomous Multi-Document Batch Dropzone
            </div>
            <span className="px-2 py-0.5 rounded-full bg-surface-container text-primary font-mono text-[9px] font-bold border border-emerald-300 whitespace-nowrap">
              AI AUTO-CLASSIFIER
            </span>
          </div>
          <p className="font-body-sm text-xs text-on-surface-variant mb-4">
            EfficientNet-B0 + PaddleOCR identifies document typology, nation,
            and tampering cues. <b>Select or drag multiple files at once.</b>
          </p>

          <div
            onClick={() => !busy && inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`rounded-2xl bg-surface-container-lowest p-6 border-2 border-dashed text-center cursor-pointer transition-colors shadow-sm group ${
              dragOver ? "border-primary bg-secondary-container/30" : "border-primary/40 hover:bg-surface-container-low"
            } ${busy ? "opacity-60 pointer-events-none" : ""}`}
          >
            <input
              ref={inputRef}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              hidden
              onChange={(e) => {
                const picked = Array.from(e.target.files || []);
                addFiles(picked);
                e.target.value = "";
              }}
            />
            <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-primary to-[#2a593e] text-on-primary mx-auto flex items-center justify-center mb-2 shadow-md group-hover:scale-110 transition-transform">
              <CloudUpload className="w-6 h-6" />
            </div>
            <div className="font-label-sm text-sm font-bold text-on-surface">
              Drop batch files or tap to browse
            </div>
            <div className="font-mono text-[10px] text-on-surface-variant mt-1">
              Up to {MAX_FILES} files, {MAX_MB}MB each · multi-select enabled
            </div>
          </div>

          {files.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-[11px] font-mono mb-2">
                <span className="text-on-surface-variant font-bold">
                  INGESTION QUEUE ({files.length} LOADED)
                </span>
                <button
                  type="button"
                  onClick={clearAll}
                  disabled={busy}
                  className="text-error hover:underline disabled:opacity-40"
                >
                  Clear all
                </button>
              </div>
              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {files.map((f) => (
                  <div key={f.id} className="p-2.5 rounded-xl bg-surface-container-lowest border border-outline-variant/30 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <img src={f.previewUrl} alt="" className="w-8 h-8 rounded-lg object-cover border border-emerald-200 shrink-0" />
                      <div className="min-w-0">
                        <div className="font-label-sm text-xs font-bold text-on-surface truncate">
                          {f.file.name}
                        </div>
                        <div className="font-mono text-[9px] text-on-surface-variant">
                          {(f.file.size / 1024).toFixed(0)} KB
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(f.id)}
                      disabled={busy}
                      className="text-on-surface-variant hover:text-error disabled:opacity-40 shrink-0"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="mt-3 p-2.5 rounded-xl bg-error-container/50 border border-error/30 text-on-error-container font-mono text-[11px] flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* ─── RIGHT: pipeline status + OCR results ─── */}
        <div className="lg:col-span-7 rounded-2xl bg-surface-container p-6 border border-emerald-200 flex flex-col shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-emerald-200/60 mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-primary" />
              <span className="font-headline-sm text-base font-bold text-on-surface">
                Pre-validation pipeline
              </span>
            </div>
            <PhasePill phase={phase} />
          </div>

          <div className="grid grid-cols-3 gap-2 mb-4">
            <MiniStage icon={Wand2} label="Quality + Enhance"
              active={phase !== "idle" && phase !== "error"} done={!!stage1} />
            <MiniStage icon={ShieldCheck} label="Classification"
              active={phase === "validating" || phase === "fetching"}
              done={!!stage1 && !stage1.blocked} />
            <MiniStage icon={FileSearch} label="OCR + Validation"
              active={phase === "fetching"} done={phase === "done"} />
          </div>

          {/* ─── OCR results ─── */}
          <div className="flex-1 overflow-y-auto pr-1 max-h-[500px]">
            {stage1 && stage2 ? (
              <OcrResults stage1={stage1} stage2={stage2} />
            ) : stage1 ? (
              <ClassificationOnly stage1={stage1} />
            ) : (
              <div className="p-6 text-center">
                <ImageIcon className="w-8 h-8 mx-auto text-on-surface-variant/40 mb-2" />
                <p className="font-body-sm text-xs text-on-surface-variant">
                  Add one or more document images, then click{" "}
                  <b>Validate &amp; Read</b>. We'll run quality, enhancement,
                  classification, OCR, and field validation in one pass.
                </p>
              </div>
            )}
          </div>

          {/* ─── Footer CTA ─── */}
          <div className="mt-4 pt-4 border-t border-emerald-200/50 flex items-center justify-between gap-3">
            <span className="font-mono text-[11px] text-on-surface-variant">
              {files.length > 0
                ? `${files.length} file${files.length === 1 ? "" : "s"} ready`
                : "Waiting for files"}
            </span>

            {phase === "done" && stage1 && stage2 ? (
              <button
                type="button"
                onClick={proceed}
                className="px-6 py-2.5 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-lg text-xs font-bold shadow-md hover:-translate-y-0.5 transition-all flex items-center gap-2"
              >
                Continue to Liveness <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                disabled={!files.length || busy}
                onClick={submit}
                className="px-6 py-2.5 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-lg text-xs font-bold shadow-md hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0 flex items-center gap-2"
              >
                {busy ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {phase === "validating" ? "Validating…" : "Reading OCR…"}
                  </>
                ) : (
                  <>
                    Validate &amp; Read <span className="font-mono">→</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────── */

function ClassificationOnly({ stage1 }) {
  return (
    <div>
      <div className="font-mono text-[10px] text-on-surface-variant font-bold mb-2 flex items-center gap-1.5">
        <ImageIcon className="w-3.5 h-3.5" />
        DETECTED DOCUMENTS ({stage1.files.length}) — reading OCR…
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {stage1.files.map((f) => (
          <FileCard key={f.index} f={f} sessionId={stage1.session_id} />
        ))}
      </div>
    </div>
  );
}

function OcrResults({ stage1, stage2 }) {
  const docs = stage2.documents || [];
  const totalFields = docs.reduce((a, d) => a + Object.keys(d.fields || {}).length, 0);
  const totalErrors = docs.reduce((a, d) => a + (d.validation?.errors?.length || 0), 0);

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span className="font-label-sm text-xs font-bold text-emerald-800">
            OCR complete · {docs.length} document{docs.length === 1 ? "" : "s"} · {totalFields} fields extracted
          </span>
        </div>
        {totalErrors > 0 && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold">
            {totalErrors} warning{totalErrors === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {/* Per-document card: thumbnail + classification + fields */}
      {docs.map((d, i) => {
        const s1f = stage1.files.find((x) => x.index === d.index);
        const hasErrors = (d.validation?.errors || []).length > 0;
        const fields = d.fields || {};
        const fieldEntries = Object.entries(fields);

        return (
          <div
            key={i}
            className={`rounded-xl border bg-surface-container-lowest overflow-hidden ${
              hasErrors ? "border-amber-300" : "border-emerald-200"
            }`}
          >
            {/* Header: thumbnail + class */}
            <div className="flex gap-3 p-3 bg-surface-container-low/40">
              <img
                src={`/api/v2/documents/preview/${stage1.session_id}/${d.index}`}
                alt={d.filename}
                className="w-20 h-24 object-cover rounded-lg border border-emerald-200 shrink-0 bg-surface-container-high"
                onError={(e) => {
                  e.target.src = `/api/v2/documents/preview/${stage1.session_id}/${d.index}?enhanced=false`;
                }}
              />
              <div className="min-w-0 flex-1">
                <div className="font-mono text-[10px] text-on-surface-variant truncate">
                  #{d.index} · {d.filename}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="font-label-sm text-base font-bold text-on-surface">
                    {cap(d.doc_type || s1f?.classification?.doc_type || "unknown")}
                  </span>
                  {s1f?.classification?.confidence != null && (
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
                      {(s1f.classification.confidence * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                  {s1f?.quality?.decision && (
                    <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-bold">
                      {s1f.quality.decision}
                    </span>
                  )}
                  {s1f?.enhanced && (
                    <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-secondary-container text-primary font-bold">
                      enhanced
                    </span>
                  )}
                  <span className={`font-mono text-[9px] px-1.5 py-0.5 rounded font-bold ${
                    hasErrors ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
                  }`}>
                    {hasErrors ? `${d.validation.errors.length} warn` : "VALID"}
                  </span>
                </div>
              </div>
            </div>

            {/* Fields */}
            <div className="p-3 border-t border-emerald-100">
              {fieldEntries.length > 0 ? (
                <>
                  <div className="font-mono text-[9px] text-on-surface-variant font-bold mb-2 flex items-center gap-1.5">
                    <Fingerprint className="w-3 h-3" />
                    EXTRACTED FIELDS ({fieldEntries.length})
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {fieldEntries.map(([k, v]) => (
                      <div key={k} className="p-2 rounded-lg bg-surface-container-low border border-emerald-100">
                        <div className="font-mono text-[9px] text-on-surface-variant uppercase truncate">
                          {k.replace(/_/g, " ")}
                        </div>
                        <div className="font-mono text-[11px] font-bold text-on-surface mt-0.5 truncate">
                          {String(v)}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="p-2 rounded-lg bg-surface-container-low border border-emerald-100 text-center">
                  <FileText className="w-4 h-4 mx-auto text-on-surface-variant/40 mb-1" />
                  <div className="font-mono text-[10px] text-on-surface-variant">
                    No fields extracted — image may be low quality or unsupported layout
                  </div>
                </div>
              )}

              {/* MRZ raw if present */}
              {d.mrz?.raw && (
                <div className="mt-2 p-2 rounded-lg bg-[#11261a] border border-emerald-900/60">
                  <div className="font-mono text-[9px] text-emerald-300 font-bold mb-1">MRZ RAW</div>
                  <div className="font-mono text-[9px] text-emerald-100 break-all leading-relaxed">
                    {Array.isArray(d.mrz.raw) ? d.mrz.raw.join("\n") : d.mrz.raw}
                  </div>
                </div>
              )}

              {/* Validation errors */}
              {hasErrors && (
                <div className="mt-2 p-2 rounded-lg bg-error-container/40 border border-error/30">
                  <div className="font-mono text-[9px] text-error font-bold flex items-center gap-1 mb-1">
                    <AlertTriangle className="w-3 h-3" /> VALIDATION WARNINGS
                  </div>
                  <ul className="font-mono text-[10px] text-on-error-container space-y-0.5">
                    {d.validation.errors.map((e, j) => <li key={j}>• {e}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FileCard({ f, sessionId }) {
  return (
    <div className={`rounded-xl overflow-hidden border flex flex-col ${
      f.blocked ? "border-error/40 bg-error-container/30" : "border-emerald-100 bg-surface-container-lowest"
    }`}>
      <div className="flex gap-2 p-2">
        <img
          src={`/api/v2/documents/preview/${sessionId}/${f.index}`}
          alt={f.filename}
          className="w-16 h-20 object-cover rounded-lg border border-emerald-200 shrink-0 bg-surface-container-high"
        />
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[10px] text-on-surface-variant truncate">
            #{f.index} · {f.filename}
          </div>
          <div className="font-label-sm text-sm font-bold text-on-surface mt-0.5 truncate">
            {f.classification?.doc_type || "unknown"}
          </div>
          <div className="font-mono text-[10px] text-secondary font-semibold">
            {typeof f.classification?.confidence === "number"
              ? `${(f.classification.confidence * 100).toFixed(1)}% match`
              : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

function PhasePill({ phase }) {
  const map = {
    idle: ["WAITING", "bg-surface-container-high text-on-surface-variant"],
    validating: ["VALIDATING", "bg-secondary-container text-primary"],
    fetching: ["READING OCR", "bg-secondary-container text-primary"],
    done: ["REVIEW", "bg-emerald-100 text-emerald-800"],
    error: ["NEEDS FIX", "bg-error text-on-error"],
  };
  const [label, cls] = map[phase] || map.idle;
  return (
    <span className={`font-mono text-[10px] font-bold px-2.5 py-1 rounded-full ${cls}`}>
      {label}
    </span>
  );
}

function MiniStage({ icon: Icon, label, active, done }) {
  return (
    <div className={`p-2 rounded-xl border text-center transition-all ${
      done ? "bg-emerald-50 border-emerald-200"
      : active ? "bg-secondary-container/60 border-primary"
      : "bg-surface-container-lowest border-outline-variant/30"
    }`}>
      <div className="flex items-center justify-center mb-1">
        {done ? <CheckCircle2 className="w-4 h-4 text-emerald-600" />
         : active ? <Loader2 className="w-4 h-4 text-primary animate-spin" />
         : <Icon className="w-4 h-4 text-on-surface-variant" />}
      </div>
      <div className="font-mono text-[9px] font-bold text-on-surface-variant leading-tight">
        {label}
      </div>
    </div>
  );
}

const cap = (s) => s ? String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : s;