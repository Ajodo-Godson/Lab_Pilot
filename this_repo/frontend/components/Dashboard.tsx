"use client";

import { useRef, useState } from "react";
import AgentFeed from "./AgentFeed";
import SARViewport, { SARViewportHandle, ScanSummary } from "./SARViewport";
import WebcamPanel from "./WebcamPanel";

type DashboardProps = {
  initialBom: string;
};

export default function Dashboard({ initialBom }: DashboardProps) {
  const [projectId, setProjectId] = useState<string>("");
  const [bomText, setBomText] = useState(initialBom);
  const [setupVerified, setSetupVerified] = useState(false);
  const [scanComplete, setScanComplete] = useState(false);
  const [status, setStatus] = useState("Idle");
  const sarRef = useRef<SARViewportHandle>(null);

  async function createAndScopeProject() {
    setStatus("Creating project...");
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    const createRes = await fetch(`${backend}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_name: "SmartPatch X1",
        bom_text: bomText,
        target_regions: ["US", "EU", "CA"],
      }),
    });
    const project = await createRes.json();
    setProjectId(project.project_id);
    setStatus("Starting scope pipeline...");
    await fetch(`${backend}/api/projects/${project.project_id}/scope`, { method: "POST" });
  }

  async function startScan() {
    setStatus("Starting synthetic SAR scan...");
    setScanComplete(false);
    await sarRef.current?.startScan();
  }

  async function generateReport() {
    if (!projectId) return;
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    const scan_summary: ScanSummary | null = sarRef.current?.getScanSummary() ?? null;
    if (!scan_summary) return;
    setStatus("Generating report...");
    await fetch(`${backend}/api/projects/${projectId}/report/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scan_summary }),
    });
  }

  return (
    <main className="dashboard">
      <section className="panel left">
        <h1>LabPilot</h1>
        <p className="muted">Synthetic SAR digital twin demo</p>
        <textarea value={bomText} onChange={(event) => setBomText(event.target.value)} />
        <button onClick={createAndScopeProject}>Create project + scope</button>
        <p className="status">{status}</p>
        <AgentFeed projectId={projectId} />
      </section>

      <section className="panel center">
        <div className="sectionHeader">
          <h2>Digital twin - SAR scan</h2>
          <div className="actions">
            <button disabled={!setupVerified} onClick={startScan}>Initialize scan</button>
            <button disabled={!scanComplete || !projectId} onClick={generateReport}>Generate report</button>
          </div>
        </div>
        <SARViewport ref={sarRef} onScanComplete={() => setScanComplete(true)} />
      </section>

      <section className="panel right">
        <h2>Setup verification</h2>
        <WebcamPanel onSetupVerified={setSetupVerified} />
        <div className="statusBoard">
          {["FCC", "EU", "CA", "JP", "BR"].map((region) => (
            <div key={region}><span className="dot" />{region}</div>
          ))}
        </div>
      </section>
    </main>
  );
}
