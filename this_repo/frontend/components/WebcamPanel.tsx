"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  onSetupVerified: (verified: boolean) => void;
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
};

export default function WebcamPanel({ onSetupVerified }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [result, setResult] = useState<VisionResult>({
    valid: false,
    issues: [],
    message: "Camera idle",
  });

  useEffect(() => {
    let stream: MediaStream | null = null;
    let interval: ReturnType<typeof setInterval> | null = null;
    let inFlight = false;

    async function captureFrame() {
      if (inFlight || !videoRef.current || !canvasRef.current) return;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      if (!ctx || videoRef.current.readyState < 2) return;

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
        if (nextResult.valid) onSetupVerified(true);
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

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) videoRef.current.srcObject = stream;
        setResult({ valid: false, issues: [], message: "Analyzing..." });
        interval = setInterval(captureFrame, 1500);
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
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [onSetupVerified]);

  return (
    <div className="webcam">
      <video ref={videoRef} autoPlay muted playsInline />
      <canvas ref={canvasRef} hidden />
      <div className={`visionBadge ${result.valid ? "valid" : result.issues.length ? "issue" : ""}`}>
        {result.valid ? "Setup valid" : result.issues.length ? "Issues found" : "Analyzing..."}
      </div>
      <p>{result.message}</p>
      {result.issues.map((issue, index) => (
        <div key={`${issue.description}-${index}`} className={`issueCard ${issue.severity}`}>
          <strong>{issue.description}</strong>
          <span>{issue.fix}</span>
        </div>
      ))}
      <button
        className="override"
        onClick={() => {
          setResult({ valid: true, issues: [], message: "Manual demo override engaged." });
          onSetupVerified(true);
        }}
      >
        Skip verification (demo override)
      </button>
    </div>
  );
}
