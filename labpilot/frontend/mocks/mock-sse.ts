import { createServer } from "http";

const events = [
  { event: "agent_start", data: { agent: "intake", message: "Parsing BOM..." }, delay: 400 },
  { event: "agent_complete", data: { agent: "intake", output: "nRF52840 BLE + RTL8723DE WiFi. Body-worn: true." }, delay: 1200 },
  { event: "device_profile", data: {
    device_name: "SmartPatch X1", form_factor: "wearable", body_worn: true, held_to_head: false,
    radios: [
      { chip: "Nordic nRF52840", type: "BLE", freq_mhz: 2440, power_dbm: 8 },
      { chip: "Realtek RTL8723DE", type: "WiFi+BT", freq_mhz: 2412, power_dbm: 20 },
    ],
    target_regions: ["US", "EU", "CA", "JP", "BR"], notes: "Body-worn wearable, both radios in 2.4 GHz ISM band.",
  }, delay: 1300 },
  { event: "agent_start", data: { agent: "jurisdiction_fcc", message: "Analyzing FCC Part 15..." }, delay: 1400 },
  { event: "agent_start", data: { agent: "jurisdiction_eu", message: "Analyzing EU RED..." }, delay: 1500 },
  { event: "agent_start", data: { agent: "jurisdiction_ca", message: "Analyzing ISED Canada..." }, delay: 1600 },
  { event: "agent_start", data: { agent: "jurisdiction_jp", message: "Analyzing Japan MIC..." }, delay: 1700 },
  { event: "agent_start", data: { agent: "jurisdiction_br", message: "Analyzing ANATEL Brazil..." }, delay: 1800 },
  { event: "agent_complete", data: { agent: "jurisdiction_fcc", output: "Requires: Part 15.247, SAR per KDB 447498. Est: 40 robot hours." }, delay: 3200 },
  { event: "agent_complete", data: { agent: "jurisdiction_eu", output: "Requires: EN 300 328, EN 62311 SAR (2.0 W/kg). CE marking." }, delay: 3400 },
  { event: "agent_complete", data: { agent: "jurisdiction_ca", output: "Requires: ISED RSS-247, RSS-102 SAR (1.6 W/kg)." }, delay: 3600 },
  { event: "agent_complete", data: { agent: "jurisdiction_jp", output: "Requires: ARIB STD-T66, MIC Ordinance 88, Giteki mark." }, delay: 3800 },
  { event: "agent_complete", data: { agent: "jurisdiction_br", output: "Requires: ANATEL Resolution 715/2019, SAR homologation." }, delay: 4000 },
  { event: "phase_complete", data: { phase: "scoping", summary: "5 jurisdictions. 14 tests required. ~3 weeks lab time." }, delay: 4200 },
  { event: "agent_start", data: { agent: "test_plan", message: "Drafting test plan with citations..." }, delay: 4800 },
  { event: "agent_complete", data: { agent: "test_plan", output: "14 configurations, 6 frequency bands, 4 SAR positions." }, delay: 7500 },
  { event: "phase_complete", data: { phase: "test_plan", summary: "Test plan complete" }, delay: 7800 },
  { event: "anomaly_detected", data: {
    id: "a1", severity: "critical",
    position: [8.2, 4.4, 3.0], sar: 1.54, limit: 1.6,
    message: "SAR 1.54 W/kg — 96% of FCC limit. Growth trajectory indicates breach within 4 steps.",
    recommendation: "Pause test matrices. Review device antenna orientation.",
  }, delay: 11000 },
  { event: "agent_start", data: { agent: "report_setup", message: "Composing setup section..." }, delay: 13000 },
  { event: "agent_start", data: { agent: "report_measurement", message: "Composing measurement section..." }, delay: 13100 },
  { event: "agent_start", data: { agent: "report_compliance", message: "Composing compliance section..." }, delay: 13200 },
  { event: "agent_complete", data: { agent: "report_setup", output: "Section complete" }, delay: 15000 },
  { event: "agent_complete", data: { agent: "report_measurement", output: "Section complete" }, delay: 15500 },
  { event: "agent_complete", data: { agent: "report_compliance", output: "Section complete" }, delay: 16000 },
  { event: "report_ready", data: { download_url: "/api/projects/demo-project/report" }, delay: 17000 },
];

createServer((req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (!req.url?.includes("/events")) {
    res.writeHead(404);
    res.end();
    return;
  }

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  events.forEach(({ event, data, delay }) => {
    setTimeout(() => {
      res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
    }, delay);
  });
}).listen(8003, () => console.log("Mock backend SSE listening on http://localhost:8003"));
