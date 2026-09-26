// Relative paths → Vite dev proxy forwards to :8000. In prod, serve behind same host.
const BASE = "";

async function jfetch(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = j.detail || j.message || detail; } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  health: () => jfetch("/health"),

  // ─── Stage 1: validate documents ───
  validateDocuments: (files) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    return jfetch("/api/v2/documents/validate", { method: "POST", body: fd });
  },

  // ─── Stage 2: OCR + validation ───
  getDetails: (sessionId) =>
    jfetch("/api/v2/documents/details", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }),

  // ─── Stage 3: liveness session orchestration ───
  startLiveness: (sessionId) =>
    jfetch("/api/v2/screening/start-liveness", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }),

  pushFrame: (livenessSessionId, blob) => {
    const fd = new FormData();
    fd.append("frame", blob, "frame.jpg");
    return jfetch(`/liveness/session/${livenessSessionId}/frame`, {
      method: "POST",
      body: fd,
    });
  },

  completeBlink: (sid) =>
    jfetch(`/liveness/session/${sid}/complete-blink-challenge`, { method: "POST" }),

  antiSpoof: (sid) =>
    jfetch(`/liveness/session/${sid}/anti-spoof`, { method: "POST" }),

  faceMatch: (sid) =>
    jfetch(`/liveness/session/${sid}/face-match`, { method: "POST" }),

  livenessStatus: (sid) => jfetch(`/liveness/session/${sid}/status`),

  verifyLiveness: (sid) =>
    jfetch(`/liveness/session/${sid}/verify`, { method: "POST" }),

  // ─── Finalize: tampering + risk + blockchain ───
  finalize: (screeningSessionId, livenessSessionId) =>
    jfetch("/api/v2/screening/finalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        screening_session_id: screeningSessionId,
        liveness_session_id: livenessSessionId,
      }),
    }),

  // ─── Fetch the full state of a screening session ───
  // Used by Step3Results to recover when a session is already at stage 'final'
  // (React StrictMode double-invoke, browser refresh, or back-navigation).
  getScreeningState: (screeningSessionId) =>
    jfetch(`/api/v2/screening/${screeningSessionId}/state`),
};