"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  onSetupVerified: (verified: boolean) => void;
};

export default function WebcamPanel({ onSetupVerified }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [message, setMessage] = useState("Camera idle");

  useEffect(() => {
    let stream: MediaStream | null = null;
    let interval: ReturnType<typeof setInterval> | null = null;

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) videoRef.current.srcObject = stream;
        setMessage("Analyzing...");
        interval = setInterval(captureFrame, 1500);
      } catch {
        setMessage("Camera unavailable. Use manual override.");
      }
    }

    async function captureFrame() {
      if (!videoRef.current || !canvasRef.current) return;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      canvas.width = 320;
      canvas.height = 240;
      ctx.drawImage(videoRef.current, 0, 0, 320, 240);
      const frame = canvas.toDataURL("image/jpeg", 0.7).split(",")[1];
      const response = await fetch("/api/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ frame }),
      });
      const result = await response.json();
      setMessage(result.message ?? "Analyzed");
      if (result.valid) onSetupVerified(true);
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
      <p>{message}</p>
      <button className="override" onClick={() => onSetupVerified(true)}>Skip verification (demo override)</button>
    </div>
  );
}
