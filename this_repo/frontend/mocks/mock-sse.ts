import { createServer } from "http";

const events = [
  { event: "agent_start", data: { agent: "intake", message: "Parsing BOM..." }, delay: 400 },
  { event: "agent_complete", data: { agent: "intake", output: "BLE + WiFi, body-worn=true" }, delay: 1200 },
  { event: "agent_start", data: { agent: "jurisdiction_fcc", message: "Analyzing FCC Part 15..." }, delay: 1400 },
  { event: "agent_start", data: { agent: "jurisdiction_eu", message: "Analyzing EU RED..." }, delay: 1400 },
  { event: "agent_start", data: { agent: "jurisdiction_ca", message: "Analyzing ISED..." }, delay: 1400 },
  { event: "agent_complete", data: { agent: "jurisdiction_fcc", output: "Requires SAR per KDB 447498." }, delay: 3000 },
  { event: "phase_complete", data: { phase: "scoping", summary: "5 jurisdictions analyzed." }, delay: 4200 },
  { event: "agent_start", data: { agent: "test_plan", message: "Drafting test plan..." }, delay: 5000 },
  { event: "agent_complete", data: { agent: "test_plan", output: "14 configurations, 4 SAR positions." }, delay: 7400 },
  { event: "report_ready", data: { download_url: "/mock-report.pdf" }, delay: 14000 },
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
