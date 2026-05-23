"use client";

import { forwardRef, useImperativeHandle, useRef, useState } from "react";

export type ScanSummary = {
  peak_sar: number;
  anomaly_count: number;
  total_points: number;
  anomalies: Array<{ position: [number, number, number]; sar: number }>;
};

type SARPoint = {
  x: number;
  y: number;
  z: number;
  sar_w_kg: number;
  pct_of_limit: number;
  is_anomaly: boolean;
};

export type SARViewportHandle = {
  startScan: () => Promise<void>;
  getScanSummary: () => ScanSummary | null;
};

type Props = {
  onScanComplete: (summary: ScanSummary) => void;
};

const SARViewport = forwardRef<SARViewportHandle, Props>(function SARViewport({ onScanComplete }, ref) {
  const [points, setPoints] = useState<SARPoint[]>([]);
  const [lastAlert, setLastAlert] = useState("");
  const summaryRef = useRef<ScanSummary | null>(null);

  useImperativeHandle(ref, () => ({
    startScan,
    getScanSummary: () => summaryRef.current,
  }));

  async function startScan() {
    const simulator = process.env.NEXT_PUBLIC_SIMULATOR_URL ?? "http://localhost:8002";
    setPoints([]);
    setLastAlert("");
    summaryRef.current = null;

    await fetch(`${simulator}/api/simulator/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ antenna_x: 0, antenna_y: 1.5, frequency_mhz: 2412, power_dbm: 20 }),
    });

    const monitor = new WebSocket(`${simulator}/sar-monitor`);
    monitor.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "warning" || message.type === "critical") {
        setLastAlert(message.message);
      }
    };

    const source = new EventSource(`${simulator}/api/simulator/stream`);
    source.addEventListener("sar_point", (event) => {
      const point: SARPoint = JSON.parse(event.data);
      setPoints((current) => [...current.slice(-399), point]);
      if (monitor.readyState === WebSocket.OPEN) {
        monitor.send(JSON.stringify(point));
      }
    });
    source.addEventListener("scan_complete", (event) => {
      const summary: ScanSummary = JSON.parse(event.data);
      summaryRef.current = summary;
      onScanComplete(summary);
      source.close();
      monitor.close();
    });
  }

  const peak = points.reduce((max, point) => Math.max(max, point.sar_w_kg), 0);

  return (
    <div className="sarBox">
      <div className="placeholderScene">
        {points.slice(-120).map((point, index) => (
          <span
            key={`${point.x}-${point.y}-${point.z}-${index}`}
            className={point.is_anomaly ? "voxel hot" : "voxel"}
            style={{
              left: `${((point.x + 8) / 16) * 100}%`,
              top: `${((point.y + 10) / 20) * 100}%`,
              opacity: Math.min(1, Math.max(0.25, point.pct_of_limit)),
            }}
          />
        ))}
      </div>
      <div className="stats">
        <span>points {points.length}</span>
        <span>peak {peak.toFixed(3)} W/kg</span>
        <span>limit 1.6 W/kg</span>
      </div>
      {lastAlert && <div className="alert">{lastAlert}</div>}
    </div>
  );
});

export default SARViewport;
