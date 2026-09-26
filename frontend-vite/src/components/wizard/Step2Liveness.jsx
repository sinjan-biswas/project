import { useCallback, useEffect, useRef, useState } from "react";
import {
  Camera, Loader2, CheckCircle2, AlertCircle, Eye, ShieldCheck,
  ArrowLeft, Play, ArrowRight, Sparkles,
} from "lucide-react";
import { api } from "../../api/client";

const FRAME_INTERVAL_MS = 100;

export default function Step2Liveness({ screeningSessionId, stage1, onComplete, onBack }) {
  const [phase, setPhase] = useState("idle"); // idle|starting|running|finishing|done|error
  const [blinkCount, setBlinkCount] = useState(0);
  const [blinkTarget, setBlinkTarget] = useState(3);
  const [ear, setEar] = useState(0);
  const [faceAligned, setFaceAligned] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [checklist, setChecklist] = useState({
    blink: { passed: false, value: "waiting" },
    antiSpoof: { passed: false, value: "sampling" },
    faceMatch: { passed: false, value: "waiting" },
  });
  const [error, setError] = useState(null);
  const [liveSid, setLiveSid] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const frameTimerRef = useRef(null);
  const pollTimerRef = useRef(null);
  const busyRef = useRef(false);
  const finishedRef = useRef(false);
  const blinkRef = useRef(0);
  const targetRef = useRef(3);

  /* ─── cleanup ─── */
  const stop = useCallback(() => {
    if (frameTimerRef.current) clearInterval(frameTimerRef.current);
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    frameTimerRef.current = null;
    pollTimerRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => () => stop(), [stop]);

  /* ─── camera ─── */
  const startCamera = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      audio: false,
    });
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
    }
  }, []);

  /* ─── status polling ─── */
  const pollStatus = useCallback(async (sid) => {
    try {
      const s = await api.livenessStatus(sid);
      setChecklist({
        blink: s.blink_challenge || { passed: false, value: "waiting" },
        antiSpoof: s.anti_spoof || { passed: false, value: "sampling" },
        faceMatch: s.face_match || { passed: false, value: "waiting" },
      });
    } catch { /* ignore */ }
  }, []);

  /* ─── frame loop ─── */
  const runFrameLoop = useCallback(
    (sid) => {
      frameTimerRef.current = setInterval(async () => {
        if (busyRef.current || finishedRef.current) return;
        const video = videoRef.current;
        const canvas = canvasRef.current;
        if (!video || !canvas || video.readyState < 2 || !video.videoWidth) return;

        busyRef.current = true;
        try {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // 2.5× brightness boost (matches backend widget)
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const px = img.data;
          for (let i = 0; i < px.length; i += 4) {
            px[i]     = Math.min(255, px[i] * 2.5);
            px[i + 1] = Math.min(255, px[i + 1] * 2.5);
            px[i + 2] = Math.min(255, px[i + 2] * 2.5);
          }
          ctx.putImageData(img, 0, 0);

          const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
          if (!blob) return;

          const data = await api.pushFrame(sid, blob);
          setBlinkCount(data.blink_count);
          blinkRef.current = data.blink_count;
          setEar(data.ear);
          setFaceAligned(!!data.face_aligned);
          setTimeRemaining(data.time_remaining || 0);

          if (data.status === "failed") {
            setPhase("error");
            setError("Liveness challenge failed (timeout). Retry.");
            stop();
            return;
          }

          if (data.blink_count >= targetRef.current && !finishedRef.current) {
            finishedRef.current = true;
            await finishFlow(sid);
          }
        } catch { /* keep looping */ }
        finally { busyRef.current = false; }
      }, FRAME_INTERVAL_MS);
    },
    [stop] // eslint-disable-line react-hooks/exhaustive-deps
  );

  /* ─── finish flow: blink → PAD → face-match ─── */
  const finishFlow = useCallback(
    async (sid) => {
      setPhase("finishing");
      stop();
      try {
        await api.completeBlink(sid);
        await api.antiSpoof(sid);
        await api.faceMatch(sid);
        await pollStatus(sid);
        setPhase("done");
      } catch (e) {
        setPhase("error");
        setError(e.message || "Failed to complete liveness checks");
      }
    },
    [pollStatus, stop]
  );

  /* ─── start ─── */
  const start = async () => {
    setError(null);
    setPhase("starting");
    finishedRef.current = false;
    try {
      const s = await api.startLiveness(screeningSessionId);
      setLiveSid(s.liveness_session_id);
      targetRef.current = s.blink_target;
      setBlinkTarget(s.blink_target);
      setBlinkCount(0);
      blinkRef.current = 0;

      await startCamera();
      setPhase("running");
      runFrameLoop(s.liveness_session_id);
      pollTimerRef.current = setInterval(
        () => pollStatus(s.liveness_session_id),
        1200
      );
    } catch (e) {
      setPhase("error");
      setError(e.message || "Could not start liveness session");
      stop();
    }
  };

  /* ─── verify + advance ─── */
  const proceed = async () => {
    try {
      // Verify then hand off. If verify 400s (some check failed), we still
      // allow proceeding so the user sees the final risk verdict.
      try { await api.verifyLiveness(liveSid); } catch { /* ignore */ }
      onComplete(liveSid);
    } catch (e) {
      setError(e.message);
    }
  };

  /* ─── render ─── */

  const busy = phase === "starting" || phase === "running" || phase === "finishing";
  const ready = phase === "done" && checklist.blink.passed && checklist.antiSpoof.passed;

  return (
    <div className="rounded-2xl bg-surface-container-low p-6 md:p-8 shadow-sm border border-emerald-200">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* LEFT — camera viewport */}
        <div className="lg:col-span-7">
          <div className="relative rounded-2xl overflow-hidden bg-black aspect-[4/3] border-2 border-primary shadow-2xl flex flex-col">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`absolute inset-0 w-full h-full object-cover ${
                phase === "running" || phase === "finishing" ? "opacity-100" : "opacity-30"
              }`}
            />
            <canvas ref={canvasRef} className="hidden" />

            {/* Overlay chrome — matches mockup */}
            <div className="relative z-20 flex items-center justify-between p-4 text-white">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/70 backdrop-blur-md border border-white/20">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    phase === "running" ? "bg-emerald-400 animate-ping" : "bg-white/40"
                  }`}
                />
                <span className="font-mono text-[10px] tracking-wider font-bold text-white">
                  {phase === "running" ? "LIVE FEED — KIOSK CAM 04" : "CAMERA STANDBY"}
                </span>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-500/80 text-white font-mono text-[9px] font-bold">
                {phase === "running" ? `${timeRemaining}s` : "—"}
              </span>
            </div>

            {/* Face guide oval */}
            {(phase === "running" || phase === "finishing") && (
              <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
                <div
                  className={`w-56 h-64 rounded-[50%] border-4 border-dashed transition-colors ${
                    faceAligned ? "border-emerald-400 shadow-[0_0_36px_rgba(52,211,153,0.5)]" : "border-white/40"
                  }`}
                />
              </div>
            )}

            {/* Idle overlay */}
            {(phase === "idle" || phase === "starting") && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center text-white gap-3 bg-black/40">
                <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur border border-white/20 flex items-center justify-center">
                  <Camera className="w-7 h-7" />
                </div>
                <div className="font-mono text-xs opacity-80">
                  {phase === "starting" ? "Starting camera…" : "Camera will start when you begin"}
                </div>
              </div>
            )}

            {/* Live telemetry strip */}
            {phase === "running" && (
              <div className="relative z-20 mt-auto p-3 bg-black/75 backdrop-blur-md border-t border-white/10">
                <div className="flex items-center justify-between font-mono text-[10px] text-emerald-300">
                  <span className="flex items-center gap-1.5">
                    <Eye className="w-3.5 h-3.5" /> ear {ear.toFixed(3)}
                  </span>
                  <span className={faceAligned ? "text-emerald-300" : "text-amber-300"}>
                    face {faceAligned ? "aligned" : "off-center"}
                  </span>
                  <span className="text-white">
                    BLINK {blinkCount}/{blinkTarget}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT — controls + checklist */}
        <div className="lg:col-span-5 flex flex-col justify-between">
          <div className="space-y-4">
            <div>
              <span className="font-label-sm text-xs font-bold text-secondary uppercase tracking-wider">
                Step 2 Biometric Triage
              </span>
              <h3 className="font-headline-sm text-xl font-bold text-on-surface mt-1">
                Live Selfie &amp; Liveness Defense
              </h3>
              <p className="font-body-sm text-xs text-on-surface-variant mt-1">
                Blink {blinkTarget} times at the camera. We run a blink challenge,
                a MiniFASNetV2 anti-spoof check, and compare your face to the
                document photo.
              </p>
            </div>

            <div className="space-y-2">
              <CheckRow
                label="Blink challenge"
                passed={checklist.blink.passed}
                value={checklist.blink.value}
                active={phase === "running"}
              />
              <CheckRow
                label="Presentation-attack model"
                passed={checklist.antiSpoof.passed}
                value={checklist.antiSpoof.value}
                active={phase === "finishing"}
              />
              <CheckRow
                label="Face matched to document"
                passed={checklist.faceMatch.passed}
                value={checklist.faceMatch.value}
                active={phase === "finishing"}
              />
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-error-container/50 border border-error/30 text-on-error-container font-mono text-[11px] flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-emerald-200/50 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={onBack}
              disabled={busy}
              className="px-4 py-2 rounded-full bg-surface-container-high text-on-surface font-label-lg text-xs font-bold hover:bg-surface-container transition-all disabled:opacity-50 flex items-center gap-1.5"
            >
              <ArrowLeft className="w-4 h-4" /> Back
            </button>

            {phase === "idle" && (
              <button
                type="button"
                onClick={start}
                className="px-6 py-2.5 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-lg text-xs font-bold shadow-md hover:-translate-y-0.5 transition-all flex items-center gap-2"
              >
                <Play className="w-4 h-4" /> Start Liveness Check
              </button>
            )}

            {phase === "error" && (
              <button
                type="button"
                onClick={start}
                className="px-6 py-2.5 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-lg text-xs font-bold shadow-md flex items-center gap-2"
              >
                Retry
              </button>
            )}

            {busy && (
              <span className="font-mono text-[11px] text-on-surface-variant flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                {phase === "finishing" ? "Running PAD + face match…" : "Listening for blinks…"}
              </span>
            )}

            {phase === "done" && (
              <button
                type="button"
                onClick={proceed}
                className="px-6 py-2.5 rounded-full bg-primary hover:bg-[#143820] text-on-primary font-label-lg text-xs font-bold shadow-md hover:-translate-y-0.5 transition-all flex items-center gap-2"
              >
                {ready ? (
                  <>
                    Run Full Screening <ArrowRight className="w-4 h-4" />
                  </>
                ) : (
                  <>
                    Continue anyway <ArrowRight className="w-4 h-4" />
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

function CheckRow({ label, passed, value, active }) {
  return (
    <div
      className={`p-3.5 rounded-xl border shadow-sm flex items-start gap-3 ${
        passed
          ? "bg-emerald-50 border-emerald-200"
          : active
          ? "bg-secondary-container/40 border-secondary/30"
          : "bg-surface-container-lowest border-emerald-100"
      }`}
    >
      <div className="shrink-0 mt-0.5">
        {passed ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-600" />
        ) : active ? (
          <Loader2 className="w-5 h-5 text-primary animate-spin" />
        ) : (
          <Sparkles className="w-5 h-5 text-on-surface-variant/60" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-label-sm text-xs font-bold text-on-surface">{label}</div>
        <div className="font-mono text-[10px] text-on-surface-variant mt-0.5">{value}</div>
      </div>
      {passed && (
        <span className="font-mono text-[9px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">
          PASS
        </span>
      )}
    </div>
  );
}