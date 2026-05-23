export type ScanSummary = {
  peak_sar: number;
  anomaly_count: number;
  total_points: number;
  anomalies: Array<{ position: [number, number, number]; sar: number }>;
};

export type SARPoint = {
  x: number;
  y: number;
  z: number;
  frequency_mhz: number;
  power_dbm: number;
  sar_w_kg: number;
  is_anomaly: boolean;
  pct_of_limit: number;
};

export type SARStreamEvent =
  | { event: "sar_point"; data: SARPoint }
  | { event: "scan_complete"; data: ScanSummary };

export type SARMonitorMessage =
  | { type: "ok"; sar: number; pct_of_limit: number }
  | { type: "warning"; message: string; sar: number; trend: "rising" | "stable" | "falling" }
  | { type: "critical"; message: string; recommendation: string };

export type AgentName =
  | "intake"
  | "jurisdiction_fcc"
  | "jurisdiction_eu"
  | "jurisdiction_ca"
  | "jurisdiction_jp"
  | "jurisdiction_br"
  | "test_plan"
  | "report_setup"
  | "report_measurement"
  | "report_citer"
  | "report_narrator"
  | "report_compliance";

export type BackendSSEEvent =
  | { event: "agent_start"; data: { agent: AgentName; message: string } }
  | { event: "agent_complete"; data: { agent: AgentName; output: string } }
  | { event: "anomaly_detected"; data: { id: string; severity: "warning" | "critical"; position: [number, number, number]; sar: number; limit: number; message: string; recommendation: string } }
  | { event: "phase_complete"; data: { phase: "intake" | "scoping" | "test_plan" | "report"; summary: string } }
  | { event: "report_ready"; data: { download_url: string } };
