"use client";

import { useCallback, useRef, useState } from "react";
import AgentFeed, { FeedEvent } from "./AgentFeed";
import SARViewport, { SARSetupEstimate, SARViewportHandle, ScanSummary } from "./SARViewport";
import WebcamPanel, { SetupEstimate } from "./WebcamPanel";

type DashboardProps = {
  initialBom: string;
};

type Jurisdiction = "FCC" | "EU" | "CA" | "JP" | "BR";
type JurisdictionState = "idle" | "active" | "complete" | "skipped";

const jurisdictionAgents: Record<string, Jurisdiction> = {
  jurisdiction_fcc: "FCC",
  jurisdiction_eu: "EU",
  jurisdiction_ca: "CA",
  jurisdiction_jp: "JP",
  jurisdiction_br: "BR",
};

const initialJurisdictions: Record<Jurisdiction, JurisdictionState> = {
  FCC: "idle",
  EU: "idle",
  CA: "idle",
  JP: "idle",
  BR: "idle",
};

export default function Dashboard({ initialBom }: DashboardProps) {
  const [projectId, setProjectId] = useState<string>("");
  const [bomText, setBomText] = useState(initialBom);
  const [deviceName, setDeviceName] = useState("SmartPatch X1");
  const [setupVerified, setSetupVerified] = useState(false);
  const [scanComplete, setScanComplete] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [setupEstimate, setSetupEstimate] = useState<SetupEstimate | null>(null);
  const [jurisdictions, setJurisdictions] = useState(initialJurisdictions);
  const sarRef = useRef<SARViewportHandle>(null);

  const handleAgentEvent = useCallback((event: FeedEvent) => {
    const agent = typeof event.data.agent === "string" ? event.data.agent : "";
    const jurisdiction = jurisdictionAgents[agent];
    if (!jurisdiction) return;
    setJurisdictions((current) => {
      let state: JurisdictionState = "active";
      if (event.event === "agent_complete") {
        const output = typeof event.data.output === "string" ? event.data.output : "";
        if (output.startsWith("Not requested")) {
          state = "skipped";
        } else {
          state = "complete";
        }
      }
      return {
        ...current,
        [jurisdiction]: state,
      };
    });
  }, []);

  async function createAndScopeProject() {
    setStatus("Creating project...");
    setScanComplete(false);
    setJurisdictions(initialJurisdictions);
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

    try {
      const createRes = await fetch(`${backend}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_name: deviceName,
          bom_text: bomText,
          target_regions: ["US", "EU", "CA"],
        }),
      });
      if (!createRes.ok) throw new Error("Project endpoint unavailable");
      const project = (await createRes.json()) as { project_id: string };
      setProjectId(project.project_id);
      setStatus("Starting scope pipeline...");
      await fetch(`${backend}/api/projects/${project.project_id}/scope`, { method: "POST" });
      setStatus("Scoping agents running");
    } catch {
      setProjectId("demo-project");
      setStatus("Using mock event stream");
    }
  }

  async function startScan() {
    setStatus("Starting synthetic SAR scan...");
    setScanComplete(false);
    await sarRef.current?.startScan(setupEstimate as SARSetupEstimate | null);
  }

  async function generateReport() {
    if (!projectId) return;
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    const scan_summary: ScanSummary | null = sarRef.current?.getScanSummary() ?? null;
    if (!scan_summary) return;
    setStatus("Generating report...");
    const response = await fetch(`${backend}/api/projects/${projectId}/report/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scan_summary }),
    });
    setStatus(response.ok ? "Report agents running" : "Report trigger failed");
  }

  return (
    <main className="dashboard">
      <section className="panel left">
        <div>
          <h1>LabPilot</h1>
          <p className="muted">Synthetic SAR digital twin demo</p>
        </div>
        <textarea value={bomText} onChange={(event) => setBomText(event.target.value)} aria-label="Device BOM" />
        <button onClick={createAndScopeProject}>Create project + scope</button>
        <p className="status">{status}</p>
        <div>
          <h2>Agent stream</h2>
          <AgentFeed projectId={projectId} onEvent={handleAgentEvent} />
        </div>
      </section>

      <section className="panel center">
        <div className="sectionHeader">
          <h2>Digital twin - SAR scan</h2>
          <div className="actions">
            <button disabled={!setupVerified} onClick={startScan}>
              Initialize scan
            </button>
            <button disabled={!scanComplete || !projectId} onClick={generateReport}>
              Generate report
            </button>
          </div>
        </div>
        <SARViewport
          ref={sarRef}
          onScanComplete={() => {
            setScanComplete(true);
            setStatus("Scan complete");
          }}
        />
      </section>

      <section className="panel right">
        <h2>Setup verification</h2>
        <WebcamPanel
          onSetupVerified={(verified, estimate) => {
            setSetupVerified(verified);
            if (estimate) setSetupEstimate(estimate);
          }}
          onDeviceIdentified={(device) => {
            const chipsList = Array.isArray(device.chips)
              ? device.chips.map((c: any) => `- ${c.chip || c.type || "Wireless Chip"} (${c.type}, ${c.freq_mhz} MHz, ${c.power_dbm} dBm)`).join("\n")
              : "";
            const formatted = `${device.device_name}
- Form factor: ${device.form_factor || "unknown"}
- Body worn: ${device.body_worn ? "true" : "false"}
${chipsList}
- Notes: ${device.notes || "None"}`;
            setDeviceName(device.device_name);
            setBomText(formatted);
            setStatus(`Identified ${device.device_name}!`);
          }}
        />
        <div className="statusBoard">
          {(Object.keys(jurisdictions) as Jurisdiction[]).map((region) => (
            <div key={region}>
              <span className={`dot ${jurisdictions[region]}`} />
              {region}
              <small>{jurisdictions[region]}</small>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
