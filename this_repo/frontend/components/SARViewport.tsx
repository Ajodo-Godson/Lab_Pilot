"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Edges } from "@react-three/drei";
import { DoubleSide } from "three";
import { forwardRef, MutableRefObject, useEffect, useImperativeHandle, useRef, useState } from "react";
import RobotArm, { RobotArmHandle } from "./RobotArm";
import VoxelCloud, { SARPoint, VoxelCloudHandle } from "./VoxelCloud";

export type ScanSummary = {
  peak_sar: number;
  anomaly_count: number;
  total_points: number;
  anomalies: Array<{ position: [number, number, number]; sar: number }>;
};

type MonitorMessage =
  | { type: "ok"; sar: number; pct_of_limit: number }
  | { type: "warning"; message: string; sar: number; trend: "rising" | "stable" | "falling" }
  | { type: "critical"; message: string; recommendation: string };

export type SARViewportHandle = {
  startScan: (setupEstimate?: SARSetupEstimate | null) => Promise<void>;
  getScanSummary: () => ScanSummary | null;
};

type Props = {
  onScanComplete: (summary: ScanSummary) => void;
};

export type SARSetupEstimate = {
  probe_distance_cm: number;
  probe_angle_deg: number;
  antenna_x: number;
  antenna_y: number;
  setup_quality: "good" | "acceptable" | "poor";
  notes: string;
};

function wsUrlFromHttp(url: string) {
  return url.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
}

function emptySummary(): ScanSummary {
  return { peak_sar: 0, anomaly_count: 0, total_points: 0, anomalies: [] };
}

function scanParamsFromSetup(setupEstimate?: SARSetupEstimate | null) {
  if (!setupEstimate) {
    return { antenna_x: 0, antenna_y: 1.5, frequency_mhz: 2412, power_dbm: 20 };
  }

  const anglePenalty = Math.min(3, Math.abs(90 - setupEstimate.probe_angle_deg) / 15);
  const distanceBoost = Math.max(0, 3 - setupEstimate.probe_distance_cm) * 0.45;
  const qualityPenalty = setupEstimate.setup_quality === "poor" ? 1.5 : setupEstimate.setup_quality === "acceptable" ? 0.5 : 0;

  return {
    antenna_x: setupEstimate.antenna_x,
    antenna_y: setupEstimate.antenna_y,
    frequency_mhz: 2412,
    power_dbm: Number((20 + anglePenalty + distanceBoost + qualityPenalty).toFixed(2)),
  };
}

function SceneContent({
  latestPoint,
  anomalyActive,
  voxelRef,
}: {
  latestPoint: SARPoint | null;
  anomalyActive: boolean;
  voxelRef: MutableRefObject<VoxelCloudHandle | null>;
}) {
  const armRef = useRef<RobotArmHandle>(null);

  useFrame(() => {
    if (latestPoint) {
      armRef.current?.updateArm(latestPoint.x, latestPoint.y, latestPoint.z);
    }
  });

  return (
    <>
      <ambientLight intensity={0.45} />
      <directionalLight position={[10, 22, 18]} intensity={1.2} />
      <pointLight position={[-8, 10, 8]} intensity={0.8} color="#3bb7ff" />

      <OrbitControls
        enableDamping
        dampingFactor={0.05}
        autoRotate
        autoRotateSpeed={0.5}
        target={[0, 0, 2]}
        makeDefault
      />

      <mesh position={[0, 0, 2]}>
        <boxGeometry args={[15, 22, 8]} />
        <meshPhongMaterial
          color="#2255bb"
          transparent
          opacity={0.08}
          side={DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, 0, 2]}>
        <boxGeometry args={[15, 22, 8]} />
        <meshBasicMaterial visible={false} />
        <Edges color="#3b82f6" scale={1.001} />
      </mesh>
      <mesh>
        <boxGeometry args={[22, 27, 20]} />
        <meshBasicMaterial color="#8ba4c7" wireframe transparent opacity={0.28} />
      </mesh>
      <mesh position={[0, -7.5, 6.45]}>
        <boxGeometry args={[5.2, 8, 0.35]} />
        <meshPhongMaterial color="#121826" emissive="#020617" />
      </mesh>
      <gridHelper args={[28, 28, "#27364d", "#172033"]} position={[0, -11, 0]} />

      <VoxelCloud ref={voxelRef} />
      <RobotArm ref={armRef} anomaly={anomalyActive} />
    </>
  );
}

const SARViewport = forwardRef<SARViewportHandle, Props>(function SARViewport({ onScanComplete }, ref) {
  const [currentPoint, setCurrentPoint] = useState<SARPoint | null>(null);
  const [voxelCount, setVoxelCount] = useState(0);
  const [monitorAlert, setMonitorAlert] = useState<{ level: "warning" | "critical"; text: string } | null>(null);
  const [scanState, setScanState] = useState<"idle" | "starting" | "scanning" | "complete" | "error">("idle");
  const voxelRef = useRef<VoxelCloudHandle | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const monitorRef = useRef<WebSocket | null>(null);
  const pendingMonitorPoints = useRef<SARPoint[]>([]);
  const summaryRef = useRef<ScanSummary | null>(null);

  useImperativeHandle(ref, () => ({
    startScan,
    getScanSummary: () => summaryRef.current,
  }));

  useEffect(() => closeConnections, []);

  function closeConnections() {
    sourceRef.current?.close();
    monitorRef.current?.close();
    sourceRef.current = null;
    monitorRef.current = null;
    pendingMonitorPoints.current = [];
  }

  function forwardToMonitor(point: SARPoint) {
    const monitor = monitorRef.current;
    if (!monitor || monitor.readyState === WebSocket.CLOSING || monitor.readyState === WebSocket.CLOSED) return;
    if (monitor.readyState === WebSocket.OPEN) {
      monitor.send(JSON.stringify(point));
      return;
    }
    pendingMonitorPoints.current.push(point);
  }

  async function startScan(setupEstimate?: SARSetupEstimate | null) {
    const simulator = process.env.NEXT_PUBLIC_SIMULATOR_URL ?? "http://localhost:8002";
    closeConnections();
    setCurrentPoint(null);
    setVoxelCount(0);
    setMonitorAlert(null);
    setScanState("starting");
    summaryRef.current = emptySummary();
    voxelRef.current?.reset();

    try {
      const scanParams = scanParamsFromSetup(setupEstimate);
      await fetch(`${simulator}/api/simulator/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(scanParams),
      });

      const monitor = new WebSocket(`${wsUrlFromHttp(simulator)}/sar-monitor`);
      monitor.onopen = () => {
        pendingMonitorPoints.current.splice(0).forEach((point) => monitor.send(JSON.stringify(point)));
      };
      monitor.onmessage = (event) => {
        const message = JSON.parse(event.data) as MonitorMessage;
        if (message.type === "warning") {
          setMonitorAlert({ level: "warning", text: message.message });
        }
        if (message.type === "critical") {
          setMonitorAlert({ level: "critical", text: `${message.message} ${message.recommendation}` });
        }
      };
      monitor.onerror = () => setMonitorAlert({ level: "warning", text: "SAR monitor socket unavailable; scan stream still running." });
      monitorRef.current = monitor;

      const source = new EventSource(`${simulator}/api/simulator/stream`);
      source.addEventListener("open", () => setScanState("scanning"));
      source.addEventListener("sar_point", (event) => {
        const point = JSON.parse(event.data) as SARPoint;
        setCurrentPoint(point);
        setVoxelCount((count) => count + 1);
        voxelRef.current?.addPoint(point);
        forwardToMonitor(point);

        const summary = summaryRef.current ?? emptySummary();
        summary.total_points += 1;
        summary.peak_sar = Math.max(summary.peak_sar, point.sar_w_kg);
        if (point.is_anomaly) {
          summary.anomaly_count += 1;
          summary.anomalies.push({ position: [point.x, point.y, point.z], sar: point.sar_w_kg });
        }
        summaryRef.current = summary;
      });
      source.addEventListener("scan_complete", (event) => {
        const summary = JSON.parse(event.data) as ScanSummary;
        summaryRef.current = summary;
        setScanState("complete");
        onScanComplete(summary);
        closeConnections();
      });
      source.onerror = () => {
        setScanState("error");
        setMonitorAlert({ level: "critical", text: "Simulator stream disconnected." });
        closeConnections();
      };
      sourceRef.current = source;
    } catch {
      setScanState("error");
      setMonitorAlert({ level: "critical", text: "Unable to start simulator scan." });
      closeConnections();
    }
  }

  const peak = summaryRef.current?.peak_sar ?? 0;
  const pct = currentPoint ? Math.round(currentPoint.pct_of_limit * 100) : 0;

  return (
    <div className="sarBox">
      <div className="sceneFrame">
        <Canvas camera={{ position: [24, 20, 30], fov: 45 }} gl={{ antialias: true }}>
          <SceneContent latestPoint={currentPoint} anomalyActive={Boolean(currentPoint?.is_anomaly)} voxelRef={voxelRef} />
        </Canvas>
      </div>
      <div className="stats">
        <span>state {scanState}</span>
        <span>current {currentPoint ? currentPoint.sar_w_kg.toFixed(4) : "0.0000"} W/kg</span>
        <span>{pct}% limit</span>
        <span>voxels {voxelCount}</span>
        <span>peak {peak.toFixed(4)} W/kg</span>
      </div>
      {monitorAlert && <div className={`alert ${monitorAlert.level}`}>{monitorAlert.text}</div>}
    </div>
  );
});

export default SARViewport;
