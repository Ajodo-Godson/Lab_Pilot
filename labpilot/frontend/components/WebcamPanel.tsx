"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  onSetupVerified: (verified: boolean, setupEstimate?: SetupEstimate) => void;
  onDeviceIdentified?: (device: any) => void;
};

type VisionIssue = {
  description: string;
  severity: "warning" | "error";
  fix: string;
};

type VisionResult = {
  valid: boolean;
  issues: VisionIssue[];
  message: string;
  setup_estimate?: SetupEstimate;
};

export type SetupEstimate = {
  probe_distance_cm: number;
  probe_angle_deg: number;
  antenna_x: number;
  antenna_y: number;
  setup_quality: "good" | "acceptable" | "poor";
  notes: string;
};

export default function WebcamPanel({ onSetupVerified, onDeviceIdentified }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [acceptedFrame, setAcceptedFrame] = useState("");
  const [identifying, setIdentifying] = useState(false);
  const [result, setResult] = useState<VisionResult>({
    valid: false,
    issues: [],
    message: "Camera idle",
  });

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    let inFlight = false;
    let attemptCount = 0;
    const MAX_ATTEMPTS = 8;

    function stopCamera() {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    }

    async function captureFrame() {
      if (acceptedFrame || inFlight || !videoRef.current || !canvasRef.current) return;
      if (attemptCount >= MAX_ATTEMPTS) {
        if (interval) clearInterval(interval);
        setResult({ valid: false, issues: [], message: "Auto-check limit reached — use override to proceed." });
        return;
      }
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      if (!ctx || videoRef.current.readyState < 2) return;

      attemptCount += 1;
      inFlight = true;
      canvas.width = 320;
      canvas.height = 240;
      ctx.drawImage(videoRef.current, 0, 0, 320, 240);
      const frame = canvas.toDataURL("image/jpeg", 0.72).split(",")[1];

      try {
        const response = await fetch("/api/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ frame }),
        });
        const nextResult = (await response.json()) as VisionResult;
        setResult(nextResult);
        if (nextResult.valid) {
          setAcceptedFrame(`data:image/jpeg;base64,${frame}`);
          onSetupVerified(true, nextResult.setup_estimate);
          if (interval) clearInterval(interval);
          stopCamera();
        }
      } catch {
        setResult({
          valid: false,
          issues: [{ description: "Vision check unavailable", severity: "warning", fix: "Use demo override if needed." }],
          message: "Vision service unavailable",
        });
      } finally {
        inFlight = false;
      }
    }

    async function refreshDevices() {
      const nextDevices = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "videoinput");
      setDevices(nextDevices);
      if (!selectedDeviceId && nextDevices[0]?.deviceId) {
        setSelectedDeviceId(nextDevices[0].deviceId);
      }
    }

    async function start() {
      if (acceptedFrame) return;
      try {
        stopCamera();
        streamRef.current = await navigator.mediaDevices.getUserMedia({
          video: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : true,
        });
        if (videoRef.current) videoRef.current.srcObject = streamRef.current;
        await refreshDevices();
        setResult({ valid: false, issues: [], message: "Analyzing..." });
        interval = setInterval(captureFrame, 3000);
      } catch {
        setResult({
          valid: false,
          issues: [{ description: "Camera permission denied or unavailable", severity: "error", fix: "Enable camera or use demo override." }],
          message: "Camera unavailable",
        });
      }
    }

    start();
    return () => {
      if (interval) clearInterval(interval);
      stopCamera();
    };
  }, [acceptedFrame, onSetupVerified, selectedDeviceId]);

  async function identifyDevice() {
    if (!acceptedFrame) return;
    setIdentifying(true);
    try {
      const base64Part = acceptedFrame.split(",")[1];
      const res = await fetch("/api/identify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ frame: base64Part }),
      });
      if (!res.ok) throw new Error("Identification failed");
      const data = await res.json();
      onDeviceIdentified?.(data);
    } catch (err) {
      console.error(err);
      alert("Failed to identify device. Make sure your API key and Internet are working.");
    } finally {
      setIdentifying(false);
    }
  }

  return (
    <div className="webcam">
      <select
        className="cameraSelect"
        value={selectedDeviceId}
        onChange={(event) => setSelectedDeviceId(event.target.value)}
        aria-label="Camera source"
      >
        {devices.length === 0 && <option value="">Default camera</option>}
        {devices.map((device, index) => (
          <option key={device.deviceId} value={device.deviceId}>
            {device.label || `Camera ${index + 1}`}
          </option>
        ))}
      </select>
      {acceptedFrame ? (
        <img className="acceptedFrame" src={acceptedFrame} alt="Accepted setup snapshot" />
      ) : (
        <video ref={videoRef} autoPlay muted playsInline />
      )}
      <canvas ref={canvasRef} hidden />
      <div className={`visionBadge ${result.valid ? "valid" : result.issues.length ? "issue" : ""}`}>
        {result.valid ? "Setup accepted" : result.issues.length ? "Issues found" : "Analyzing..."}
      </div>
      <p>{result.message}</p>
      {result.valid && result.setup_estimate && (
        <div className="setupEstimate">
          <span>distance {result.setup_estimate.probe_distance_cm.toFixed(1)} cm</span>
          <span>angle {Math.round(result.setup_estimate.probe_angle_deg)} deg</span>
          <span>offset {result.setup_estimate.antenna_x.toFixed(1)}</span>
          <span>{result.setup_estimate.setup_quality}</span>
        </div>
      )}
      {result.valid && (
        <button
          disabled={identifying}
          style={{ width: "100%", marginTop: "6px", background: "#042f3f", borderColor: "#164e63" }}
          onClick={identifyDevice}
        >
          {identifying ? "Identifying..." : "🔍 Identify device"}
        </button>
      )}
      {result.issues.map((issue, index) => (
        <div key={`${issue.description}-${index}`} className={`issueCard ${issue.severity}`}>
          <strong>{issue.description}</strong>
          <span>{issue.fix}</span>
        </div>
      ))}
      <button
        className="override"
        onClick={() => {
          if (!videoRef.current || !canvasRef.current || videoRef.current.readyState < 2) {
            setResult({
              valid: false,
              issues: [{ description: "No live setup frame available", severity: "error", fix: "Select a camera and show the device/probe setup first." }],
              message: "Cannot lock setup without a camera frame.",
            });
            return;
          }
          const canvas = canvasRef.current;
          const ctx = canvas.getContext("2d");
          if (!ctx) return;
          canvas.width = 320;
          canvas.height = 240;
          ctx.drawImage(videoRef.current, 0, 0, 320, 240);
          const setupEstimate: SetupEstimate = {
            probe_distance_cm: 3,
            probe_angle_deg: 90,
            antenna_x: 0,
            antenna_y: 1.5,
            setup_quality: "acceptable",
            notes: "Manual lock from current visible setup frame.",
          };
          setAcceptedFrame(canvas.toDataURL("image/jpeg", 0.72));
          setResult({ valid: true, issues: [], message: "Current setup frame locked for simulation.", setup_estimate: setupEstimate });
          onSetupVerified(true, setupEstimate);
          streamRef.current?.getTracks().forEach((track) => track.stop());
        }}
      >
        Lock current setup (demo override)
      </button>
    </div>
  );
}
