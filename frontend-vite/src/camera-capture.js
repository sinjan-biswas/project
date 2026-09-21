/* A self-contained React camera flow. The stream never escapes this component. */
(function () {
  const mount = document.getElementById("cameraCaptureRoot");
  if (!mount || !window.React || !window.ReactDOM) return;

  const { createElement: h, useEffect, useRef, useState } = window.React;
  const root = window.ReactDOM.createRoot(mount);

  function CameraCapture() {
    const [status, setStatus] = useState("idle");
    const [message, setMessage] = useState("");
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const imageRef = useRef(null);
    const streamRef = useRef(null);
    const photoRef = useRef(null);

    const releaseStream = () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    };

    useEffect(() => {
      const onVisibilityChange = () => {
        if (document.visibilityState === "hidden") {
          releaseStream();
          setStatus("idle");
          setMessage("");
        }
      };
      document.addEventListener("visibilitychange", onVisibilityChange);
      return () => {
        document.removeEventListener("visibilitychange", onVisibilityChange);
        releaseStream();
      };
    }, []);

    const startCamera = async () => {
      releaseStream();
      setStatus("starting");
      setMessage("Starting…");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
          audio: false,
        });
        streamRef.current = stream;
        if (!videoRef.current) return releaseStream();
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setStatus("live");
        setMessage("");
      } catch (error) {
        releaseStream();
        setStatus("idle");
        const reason = error?.name === "NotAllowedError" || error?.name === "PermissionDeniedError"
          ? "Camera permission was denied. Allow access and try again."
          : error?.name === "NotFoundError" || error?.name === "DevicesNotFoundError"
            ? "No camera was found on this device."
            : "Unable to start the camera. Please try again.";
        setMessage(reason);
      }
    };

    const capturePhoto = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2 || !video.videoWidth) {
        setMessage("Waiting for the camera frame…");
        return;
      }
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      // The preview is mirrored only by CSS; canvas receives the original camera frame.
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
      // Match the reference flow: preview immediately from the canvas and keep
      // a Blob version for the multipart backend request.
      const imageDataUrl = canvas.toDataURL("image/jpeg", 0.92);
      if (imageRef.current) imageRef.current.src = imageDataUrl;
      canvas.toBlob((blob) => {
        if (!blob) {
          setMessage("The photo could not be captured. Try again.");
          return;
        }
        photoRef.current = blob;
        releaseStream();
        setStatus("captured");
        setMessage("");
      }, "image/jpeg", 0.92);
    };

    const stopCamera = () => {
      releaseStream();
      setStatus("idle");
      setMessage("");
    };

    const usePhoto = () => {
      if (!photoRef.current) return;
      window.dispatchEvent(new CustomEvent("camera-photo-ready", { detail: photoRef.current }));
      setStatus("done");
      setMessage("");
    };

    let controls;
    if (status === "idle") {
      const retry = /denied|found|unable/i.test(message);
      controls = h("button", { type: "button", className: "btn btn-primary camera-primary", onClick: startCamera }, retry ? "Try again" : "Start Camera");
    } else if (status === "starting") {
      controls = h("button", { type: "button", className: "btn btn-primary camera-primary", disabled: true }, [h("i", { key: "spinner", className: "fas fa-spinner fa-spin" }), " Starting…"]);
    } else if (status === "live") {
      controls = h("div", { className: "camera-live-actions" }, [
        h("button", { key: "capture", type: "button", className: "btn btn-primary camera-primary", onClick: capturePhoto }, "Capture Photo"),
        h("button", { key: "stop", type: "button", className: "camera-stop-icon", onClick: stopCamera, "aria-label": "Stop camera", title: "Stop camera" }, h("i", { className: "fas fa-stop" })),
      ]);
    } else if (status === "captured") {
      controls = h("div", { className: "camera-captured-actions" }, [
        h("button", { key: "retake", type: "button", className: "btn btn-outline camera-retake", onClick: startCamera }, "Retake"),
        h("button", { key: "use", type: "button", className: "btn btn-primary camera-use", onClick: usePhoto }, "Use this photo"),
      ]);
    } else {
      controls = h("div", { className: "camera-complete" }, [h("i", { key: "icon", className: "fas fa-check-circle" }), h("span", { key: "text" }, "Photo ready for screening")]);
    }

    return h(window.React.Fragment, null, [
      h("h4", { key: "title" }, [h("i", { key: "icon", className: "fas fa-user-circle" }), " Face Capture"]),
      h("p", { key: "subtitle", className: "text-muted" }, "Take a live photo for verification against the document."),
      h("p", { key: "guidance", className: "camera-guidance" }, "Face a light source, align your face, take off your glasses, and tuck your hair behind your ears."),
      h("div", { key: "preview", className: `camera-area camera-${status}` }, [
        h("video", { key: "video", ref: videoRef, autoPlay: true, playsInline: true, style: { display: status === "live" ? "block" : "none" } }),
        h("canvas", { key: "canvas", ref: canvasRef }),
        h("img", { key: "image", ref: imageRef, alt: "Captured face", style: { display: status === "captured" || status === "done" ? "block" : "none" } }),
        status === "live" && h("div", { key: "guide", className: "face-guide", "aria-hidden": "true" }),
        (status === "idle" || status === "starting") && h("div", { key: "placeholder", className: "camera-placeholder" }, [h("i", { key: "camera", className: status === "starting" ? "fas fa-spinner fa-spin" : "fas fa-camera" }), h("span", { key: "text" }, status === "starting" ? "Starting camera…" : "Position face in frame")]),
      ]),
      h("p", { key: "status", className: `camera-status-message${message ? " is-visible" : ""}`, "aria-live": "polite" }, message),
      h("div", { key: `controls-${status}`, className: "camera-buttons camera-controls-transition" }, controls),
    ]);
  }
  root.render(h(CameraCapture));
})();
