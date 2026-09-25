/* Liveness challenge widget. */
(function () {
  const mount = document.getElementById("livenessWidgetRoot");
  if (!mount || !window.React || !window.ReactDOM) return;

  const { createElement: h, useEffect, useRef, useState, useCallback } = window.React;
  const root = window.ReactDOM.createRoot(mount);

  const API = "http://localhost:8000";
  const FRAME_INTERVAL_MS = 80;
  const STATUS_POLL_MS = 1000;
  const EAR_CLOSED = 0.15;

  const fetchTimeout = (url, opts = {}, ms = 60000) => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    return fetch(url, { ...opts, signal: ctrl.signal })
      .finally(() => clearTimeout(timer));
  };

  function ChecklistRow({ label, pendingLabel, result, passed }) {
    return h("li", { className: "lw-check-row" + (passed ? " lw-check-done" : "") }, [
      h("span", { key: "i", className: "lw-check-icon" },
        passed ? h("i", { className: "fas fa-circle-check" })
               : h("i", { className: "far fa-circle" })),
      h("span", { key: "l", className: "lw-check-label" }, label),
      h("span", { key: "v", className: "lw-check-value" },
        passed ? result : pendingLabel),
    ]);
  }

  function LivenessWidget() {
    const [phase, setPhase] = useState("idle");
    const [state, setState] = useState("created");
    const [blinkTarget, setBlinkTarget] = useState(3);
    const [blinkCount, setBlinkCount] = useState(0);
    const [ear, setEar] = useState(0);
    const [faceAligned, setFaceAligned] = useState(false);
    const [timeRemaining, setTimeRemaining] = useState(0);
    const [checklist, setChecklist] = useState({
      blink: { passed: false, value: "0 of 3" },
      antiSpoof: { passed: false, value: "sampling" },
      faceMatch: { passed: false, value: "waiting" },
    });
    const [canVerify, setCanVerify] = useState(false);
    const [error, setError] = useState("");

    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const frameTimerRef = useRef(null);
    const pollTimerRef = useRef(null);
    const sessionIdRef = useRef(null);
    const blinkCountRef = useRef(0);
    const blinkTargetRef = useRef(3);
    const bestFrameRef = useRef(null);
    const busyRef = useRef(false);
    const finishingRef = useRef(false);

    const releaseStream = useCallback(() => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (videoRef.current) videoRef.current.srcObject = null;
      if (frameTimerRef.current) clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }, []);

    const stopPolling = useCallback(() => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }, []);

    const emitVerified = useCallback((unverified = false, reason = "") => {
      releaseStream();
      stopPolling();
      setPhase("verified");
      window.dispatchEvent(new CustomEvent("liveness-verified", {
        detail: {
          verificationId: null,
          livenessSessionId: sessionIdRef.current,   // ← ADD
          unverified,
          reason,
          livePhoto: bestFrameRef.current,
        },
      }));
    }, [releaseStream, stopPolling]);

    useEffect(() => () => { releaseStream(); stopPolling(); }, [releaseStream, stopPolling]);

    const refreshStatus = useCallback(async () => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      try {
        const res = await fetchTimeout(`${API}/liveness/session/${sid}/status`, {}, 5000);
        if (!res.ok) return;
        const data = await res.json();
        setState(data.state);
        setChecklist({
          blink: data.blink_challenge || { passed: false, value: "0 of 0" },
          antiSpoof: data.anti_spoof || { passed: false, value: "sampling" },
          faceMatch: data.face_match || { passed: false, value: "waiting" },
        });
        setCanVerify(!!data.can_verify);
        if (data.state === "failed") {
          setPhase("failed");
          setError(data.failure_reason || "Liveness challenge failed.");
          stopPolling();
        }
      } catch { /* transient */ }
    }, [stopPolling]);

    const startCamera = useCallback(async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        return true;
      } catch {
        setError("Camera permission denied or no camera found.");
        setPhase("failed");
        return false;
      }
    }, []);

    const finishBlinkChallenge = useCallback(async () => {
      if (finishingRef.current) return;
      finishingRef.current = true;

      setPhase("finishing");
      const sid = sessionIdRef.current;
      if (!sid) return;

      try {
        const res = await fetchTimeout(
          `${API}/liveness/session/${sid}/complete-blink-challenge`,
          { method: "POST" },
          30000
        );
        if (!res.ok) throw new Error(`complete-blink failed (${res.status})`);
        const data = await res.json();
        setChecklist((c) => ({
          ...c,
          blink: {
            passed: !!data.blink_challenge?.passed,
            value: data.blink_challenge?.result || `${blinkCountRef.current} of ${blinkTargetRef.current}`,
          },
        }));

        try {
          await fetchTimeout(`${API}/liveness/session/${sid}/anti-spoof`, { method: "POST" }, 30000);
        } catch { /* logged server-side */ }

        try {
          await fetchTimeout(`${API}/liveness/session/${sid}/face-match`, { method: "POST" }, 60000);
        } catch { /* logged server-side */ }

        await refreshStatus();
        // No auto-continue. If face-match failed, the user must click
        // Retry or Continue to screening explicitly.
      } catch (e) {
        setError(e.message || "Could not complete blink challenge.");
        setPhase("failed");
      }
    }, [refreshStatus]);

    const retryFaceMatch = useCallback(async () => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      try {
        await fetchTimeout(`${API}/liveness/session/${sid}/retry-face-match`, { method: "POST" }, 10000);
        await fetchTimeout(`${API}/liveness/session/${sid}/face-match`, { method: "POST" }, 60000);
        await refreshStatus();
      } catch { /* logged server-side */ }
    }, [refreshStatus]);

    const startFrameLoop = useCallback(() => {
      if (frameTimerRef.current) clearInterval(frameTimerRef.current);
      frameTimerRef.current = setInterval(async () => {
        if (busyRef.current || finishingRef.current) return;
        const video = videoRef.current, canvas = canvasRef.current;
        const sid = sessionIdRef.current;
        if (!video || !canvas || !sid) return;
        if (video.readyState < 2 || !video.videoWidth) return;

        busyRef.current = true;
        try {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // 2.5× brightness boost — critical for InsightFace in dim rooms
          const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const px = imgData.data;
          for (let i = 0; i < px.length; i += 4) {
            px[i]     = Math.min(255, px[i]     * 2.5);
            px[i + 1] = Math.min(255, px[i + 1] * 2.5);
            px[i + 2] = Math.min(255, px[i + 2] * 2.5);
          }
          ctx.putImageData(imgData, 0, 0);

          const blob = await new Promise((resolve) =>
            canvas.toBlob(resolve, "image/jpeg", 0.85)
          );
          if (!blob) return;
          bestFrameRef.current = blob;

          const fd = new FormData();
          fd.append("frame", blob, "frame.jpg");
          const res = await fetchTimeout(`${API}/liveness/session/${sid}/frame`, {
            method: "POST",
            body: fd,
          }, 10000);
          if (!res.ok) return;
          const data = await res.json();

          setBlinkCount(data.blink_count);
          blinkCountRef.current = data.blink_count;
          setEar(data.ear);
          setFaceAligned(!!data.face_aligned);
          setTimeRemaining(data.time_remaining);
          setState(data.status);

          if (data.status === "failed") {
            setPhase("failed");
            setError("Liveness challenge failed (timeout).");
            releaseStream();
            stopPolling();
            return;
          }

          if (data.blink_count >= blinkTargetRef.current) {
            finishBlinkChallenge();
          }
        } catch { /* keep looping */ }
        finally { busyRef.current = false; }
      }, FRAME_INTERVAL_MS);
    }, [finishBlinkChallenge, releaseStream, stopPolling]);

    const startPolling = useCallback(() => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(refreshStatus, STATUS_POLL_MS);
    }, [refreshStatus]);

    const startSession = useCallback(async () => {
      const docFile = window._docFile;
      if (!docFile) { setError("Upload a document first."); return; }

      setError("");
      setPhase("starting");
      finishingRef.current = false;

      try {
        const fd = new FormData();
        fd.append("document_photo", docFile, docFile.name || "document.jpg");
        const res = await fetchTimeout(`${API}/liveness/session`, { method: "POST", body: fd }, 30000);
        if (!res.ok) throw new Error(`session create failed (${res.status})`);
        const data = await res.json();

        sessionIdRef.current = data.session_id;
        blinkTargetRef.current = data.blink_target;
        blinkCountRef.current = 0;
        bestFrameRef.current = null;

        setBlinkTarget(data.blink_target);
        setBlinkCount(0);
        setChecklist({
          blink: { passed: false, value: `0 of ${data.blink_target}` },
          antiSpoof: { passed: false, value: "sampling" },
          faceMatch: { passed: false, value: "waiting" },
        });
        setCanVerify(false);

        const ok = await startCamera();
        if (!ok) return;

        setPhase("running");
        startFrameLoop();
        startPolling();
      } catch (e) {
        setPhase("failed");
        setError(e.message || "Could not start liveness session.");
      }
    }, [startCamera, startFrameLoop, startPolling]);

    const verify = useCallback(async () => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      try {
        const res = await fetchTimeout(`${API}/liveness/session/${sid}/verify`, { method: "POST" }, 20000);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `verify failed (${res.status})`);
        }
        const data = await res.json();
        releaseStream();
        stopPolling();
        setPhase("verified");
        window.dispatchEvent(new CustomEvent("liveness-verified", {
          detail: {
            verificationId: data.verification_id,
            livenessSessionId: sid,                   // ← ADD
            unverified: false,
            livePhoto: bestFrameRef.current,
          },
        }));
      } catch (e) {
        setError(e.message || "Verification failed.");
        setPhase("failed");
      }
    }, [releaseStream, stopPolling]);

    const reset = useCallback(() => {
      releaseStream();
      stopPolling();
      sessionIdRef.current = null;
      bestFrameRef.current = null;
      blinkCountRef.current = 0;
      finishingRef.current = false;
      setPhase("idle");
      setState("created");
      setBlinkCount(0);
      setEar(0);
      setFaceAligned(false);
      setTimeRemaining(0);
      setCanVerify(false);
      setError("");
      setChecklist({
        blink: { passed: false, value: `0 of ${blinkTargetRef.current}` },
        antiSpoof: { passed: false, value: "sampling" },
        faceMatch: { passed: false, value: "waiting" },
      });
    }, [releaseStream, stopPolling]);

    const running = phase === "running" || phase === "finishing";

    const blinkAntiPassed = checklist.blink.passed && checklist.antiSpoof.passed;
    const faceMatchFailed = blinkAntiPassed && !checklist.faceMatch.passed;
    const showRetryMatch = running && !canVerify && faceMatchFailed;

    const statusLine =
      phase === "idle"       ? "Upload a document, then start the liveness check." :
      phase === "starting"   ? "Starting secure session…" :
      phase === "finishing"  ? (canVerify
                                  ? "All checks passed — click Verify traveller."
                                  : faceMatchFailed
                                    ? "Face match failed — retry or continue to screening."
                                    : "Running presentation-attack and face-match checks…") :
      phase === "verified"   ? "Ready for screening" :
      phase === "failed"     ? (error || "Liveness failed") :
      !faceAligned           ? "Look at the camera and fill the oval with your face" :
                               `Blink ${blinkTarget} times — done ${blinkCount}`;

    const eyeMarker = ear < EAR_CLOSED ? "●" : "○";

    return h("div", { className: "lw-root" }, [
      h("div", { key: "head", className: "lw-head" }, [
        h("h4", { key: "t" }, [
          h("i", { key: "i", className: "fas fa-user-shield" }),
          " Liveness Check",
        ]),
        h("p", { key: "s", className: "lw-sub" },
          "Blink challenge + presentation-attack check, scored server-side."),
      ]),

      h("div", { key: "video", className: "lw-video-wrap" }, [
        h("span", { key: "c1", className: "lw-corner lw-corner-tl" }),
        h("span", { key: "c2", className: "lw-corner lw-corner-tr" }),
        h("span", { key: "c3", className: "lw-corner lw-corner-bl" }),
        h("span", { key: "c4", className: "lw-corner lw-corner-br" }),
        h("div",  { key: "ov", className: "lw-oval" }),
        h("video", {
          key: "v", ref: videoRef, autoPlay: true, playsInline: true,
          muted: true, className: "lw-video",
        }),
        h("canvas", { key: "cv", ref: canvasRef, style: { display: "none" } }),
        running && h("div", { key: "o", className: "lw-overlay" }, [
          h("div", { key: "l1", className: "lw-overlay-line lw-overlay-green" },
            `BLINK ${blinkTarget} TIMES — done ${blinkCount} — ${timeRemaining}s`),
          h("div", { key: "l2", className: "lw-overlay-line lw-overlay-cyan" },
            `ear ${ear.toFixed(3)} ${eyeMarker}`),
        ]),
      ]),

      h("div", { key: "status", className: "lw-status" }, [
        h("span", { key: "d", className: `lw-dot lw-dot-${phase}` }),
        h("span", { key: "t" }, statusLine),
      ]),

      h("ol", { key: "steps", className: "lw-steps" }, [
        h("li", { key: "s1" }, "Sit square to the camera and fill the oval with your face"),
        h("li", { key: "s2" }, "Blink when the prompt asks, twice or three times"),
        h("li", { key: "s3" }, "Hold still while the photo is compared to the document"),
      ]),

      h("ul", { key: "checklist", className: "lw-checklist" }, [
        h(ChecklistRow, {
          key: "blink", label: "Blink challenge", pendingLabel: "watching",
          result: checklist.blink.value, passed: checklist.blink.passed,
        }),
        h(ChecklistRow, {
          key: "anti", label: "Presentation-attack model", pendingLabel: "sampling",
          result: checklist.antiSpoof.value, passed: checklist.antiSpoof.passed,
        }),
        h(ChecklistRow, {
          key: "match", label: "Face matched to document photo", pendingLabel: "waiting",
          result: checklist.faceMatch.value, passed: checklist.faceMatch.passed,
        }),
      ]),

      h("div", { key: "actions", className: "lw-actions" }, [
        phase === "idle" && h("button", {
          key: "start", type: "button", className: "btn btn-primary lw-btn",
          onClick: startSession,
        }, "Start Liveness Check"),

        phase === "failed" && h("button", {
          key: "retry", type: "button", className: "btn btn-outline-light lw-btn",
          onClick: reset,
        }, "Retry"),

        showRetryMatch && h("button", {
          key: "retry-match", type: "button", className: "btn btn-outline-light lw-btn",
          onClick: retryFaceMatch,
        }, "Retry face match"),

        showRetryMatch && h("button", {
          key: "continue-unverified", type: "button", className: "btn btn-primary lw-btn",
          onClick: () => emitVerified(true, "face_match_failed"),
        }, "Continue to screening"),

        running && canVerify && h("button", {
          key: "verify", type: "button", className: "btn btn-primary lw-btn",
          onClick: verify,
        }, "Verify traveller"),

        phase === "verified" && h("div", { key: "done", className: "lw-verified" }, [
          h("i", { key: "i", className: "fas fa-circle-check" }),
          h("span", { key: "t" }, " Ready for screening"),
        ]),
      ]),

      (error && phase !== "verified")
        ? h("p", { key: "err", className: "lw-error" }, error)
        : null,
    ]);
  }

  root.render(h(LivenessWidget));
})();