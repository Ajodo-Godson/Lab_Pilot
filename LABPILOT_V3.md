# LabPilot — Final Architectural Plan (V3)
### Google I/O Hackathon · Gemini 3.5 Flash · 6.5-Hour Sprint

> **Honest framing:** LabPilot is a synthetic SAR digital twin demo. The scan data is physics-simulated, not physically measured. The AI intelligence (agents, vision, monitoring) is real. Own this — DeepMind researchers respect honesty over overclaiming.

---

## What We're Building

LabPilot automates the engineering intelligence layer of RF/wireless certification testing — from device intake to compliance report — using Gemini 3.5 Flash managed agents, frame-by-frame vision verification, and a physics-based SAR simulation with a 3D digital twin.

**Two-act demo structure:**
- **Act 1 — Vision Setup Check:** Flash analyzes webcam frames of a phone + pen on the desk, verifies positioning, and clears the test to begin. Has a manual override so demo never dies on camera failure.
- **Act 2 — Digital Twin Scan:** A 3D robot arm sweeps a volumetric SAR grid. Flash monitors the live data stream via WebSocket and flags anomalies mid-scan.

---

## Build Priority

| Priority | What | Who |
|---|---|---|
| Must | Intake → scoping pipeline, 5 parallel jurisdiction agents, SSE stream | P1 |
| Must | SAR simulator SSE with guaranteed anomaly at (8.2, 4.4, 3.0) | P2 |
| Must | SAR monitor WebSocket wired to frontend SSE forward | P2 + P3 |
| Must | Dashboard + 3D robot arm + voxel heatmap + agent feed | P3 |
| Must | Manual override button on webcam gate | P3 |
| Must | Scan summary (peak SAR + anomalies) passed into report agent | P1 + P3 |
| Nice | Webcam vision check (frame-by-frame, honest framing) | P3 |
| Nice | 5 parallel report agents generating compliance document | P1 |
| Stretch | True Gemini Live API implementation | P2 |
| Cut | R&S EMCvu XML script compiler | — |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GOOGLE AI STUDIO                         │
│  Gemini 3.5 Flash · Managed Agents · Context Cache          │
│  Code Execution · Search Grounding                           │
└──────────────┬──────────────────────┬────────────────────────┘
               │                      │
        REST/SSE :8000         Vision API calls
               │                      │
               ▼                      ▼
┌─────────────────────┐   ┌──────────────────────────────────┐
│   BACKEND ENGINE    │   │       INTERACTION CORE           │
│   Person 1          │   │       Person 3                   │
│   FastAPI :8000     │   │       Next.js :3000              │
│   Agents + Cache    │   │       Three.js · Vision · UI     │
└─────────────────────┘   └────────────┬─────────────────────┘
                                       │
                          SSE consume + WebSocket forward
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │   TELEMETRY ENGINE        │
                          │   Person 2                │
                          │   FastAPI :8002           │
                          │   SAR Physics + Monitor   │
                          └──────────────────────────┘
```

**Critical data flow to understand:**
```
P2 simulator → SSE stream → P3 frontend → Three.js voxels
                                        ↘ WebSocket forward → P2 SAR monitor → Flash → alert back to P3
```

P3 consumes the SSE stream AND forwards each point to the WebSocket monitor. Both happen in the same SSE handler.

---

## ⚠️ Shared Contracts — Implement These Before Anything Else

### REST API (Person 1 → Person 3) — Port :8000

```typescript
// POST /api/projects
Request:  { device_name: string, bom_text: string, target_regions: string[] }
Response: { project_id: string, status: "created" }

// POST /api/projects/:id/scope
Request:  { scan_summary?: ScanSummary }  // optional — pass when scan is complete
Response: { project_id: string, status: "scoping" }

// GET /api/projects/:id/events   ← SSE stream
// GET /api/projects/:id/report
Response: { pdf_base64: string, summary: string }

type ScanSummary = {
  peak_sar: number
  anomaly_count: number
  total_points: number
  anomalies: Array<{ position: [number,number,number], sar: number }>
}
```

### SAR Telemetry Stream (Person 2 → Person 3) — Port :8002

```typescript
// POST /api/simulator/start
Request:  { antenna_x: number, antenna_y: number, frequency_mhz: number, power_dbm: number }
Response: { status: "streaming" }

// GET /api/simulator/stream   ← SSE, streams SARPoint objects

// WebSocket /sar-monitor
// Client (P3 frontend) sends:  SARPoint
// Server (P2 Flash agent) sends: SARMonitorMessage

type SARPoint = {
  x: number; y: number; z: number
  frequency_mhz: number; power_dbm: number
  sar_w_kg: number; is_anomaly: boolean; pct_of_limit: number
}

type SARMonitorMessage =
  | { type: "ok";       sar: number; pct_of_limit: number }
  | { type: "warning";  message: string; sar: number; trend: "rising"|"stable"|"falling" }
  | { type: "critical"; message: string; recommendation: string }
```

### SSE Event Schema (Person 1 → Person 3)

```typescript
type SSEEvent =
  | { event: "agent_start";      data: { agent: AgentName; message: string } }
  | { event: "agent_complete";   data: { agent: AgentName; output: string } }
  | { event: "anomaly_detected"; data: Anomaly }
  | { event: "phase_complete";   data: { phase: PhaseName; summary: string } }
  | { event: "report_ready";     data: { download_url: string } }

type AgentName =
  | "intake" | "jurisdiction_fcc" | "jurisdiction_eu" | "jurisdiction_ca"
  | "jurisdiction_jp" | "jurisdiction_br" | "test_plan"
  | "report_setup" | "report_measurement" | "report_citer"
  | "report_narrator" | "report_compliance"

type PhaseName = "intake" | "scoping" | "test_plan" | "report"

type Anomaly = {
  id: string; severity: "warning" | "critical"
  position: [number, number, number]
  sar: number; limit: number
  message: string; recommendation: string
}
```

### Mock Device BOM (use for all dev/demo)

```json
{
  "device_name": "SmartPatch X1",
  "chips": [
    { "model": "Nordic nRF52840", "type": "BLE", "freq_mhz": 2402, "power_dbm": 0 },
    { "model": "Realtek RTL8723DE", "type": "WiFi+BT", "freq_mhz": 2412, "power_dbm": 20 }
  ],
  "form_factor": "wearable",
  "body_worn": true,
  "target_regions": ["US", "EU", "CA"]
}
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11 + FastAPI + uvicorn (async throughout) |
| AI | google-generativeai SDK — Gemini 3.5 Flash |
| Vision | Gemini multimodal (frame-by-frame JPEG, every 1.5s) |
| Frontend | Next.js 14 + Tailwind + TypeScript |
| 3D | Three.js + react-three-fiber |
| Real-time | SSE (both services → frontend), WebSocket (frontend → P2 monitor) |
| Mock | Custom mock-sse.ts script on :8003 |

---

## Repository Structure

```
labpilot/
├── .env.example
├── backend/               ← Person 1
│   ├── requirements.txt
│   ├── main.py
│   ├── orchestrator.py
│   ├── cache_loader.py
│   └── agents/
│       ├── intake.py
│       ├── jurisdiction.py
│       ├── test_plan.py
│       └── report.py
│
├── simulator/             ← Person 2
│   ├── requirements.txt
│   ├── main.py
│   ├── sar_physics.py
│   └── sar_monitor_agent.py
│
└── frontend/              ← Person 3
    ├── package.json
    ├── app/
    │   ├── page.tsx
    │   ├── project/[id]/page.tsx
    │   └── api/verify/route.ts   ← vision verification API route
    ├── components/
    │   ├── Dashboard.tsx          ← split-screen layout
    │   ├── AgentFeed.tsx          ← left panel
    │   ├── SARViewport.tsx        ← center panel (Three.js + monitor wire)
    │   ├── WebcamPanel.tsx        ← right panel (vision + manual override)
    │   └── TelemetryBar.tsx       ← jurisdiction agent status dots
    └── mocks/
        └── mock-sse.ts            ← dev server on :8003
```

---

---

# PERSON 1 — AI Core, Orchestration & Compliance

**You own:** `backend/` on port `:8000`
**You do NOT build:** SAR physics, webcam, Three.js, frontend

### Deliverables
1. Context cache loader — loads regulatory corpus once, all agents share it
2. Managed agent swarm — intake, 5 parallel jurisdiction agents, test plan, 5 parallel report agents
3. SSE broadcaster — streams agent reasoning to frontend left panel
4. Report agent that accepts scan summary data from the frontend

---

### Setup

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn google-generativeai python-dotenv numpy
```

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
CACHE_NAME=            # filled after running cache_loader.py
PORT=8000
```

---

### Step 1 — Run First: Context Cache Loader

Run once at hackathon start. Prints `CACHE_NAME` — add it to `.env`.

```python
# cache_loader.py
import google.generativeai as genai
from google.generativeai import caching
import datetime, os
from dotenv import load_dotenv
load_dotenv()

CORPUS = """
=== FCC PART 15 ===
47 CFR Part 15.247: Operation in 2400-2483.5 MHz band.
47 CFR Part 15.249: Operation in 2400-2483.5 MHz band, lower power.
OET-65: RF human exposure evaluation guidelines.
KDB 447498: SAR measurement procedures for portable devices within 20cm of body.
KDB 616217: RF exposure compliance for mobile and portable devices.
SAR LIMIT (FCC): 1.6 W/kg averaged over 1g tissue. Reference: 47 CFR 2.1093.
FCC ID labeling required under 47 CFR 2.925.

=== EU RADIO EQUIPMENT DIRECTIVE ===
EN 300 328 v2.2.2: WLAN/BT in 2.4 GHz band.
EN 301 489-1/-17: EMC requirements for radio equipment.
EN 62311:2020: Human exposure assessment.
SAR LIMIT (EU): 2.0 W/kg averaged over 10g tissue. CE marking required.
Radio Equipment Directive 2014/53/EU.

=== ISED CANADA ===
RSS-247 Issue 2: Digital transmission in 2.4 GHz and 5 GHz.
RSS-Gen Issue 5: General requirements for radio apparatus.
RSS-102 Issue 6: RF exposure compliance.
SAR LIMIT (CA): 1.6 W/kg over 1g tissue. Same as FCC. ISED certification required.

=== JAPAN MIC ===
ARIB STD-T66: Bluetooth standard for Japan.
MIC Ordinance 88: Technical standards for specified radio equipment.
Giteki mark required for radio devices sold in Japan.

=== BRAZIL ANATEL ===
ANATEL Resolution 715/2019: Homologation of telecommunications products.
SAR LIMIT (BR): 1.6 W/kg over 1g tissue. Homologation number required.
"""

def load_cache():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    cache = caching.CachedContent.create(
        model=os.getenv("GEMINI_MODEL"),
        system_instruction="You are an expert in wireless device RF certification regulations.",
        contents=[CORPUS],
        ttl=datetime.timedelta(hours=8),
        display_name="labpilot_regulatory_corpus"
    )
    print(f"CACHE_NAME={cache.name}")
    return cache.name

if __name__ == "__main__":
    load_cache()
```

---

### Step 2 — FastAPI Main + SSE

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, uuid
from orchestrator import run_project

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

projects: dict[str, dict] = {}
queues:   dict[str, asyncio.Queue] = {}

@app.post("/api/projects")
async def create_project(body: dict):
    pid = str(uuid.uuid4())[:8]
    projects[pid] = {"status": "created", "data": body}
    queues[pid]   = asyncio.Queue()
    return {"project_id": pid, "status": "created"}

@app.post("/api/projects/{pid}/scope")
async def start_scoping(pid: str, body: dict = {}):
    # body may contain scan_summary from the frontend after the scan completes
    data = {**projects[pid]["data"], "scan_summary": body.get("scan_summary")}
    asyncio.create_task(run_project(pid, data, queues[pid]))
    return {"project_id": pid, "status": "scoping"}

@app.get("/api/projects/{pid}/events")
async def event_stream(pid: str):
    async def generate():
        q = queues[pid]
        while True:
            evt = await q.get()
            yield f"event: {evt['event']}\ndata: {json.dumps(evt['data'])}\n\n"
            if evt["event"] == "report_ready":
                break
    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

---

### Step 3 — Orchestrator

```python
# orchestrator.py
import asyncio
import google.generativeai as genai
import os

async def emit(q, event, data):
    await q.put({"event": event, "data": data})

async def run_project(pid: str, data: dict, q: asyncio.Queue):
    model_name = os.getenv("GEMINI_MODEL")
    cache_name = os.getenv("CACHE_NAME")

    # --- INTAKE ---
    await emit(q, "agent_start", {"agent": "intake", "message": "Parsing device BOM..."})
    device_profile = await run_intake(data, model_name)
    await emit(q, "agent_complete", {"agent": "intake", "output": str(device_profile)[:300]})

    # --- 5 PARALLEL JURISDICTION AGENTS ---
    regions = ["fcc", "eu", "ca", "jp", "br"]
    for r in regions:
        await emit(q, "agent_start", {"agent": f"jurisdiction_{r}",
                                       "message": f"Analyzing {r.upper()} requirements..."})

    cert_matrix = await run_jurisdiction_parallel(device_profile, model_name, cache_name)
    for r in regions:
        await emit(q, "agent_complete", {"agent": f"jurisdiction_{r}",
                                          "output": cert_matrix.get(r, "")[:200]})
    await emit(q, "phase_complete", {"phase": "scoping",
                                      "summary": "5 jurisdictions analyzed"})

    # --- TEST PLAN ---
    await emit(q, "agent_start", {"agent": "test_plan",
                                   "message": "Drafting test plan with regulatory citations..."})
    test_plan = await run_test_plan(device_profile, cert_matrix, model_name, cache_name)
    await emit(q, "agent_complete", {"agent": "test_plan", "output": test_plan[:300]})
    await emit(q, "phase_complete", {"phase": "test_plan", "summary": "Test plan complete"})

    # --- 5 PARALLEL REPORT AGENTS (include scan summary if available) ---
    scan_summary = data.get("scan_summary")
    report_agents = ["report_setup", "report_measurement", "report_citer",
                     "report_narrator", "report_compliance"]
    for ra in report_agents:
        await emit(q, "agent_start", {"agent": ra,
                                       "message": f"Composing {ra.replace('report_', '')} section..."})

    await run_report_parallel(test_plan, device_profile, scan_summary,
                               model_name, cache_name, q)
    await emit(q, "report_ready", {"download_url": f"/api/projects/{pid}/report"})
```

---

### Step 4 — Jurisdiction Agents (parallel, context-cached)

```python
# agents/jurisdiction.py
import asyncio
import google.generativeai as genai
import os

PROMPTS = {
    "fcc": "FCC regulatory expert. Analyze this device. List every required test, exact CFR citation, estimated hours. Device: {profile}",
    "eu":  "EU RED compliance expert. List CE marking requirements, required EN standards, SAR obligations. Device: {profile}",
    "ca":  "ISED Canada expert. List required tests under RSS rules and certification path. Device: {profile}",
    "jp":  "Japan MIC/ARIB expert. List required tests and Giteki certification steps. Device: {profile}",
    "br":  "ANATEL Brazil expert. List homologation requirements under Resolution 715. Device: {profile}",
}

async def run_single(region: str, profile: dict, model_name: str, cache_name: str) -> str:
    model = genai.GenerativeModel(model_name=model_name, cached_content=cache_name)
    prompt = PROMPTS[region].format(profile=str(profile)[:500])
    resp = await asyncio.to_thread(model.generate_content, prompt)
    return resp.text

async def run_jurisdiction_parallel(device_profile: dict,
                                     model_name: str, cache_name: str) -> dict:
    results = await asyncio.gather(
        *[run_single(r, device_profile, model_name, cache_name)
          for r in ["fcc", "eu", "ca", "jp", "br"]]
    )
    return dict(zip(["fcc", "eu", "ca", "jp", "br"], results))
```

---

### Step 5 — Report Agents (include scan data)

```python
# agents/report.py
import asyncio
import google.generativeai as genai

SECTION_PROMPTS = {
    "report_setup":       "Write the test setup section describing equipment, phantom type, and environmental conditions. Test plan: {context}",
    "report_measurement": "Summarize measurement results. Peak SAR: {peak_sar} W/kg. Anomalies: {anomaly_count}. Test plan: {context}",
    "report_citer":       "For each measurement value, cite the exact regulatory paragraph it satisfies. Test plan: {context}",
    "report_narrator":    "Explain any anomalies detected and their resolution. Anomaly data: {anomalies}. Test plan: {context}",
    "report_compliance":  "Draft the executive compliance statement. Peak SAR: {peak_sar} W/kg vs FCC limit 1.6 W/kg. Pass/fail per jurisdiction. Test plan: {context}",
}

async def run_report_parallel(test_plan: str, device_profile: dict,
                               scan_summary: dict, model_name: str,
                               cache_name: str, queue) -> dict:
    peak_sar      = scan_summary.get("peak_sar", "N/A") if scan_summary else "N/A"
    anomaly_count = scan_summary.get("anomaly_count", 0) if scan_summary else 0
    anomalies     = scan_summary.get("anomalies", []) if scan_summary else []
    context       = test_plan[:1500]

    async def run_section(name: str, prompt_template: str) -> tuple[str, str]:
        model = genai.GenerativeModel(model_name=model_name, cached_content=cache_name)
        prompt = prompt_template.format(
            context=context, peak_sar=peak_sar,
            anomaly_count=anomaly_count, anomalies=str(anomalies)
        )
        resp = await asyncio.to_thread(model.generate_content, prompt)
        await queue.put({"event": "agent_complete",
                         "data": {"agent": name, "output": "Section complete"}})
        return name, resp.text

    results = await asyncio.gather(
        *[run_section(k, v) for k, v in SECTION_PROMPTS.items()]
    )
    return dict(results)
```

---

### Person 1 — Coding Agent Directive

```
Build a FastAPI server on port 8000 using the google-generativeai SDK.

Endpoints:
- POST /api/projects: creates project, returns {project_id, status}
- POST /api/projects/:id/scope: accepts optional body {scan_summary: {peak_sar, anomaly_count, anomalies}}
  starts async orchestration pipeline
- GET /api/projects/:id/events: SSE stream of agent events
- GET /api/projects/:id/report: returns {pdf_base64, summary}

Pipeline runs in sequence:
1. intake agent: parses BOM text into structured device profile
2. 5 parallel jurisdiction agents (fcc, eu, ca, jp, br): use Context Cache (CACHE_NAME env var)
   containing full regulatory corpus. Each returns required tests + citations.
3. test_plan agent: drafts test plan from certification matrix
4. 5 parallel report agents (setup, measurement, citer, narrator, compliance):
   include peak_sar and anomalies from scan_summary if provided

SSE event schema:
{ event: "agent_start"|"agent_complete"|"phase_complete"|"report_ready", data: {...} }

Use asyncio.Queue per project. Use asyncio.gather for all parallel calls.
CORS allow all origins.
```

---

### Person 1 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Setup, run cache_loader.py, confirm CACHE_NAME in .env |
| 0:30–1:30 | main.py + SSE endpoint running with mock queue |
| 1:30–2:30 | Intake + 5 jurisdiction agents returning real output |
| 2:30–3:30 | Test plan agent working end-to-end |
| 3:30–4:30 | 5 parallel report agents, scan_summary flowing into compliance section |
| 4:30–5:30 | Full pipeline test: mock BOM in → report_ready out via SSE |
| 5:30–6:30 | Error handling, edge cases, demo rehearsal |

---

---

# PERSON 2 — Telemetry Engine & SAR Monitor

**You own:** `simulator/` on port `:8002`
**You do NOT build:** Gemini agents, frontend, Three.js

### Deliverables
1. SAR physics generator streaming volumetric measurements over SSE
2. Guaranteed anomaly injection at (8.2, 4.4, 3.0) — the demo climax
3. SAR monitor WebSocket — Flash watches the live stream and fires interventions

> Note: R&S XML script compiler is **cut from must-have**. Add only if time permits after all must-haves are done.

---

### Setup

```bash
cd simulator
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn google-generativeai python-dotenv numpy
```

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
PORT=8002
```

---

### Step 1 — SAR Physics Engine

```python
# sar_physics.py
import numpy as np
import asyncio

SAR_LIMIT_FCC = 1.6

def compute_sar(x: float, y: float, z: float,
                antenna_pos: tuple, freq_mhz: float, power_dbm: float) -> float:
    ax, ay, az = antenna_pos
    r = max(np.sqrt((x-ax)**2 + (y-ay)**2 + (z-az)**2), 0.5)
    power_mw = 10 ** (power_dbm / 10)
    freq_factor = freq_mhz / 2400
    tissue_conductivity = 1.8
    sar = (power_mw * 0.001 * freq_factor * tissue_conductivity) / (2 * np.pi * r**2)
    return round(float(sar) * float(np.random.normal(1.0, 0.03)), 4)

async def stream_sar_grid(params: dict, queue: asyncio.Queue):
    antenna_pos = (params.get("antenna_x", 0), params.get("antenna_y", 1.5), 0)
    freq = params.get("frequency_mhz", 2412)
    power = params.get("power_dbm", 20)

    xs = np.arange(-8, 8.1, 0.5)
    ys = np.arange(-10, 10.1, 0.5)
    zs = np.arange(0, 5.1, 1.0)

    for xi in xs:
        for yi in ys:
            for zi in zs:
                sar = compute_sar(xi, yi, zi, antenna_pos, freq, power)

                # Planted anomaly — guaranteed demo climax
                if abs(xi - 8.2) < 1.0 and abs(yi - 4.4) < 1.0 and abs(zi - 3.0) < 1.0:
                    sar = round(float(np.random.uniform(1.49, 1.58)), 4)

                pct = round(sar / SAR_LIMIT_FCC, 4)
                point = {
                    "x": round(float(xi), 2),
                    "y": round(float(yi), 2),
                    "z": round(float(zi), 2),
                    "frequency_mhz": freq,
                    "power_dbm": power,
                    "sar_w_kg": sar,
                    "is_anomaly": pct > 0.90,
                    "pct_of_limit": pct
                }
                await queue.put(point)
                await asyncio.sleep(0.012)  # ~83 points/sec
```

---

### Step 2 — FastAPI Simulator Service

```python
# main.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json
from sar_physics import stream_sar_grid
from sar_monitor_agent import handle_sar_monitor

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

sim_queue: asyncio.Queue = asyncio.Queue()

@app.post("/api/simulator/start")
async def start_sim(body: dict):
    asyncio.create_task(stream_sar_grid(body, sim_queue))
    return {"status": "streaming"}

@app.get("/api/simulator/stream")
async def sim_stream():
    async def generate():
        while True:
            point = await sim_queue.get()
            yield f"data: {json.dumps(point)}\n\n"
    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.websocket("/sar-monitor")
async def sar_monitor_ws(ws: WebSocket):
    await ws.accept()
    await handle_sar_monitor(ws)
```

---

### Step 3 — SAR Monitor Agent

Flash watches a rolling window of SAR points. Fires warning or critical alerts.

```python
# sar_monitor_agent.py
import google.generativeai as genai
import os, json
from fastapi import WebSocket
from collections import deque

MONITOR_PROMPT = """
You are a real-time SAR safety monitor for RF certification testing.
FCC limit: 1.6 W/kg (1g tissue). Critical threshold: 90% = 1.44 W/kg.

Recent SAR readings:
{readings}

Analyze trend. Respond ONLY in JSON, no markdown:
{{
  "status": "ok" | "warning" | "critical",
  "trend": "rising" | "stable" | "falling",
  "message": "one sentence",
  "recommendation": "one action sentence"
}}

Flag warning if: 3+ consecutive readings rising AND latest > 1.2 W/kg.
Flag critical if: any reading > 1.44 W/kg.
"""

async def handle_sar_monitor(ws: WebSocket):
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL"))
    window = deque(maxlen=8)
    call_count = 0

    try:
        while True:
            point = await ws.receive_json()
            window.append(point)
            call_count += 1

            # Invoke Flash every 5 points to manage rate limits
            if call_count % 5 != 0:
                await ws.send_json({"type": "ok",
                                    "sar": point["sar_w_kg"],
                                    "pct_of_limit": point["pct_of_limit"]})
                continue

            prompt = MONITOR_PROMPT.format(readings=json.dumps(list(window), indent=2))
            response = model.generate_content(prompt)
            text = response.text.strip().strip("```json").strip("```").strip()
            result = json.loads(text)

            if result["status"] == "ok":
                await ws.send_json({"type": "ok",
                                    "sar": point["sar_w_kg"],
                                    "pct_of_limit": point["pct_of_limit"]})
            elif result["status"] == "warning":
                await ws.send_json({"type": "warning",
                                    "message": result["message"],
                                    "sar": point["sar_w_kg"],
                                    "trend": result["trend"]})
            else:
                await ws.send_json({"type": "critical",
                                    "message": result["message"],
                                    "recommendation": result["recommendation"]})

    except Exception as e:
        print(f"SAR monitor error: {e}")
```

---

### Person 2 — Coding Agent Directive

```
Create a FastAPI service on port 8002 with CORS enabled for all origins.

Endpoints:
1. POST /api/simulator/start — body: {antenna_x, antenna_y, frequency_mhz, power_dbm}
   Returns {status: "streaming"}. Starts async SAR grid sweep.

2. GET /api/simulator/stream — SSE stream, each event is a JSON SARPoint:
   {x, y, z, frequency_mhz, power_dbm, sar_w_kg, is_anomaly, pct_of_limit}

3. WebSocket /sar-monitor — receives SARPoint JSON from frontend, responds with:
   {type: "ok"|"warning"|"critical", message?, recommendation?, trend?}

SAR physics:
  r = max(sqrt((x-ax)^2 + (y-ay)^2 + (z-az)^2), 0.5)
  power_mw = 10^(power_dbm/10)
  sar = (power_mw * 0.001 * (freq_mhz/2400) * 1.8) / (2 * pi * r^2) * normal(1.0, 0.03)

Grid: X[-8 to 8 step 0.5], Y[-10 to 10 step 0.5], Z[0 to 5 step 1.0]
Anomaly override: if distance from (8.2, 4.4, 3.0) < 1.0, set sar = uniform(1.49, 1.58)
Sleep 12ms between points.

SAR monitor: use rolling window of 8 points. Call Gemini every 5 points.
Prompt Gemini for "ok", "warning", or "critical" status with trend analysis.
```

---

### Person 2 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Setup, verify physics formula produces 0.1–1.5 W/kg range |
| 0:30–1:30 | SSE endpoint streaming grid points, anomaly injection verified |
| 1:30–2:30 | SAR monitor WebSocket receiving points, Gemini responding |
| 2:30–3:30 | Full end-to-end: start → stream → monitor alert on anomaly |
| 3:30–4:30 | Integration test with Person 3 consuming SSE |
| 4:30–6:30 | Polish, rate limit handling, reconnect logic |

**Test without frontend:**
```bash
# Test SSE stream
curl -N http://localhost:8002/api/simulator/stream

# Test monitor WebSocket
wscat -c ws://localhost:8002/sar-monitor
> {"x":8.2,"y":4.4,"z":3.0,"frequency_mhz":2412,"power_dbm":20,"sar_w_kg":1.54,"is_anomaly":true,"pct_of_limit":0.963}
```

---

---

# PERSON 3 — Interaction Core, 3D Viewport & Vision Check

**You own:** `frontend/` on port `:3000`
**You do NOT build:** Python backends, SAR physics, Gemini agent calls

**First 30 minutes:** Fire all four coding agent prompts into Claude Code simultaneously. Let them generate. Then integrate.

---

### Setup

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app
npm install three @react-three/fiber @react-three/drei
```

```env
# .env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8003    # mock during dev
NEXT_PUBLIC_SIMULATOR_URL=http://localhost:8002
# Flip to real when Person 1 is ready:
# NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

### Coding Agent Prompt 1 — Articulated Robot Arm

```
Create RobotArm.tsx using react-three-fiber.

Build a 3-joint arm with nested Group hierarchies:
- baseGroup: fixed at (11, 13, 11). Add SphereGeometry r=0.7, color #667788.
  - shoulderGroup: rotates on Y axis for azimuth
    - upperArm: CylinderGeometry(0.15, 0.15, 8) along Y axis
    - SphereGeometry joint r=0.5 at end of upper arm
    - elbowGroup: rotates on Z axis for elevation
      - forearm: CylinderGeometry(0.12, 0.12, 6) along Y axis
      - SphereGeometry joint r=0.35 at end of forearm
      - probe: CylinderGeometry(0.08, 0.08, 4) with yellow SphereGeometry tip r=0.38

All meshes: MeshPhongMaterial color #667788 except tip (yellow, emissive).

Write updateArm(tx, ty, tz) using closed-form IK:
1. azimuth = atan2(tx - 11, tz - 11) → shoulderGroup.rotation.y
2. 2-link planar IK (l1=8, l2=6) using law of cosines for elevation
3. Smooth with lerp(current, target, 0.12) per frame

Export updateArm via useImperativeHandle so parent can call it.
Accept prop: anomaly: boolean — when true, make tip pulse red using sin(Date.now()*0.007).
```

---

### Coding Agent Prompt 2 — Instanced Voxel Heatmap

```
Create VoxelCloud.tsx using react-three-fiber.

InstancedMesh: BoxGeometry(0.62, 0.62, 0.62), MeshBasicMaterial vertexColors transparent.
Pre-initialize 2000 instances at scale 0.001 (invisible).

Accept props:
- onPointAdded: (point: SARPoint) => void  // called after adding each voxel
- ref for reset() method

When addPoint(SARPoint) is called:
1. Reveal next instance at position (x, y, z) with scale 1
2. Color by pct_of_limit:
   < 0.40: #1044bb  (safe, blue)
   < 0.65: #1a9980  (moderate, teal)
   < 0.82: #f09510  (caution, amber)
   < 0.92: #e03010  (warning, red-orange)
   >= 0.92: #ff1020  (critical, crimson)
3. needsUpdate = true on instanceMatrix and instanceColor

Anomaly voxels (is_anomaly: true): pulse scale between 0.78–1.2 using sin(Date.now()*0.007).
Export addPoint and reset via useImperativeHandle.
```

---

### Coding Agent Prompt 3 — SAR Viewport (Three.js scene + monitor wire)

```
Create SARViewport.tsx. This component owns the Three.js scene AND
the WebSocket connection to the SAR monitor. Both are wired here.

Three.js scene contents:
- Semi-transparent phantom box: BoxGeometry(15, 22, 8), opacity 0.07, blue, DoubleSide
- Gantry wireframe: EdgesGeometry on BoxGeometry(22, 27, 20), opacity 0.28
- Small dark device box on phantom front face at z=4.25
- RobotArm component (from Prompt 1)
- VoxelCloud component (from Prompt 2)
- Slow orbiting camera using useFrame

WebSocket monitor wire:
const monitor = useRef<WebSocket | null>(null);

useEffect(() => {
  monitor.current = new WebSocket(`${process.env.NEXT_PUBLIC_SIMULATOR_URL}/sar-monitor`);
  monitor.current.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "critical") showCriticalAlert(msg.message, msg.recommendation);
    if (msg.type === "warning")  showWarningBanner(msg.message);
  };
  return () => monitor.current?.close();
}, []);

SSE consumer — when scan is active, consume SSE and handle EACH point by doing BOTH:
1. voxelCloudRef.current?.addPoint(point)   // update Three.js
2. monitor.current?.send(JSON.stringify(point))  // forward to Flash monitor

Track scan summary in a ref:
const scanSummary = useRef({ peak_sar: 0, anomaly_count: 0, total_points: 0, anomalies: [] });

Update it on each anomaly point. Expose getScanSummary() via useImperativeHandle
so the parent Dashboard can read it before triggering the report.

Show stats bar below canvas: current SAR, % of limit, voxel count, peak SAR.
```

---

### Coding Agent Prompt 4 — Dashboard + Webcam Panel

```
Create Dashboard.tsx — the main split-screen control room.

Dark mode (#03030b background). Three columns:

LEFT (25%):
- "Agent stream" header, monospace
- Scrollable SSE event feed from NEXT_PUBLIC_BACKEND_URL/api/projects/:id/events
- Event cards by type:
  agent_start: blue left border, agent name + message
  agent_complete: green left border, output (truncated 120 chars)
  anomaly_detected: red left border, pulsing animation
  phase_complete: purple left border
  report_ready: emerald left border + download button
- Auto-scrolls to bottom

CENTER (55%):
- "Digital twin — SAR scan" header
- SARViewport component fills this area
- "Initialize scan" button — disabled by default, enabled when setupVerified state is true
- On click: POST /api/simulator/start, start consuming SSE from /api/simulator/stream
- "Generate report" button appears after scan completes:
  On click: read getScanSummary() from SARViewport ref, POST to backend /api/projects/:id/scope
  with body {scan_summary: {...}}

RIGHT (20%):
- "Setup verification" header
- WebcamPanel component (see below)
- Jurisdiction status dots below webcam:
  5 rows (FCC, EU, CA, JP, BR), each: colored dot + label
  gray=idle, animated-spin=active, green=complete
  Updates based on SSE agent events

---

Also create WebcamPanel.tsx:

1. navigator.mediaDevices.getUserMedia({ video: true }) — start webcam
2. Show live video feed
3. Status badge: "Analyzing..." | "Setup valid ✓" | "Issues found"
4. Every 1500ms: capture frame to hidden canvas (320x240), extract base64 JPEG,
   POST to /api/verify with { frame: base64 }
5. Display issue cards with severity colors and fix text
6. When valid is true: set parent setupVerified = true (via prop callback)

IMPORTANT — Add manual override button below video:
  <button onClick={() => onSetupVerified(true)} style="opacity:0.5; font-size:11px">
    Skip verification (demo override)
  </button>

Also create app/api/verify/route.ts (Next.js API route):
  POST — accepts { frame: string (base64 JPEG) }
  Calls Gemini 3.5 Flash with frame + this prompt:
  ---
  You are verifying an RF probe positioning setup.
  Objects in frame:
  - Phone = the device under test (DUT)
  - Pen = the RF probe

  Requirements:
  1. Phone is lying flat, screen visible
  2. Pen tip is within 3cm of the phone surface
  3. Pen is approximately perpendicular to phone face (90 degrees +/- 5 degrees)
  4. No large metallic objects directly touching the phone

  Respond ONLY in this JSON, no markdown or code blocks:
  {
    "valid": true or false,
    "issues": [{"description": "text", "severity": "warning or error", "fix": "exact instruction"}],
    "message": "one-line summary"
  }
  ---
  Returns the parsed JSON. Handle parse errors gracefully (return {valid: false, issues: [], message: "Parse error"}).
```

---

### Mock SSE Server (dev — no backend needed)

```typescript
// mocks/mock-sse.ts — run with: npx ts-node mocks/mock-sse.ts
import { createServer } from "http";

const EVENTS = [
  { event: "agent_start",    data: { agent: "intake", message: "Parsing BOM..." }, delay: 400 },
  { event: "agent_complete", data: { agent: "intake", output: "nRF52840 BLE + RTL8723DE WiFi. Body-worn: true." }, delay: 1200 },
  { event: "agent_start",    data: { agent: "jurisdiction_fcc", message: "Analyzing FCC Part 15..." }, delay: 1400 },
  { event: "agent_start",    data: { agent: "jurisdiction_eu",  message: "Analyzing EU RED..." }, delay: 1400 },
  { event: "agent_start",    data: { agent: "jurisdiction_ca",  message: "Analyzing ISED Canada..." }, delay: 1400 },
  { event: "agent_complete", data: { agent: "jurisdiction_fcc", output: "Requires: Part 15.247, SAR per KDB 447498. Est: 40 robot hours." }, delay: 3200 },
  { event: "agent_complete", data: { agent: "jurisdiction_eu",  output: "Requires: EN 300 328, EN 62311 SAR (2.0 W/kg). CE marking." }, delay: 3400 },
  { event: "agent_complete", data: { agent: "jurisdiction_ca",  output: "Requires: ISED RSS-247, RSS-102 SAR (1.6 W/kg)." }, delay: 3600 },
  { event: "phase_complete", data: { phase: "scoping", summary: "5 jurisdictions. 14 tests required. ~3 weeks lab time." }, delay: 4200 },
  { event: "agent_start",    data: { agent: "test_plan", message: "Drafting test plan with citations..." }, delay: 4800 },
  { event: "agent_complete", data: { agent: "test_plan", output: "14 configurations, 6 frequency bands, 4 SAR positions." }, delay: 7500 },
  { event: "anomaly_detected", data: {
      id: "a1", severity: "critical",
      position: [8.2, 4.4, 3.0], sar: 1.54, limit: 1.6,
      message: "SAR 1.54 W/kg — 96% of FCC limit. Growth trajectory indicates breach within 4 steps.",
      recommendation: "Pause test matrices. Review device antenna orientation."
    }, delay: 11000 },
  { event: "report_ready", data: { download_url: "/mock-report.pdf" }, delay: 17000 },
];

createServer((req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.url?.includes("/events")) {
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    EVENTS.forEach(({ event, data, delay }) =>
      setTimeout(() => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`), delay)
    );
  } else {
    res.writeHead(404); res.end();
  }
}).listen(8003, () => console.log("Mock SSE :8003 — set NEXT_PUBLIC_BACKEND_URL=http://localhost:8003"));
```

---

### Person 3 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Fire all 4 coding agent prompts simultaneously into Claude Code |
| 0:30–1:30 | Assemble generated components. Mock SSE running on :8003. All three panels visible. |
| 1:30–2:30 | ACT 1: Webcam live with phone + pen on desk. Manual override working. Green state fires. |
| 2:30–3:30 | ACT 2: Connect to Person 2 simulator SSE. Robot arm tracking. Voxel cloud building. |
| 3:30–4:00 | Wire SAR monitor: confirm frontend forwards points to WebSocket, alerts come back. |
| 4:00–4:30 | Connect Person 1 SSE. Left panel showing real agent events. |
| 4:30–5:30 | Full flow: webcam → green → scan → anomaly alert → report trigger. |
| 5:30–6:30 | Polish, timing, anomaly pulse, demo rehearsal x2. |

---

---

## Integration Checkpoints

| Time | Who | Verify |
|---|---|---|
| T+1:30h | P1 + P3 | P1 SSE endpoint streaming. P3 agent feed shows mock events from P1 real server. |
| T+3:00h | P2 + P3 | P2 simulator SSE streaming. P3 voxel cloud building. Robot arm moving. |
| T+3:30h | P2 + P3 | P3 forwarding SAR points to P2 WebSocket. Alerts returning to frontend. |
| T+4:30h | All | Scan summary flows from P3 into P1 report agent. Report includes peak SAR. |
| T+6:00h | All | Full rehearsal. 3-minute run-through. Every state transition works. |

---

## Google AI Studio Feature Map

| Feature | Owner | Purpose |
|---|---|---|
| Gemini 3.5 Flash | P1, P2 | All agent intelligence and SAR monitoring |
| Managed Agents API | P1 | Persistent project state, sub-agent orchestration |
| Context Caching | P1 | Regulatory corpus cached once, shared by all 5 jurisdiction + 5 report agents |
| Multimodal vision | P3 (via API route) | Frame-by-frame webcam setup verification |
| Code Execution | P1 | Report chart generation |
| Search Grounding | P1 | Live regulatory update awareness |
| Parallel function calling | P1 | 5 jurisdiction agents simultaneously, 5 report agents simultaneously |

---

## Environment Variables

```env
# .env — shared reference, each service copies what it needs

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
CACHE_NAME=              # Person 1 fills after running cache_loader.py

# Ports
BACKEND_PORT=8000
SIMULATOR_PORT=8002

# Frontend
NEXT_PUBLIC_BACKEND_URL=http://localhost:8003   # mock — flip to :8000 when P1 ready
NEXT_PUBLIC_SIMULATOR_URL=http://localhost:8002
```

---

## Quick Start

```bash
# Terminal 1 — Person 1
cd backend && source venv/bin/activate
python cache_loader.py      # ONCE — copy CACHE_NAME to .env
uvicorn main:app --reload --port 8000

# Terminal 2 — Person 2
cd simulator && source venv/bin/activate
uvicorn main:app --reload --port 8002

# Terminal 3 — Person 3
cd frontend
npx ts-node mocks/mock-sse.ts &   # mock backend during dev
npm run dev                        # http://localhost:3000
```

---

## Demo Script — 3 Minutes

**[0:00–0:20]**
*"Every wireless device must pass RF certification before it ships. The engineering work takes 2 weeks and costs $50,000. This is LabPilot."*

Paste mock BOM. Submit. Five jurisdiction agents fire simultaneously in the left panel.

**[0:20–0:50]** *(Act 1)*
*"Before any scan can run, the physical setup must be verified."*

Show webcam panel. Phone and pen on desk. Deliberately tilt the pen. Flash: *"Pen not perpendicular — rotate 8° clockwise."* Correct it. Green badge. *(Manual override visible but not needed.)*

**[0:50–2:10]** *(Act 2)*
*"Flash doesn't wait for the test to finish. It watches the data stream in real time."*

Click Initialize Scan. Robot arm moves. Voxel cloud builds. Blue → amber as heatmap fills. Anomaly cluster hits at (8.2, 4.4, 3.0). Red pulse. Critical alert fires: *"SAR 1.54 W/kg — 96% of FCC limit. Recommend pause."*

**[2:10–3:00]**
*"Five agents simultaneously draft the compliance report — including the measured peak SAR and anomaly data from the scan."*

Click Generate Report. Five report agents light up in the left panel at once. Report ready. *"200-page TCB-ready document. What used to take 2 days."*
