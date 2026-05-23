# LabPilot — Final Architectural Plan
### Google I/O Hackathon · Gemini 3.5 Flash · 6.5-Hour Sprint

---

## What We're Building

LabPilot automates the engineering intelligence layer of RF/wireless certification testing — from client email intake to TCB-ready compliance report — using Gemini 3.5 Flash managed agents, real-time video verification via the Live API, and a physics-based SAR simulation with a 3D digital twin.

**Two-act demo structure:**
- **Act 1 — Setup Verification:** Gemini Flash watches the physical desk via webcam, verifies the device and probe are correctly positioned, and clears the test to begin.
- **Act 2 — Digital Twin Scan:** A 3D robot arm sweeps a volumetric SAR grid inside a virtual phantom body. Flash monitors the live data stream and flags anomalies in real time.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       GOOGLE AI STUDIO                           │
│  Gemini 3.5 Flash · Managed Agents · Live API · Context Cache   │
│  Code Execution · File API · Search Grounding                    │
└───────────────┬─────────────────────┬───────────────────────────┘
                │                     │
         REST/SSE :8000          Live API stream
                │                     │
                ▼                     ▼
┌──────────────────────┐   ┌──────────────────────────────────────┐
│   BACKEND ENGINE     │   │         INTERACTION CORE             │
│   Person 1           │   │         Person 3                     │
│   FastAPI :8000      │   │         Next.js :3000                │
│   Agents + Cache     │   │         Three.js · Webcam · UI       │
└──────────────────────┘   └──────────────┬───────────────────────┘
                                          │ WebSocket control
                                          ▼
                           ┌──────────────────────────┐
                           │   TELEMETRY ENGINE        │
                           │   Person 2                │
                           │   FastAPI :8002           │
                           │   SAR Physics + Scripts   │
                           └──────────────────────────┘
```

---

## ⚠️ Shared Contracts — Read Before Writing Any Code

**These are law. All three implement against them before writing anything else.**

### REST API (Person 1 → Person 3) — Port :8000

```typescript
// POST /api/projects
Request:  { device_name: string, bom_text: string, target_regions: string[] }
Response: { project_id: string, status: "created" }

// POST /api/projects/:id/scope
Request:  {}
Response: { project_id: string, status: "scoping" }

// GET /api/projects/:id/events   ← SSE stream
// GET /api/projects/:id/report
Response: { pdf_base64: string, summary: string }
```

### SAR Telemetry Stream (Person 2 → Person 3) — Port :8002

```typescript
// POST /api/simulator/start
Request:  { antenna_x: number, antenna_y: number, frequency_mhz: number, power_dbm: number }
Response: { status: "streaming" }

// GET /api/simulator/stream   ← SSE live scan stream

type SARPoint = {
  x: number; y: number; z: number
  frequency_mhz: number; power_dbm: number
  sar_w_kg: number; is_anomaly: boolean; pct_of_limit: number
}
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
  | "jurisdiction_jp" | "jurisdiction_br" | "test_plan" | "script_gen"
  | "report_setup" | "report_measurement" | "report_citer"
  | "report_narrator" | "report_compliance"

type PhaseName = "intake" | "scoping" | "test_plan" | "simulation" | "report"

type Anomaly = {
  id: string; severity: "warning" | "critical"
  position: [number, number, number]
  sar: number; limit: number
  message: string; recommendation: string
}
```

### WebSocket Schema (Person 3 webcam → Person 2 monitor)

```typescript
// ws://localhost:8002/sar-monitor
// Client sends: SARPoint
// Server sends:
type SARMonitorMessage =
  | { type: "ok";       sar: number; pct_of_limit: number }
  | { type: "warning";  message: string; sar: number; trend: "rising"|"stable"|"falling" }
  | { type: "critical"; message: string; recommendation: string }
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
| Backend | Python 3.11 + FastAPI + uvicorn (async) |
| AI | google-generativeai SDK |
| Live API | Gemini Live API (webcam stream) |
| Frontend | Next.js 14 + Tailwind + TypeScript |
| 3D | Three.js / react-three-fiber |
| Real-time | SSE (backend→frontend), WebSocket (monitor) |
| Mock | json-server + custom mock-sse script |

---

## Repository Structure

```
labpilot/
├── .env.example
│
├── backend/                  ← Person 1
│   ├── requirements.txt
│   ├── main.py
│   ├── orchestrator.py
│   ├── cache_loader.py
│   ├── agents/
│   │   ├── intake.py
│   │   ├── jurisdiction.py
│   │   ├── test_plan.py
│   │   ├── script_gen.py
│   │   └── report.py
│   └── prompts/
│       ├── intake.txt
│       ├── jurisdiction_fcc.txt
│       ├── jurisdiction_eu.txt
│       ├── test_plan.txt
│       └── report_sections.txt
│
├── simulator/                ← Person 2
│   ├── requirements.txt
│   ├── main.py
│   ├── sar_physics.py
│   ├── anomaly_injector.py
│   ├── sar_monitor_agent.py
│   └── script_compiler.py
│
└── frontend/                 ← Person 3
    ├── package.json
    ├── app/
    │   ├── page.tsx
    │   └── project/[id]/page.tsx
    ├── components/
    │   ├── Dashboard.tsx          ← split-screen layout
    │   ├── AgentFeed.tsx          ← left panel: SSE log stream
    │   ├── SARViewport.tsx        ← center panel: Three.js scene
    │   ├── WebcamPanel.tsx        ← right panel: Live API feed
    │   └── TelemetryBar.tsx       ← jurisdiction agent status
    └── mocks/
        ├── mock-sse.ts            ← runs on :8002 during dev
        └── db.json
```

---

---

# PERSON 1 — AI Core, Orchestration & Compliance

**You own:** `backend/` on port `:8000`
**You do NOT build:** SAR physics, webcam, Three.js, frontend

### Deliverables
1. Context cache initializer — loads full regulatory corpus once, saves token quota
2. Managed agent swarm — intake, 5 parallel jurisdiction agents, test plan, 5 parallel report agents
3. SSE broadcaster — streams agent reasoning to frontend left panel in real time

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
CACHE_NAME=                    # filled after running cache_loader.py
PORT=8000
```

---

### Step 1 — Run This First: Context Cache Loader

Run once at hackathon start. Saves the entire regulatory corpus as a cached context.
The cache name it prints goes into your `.env` as `CACHE_NAME`.

```python
# cache_loader.py
import google.generativeai as genai
from google.generativeai import caching
import datetime, os
from dotenv import load_dotenv
load_dotenv()

REGULATORY_CORPUS = """
=== FCC PART 15 ===
47 CFR Part 15.247: Operation in the bands 902-928 MHz, 2400-2483.5 MHz, 5725-5850 MHz.
47 CFR Part 15.249: Operation within the bands 902-928 MHz, 2400-2483.5 MHz, 5725-5875 MHz.
OET-65: Evaluating Compliance with FCC Guidelines for Human Exposure to Radiofrequency Fields.
KDB 447498: SAR measurement procedures for portable devices used within 20cm of the body.
KDB 616217: RF exposure compliance for mobile and portable devices.
KDB 648474: Guidance for evaluation of SAR in portable devices.
SAR LIMIT (FCC): 1.6 W/kg averaged over 1g tissue for portable devices (47 CFR 2.1093).
FCC ID labeling: Required under 47 CFR 2.925 for all intentional radiators.

=== EU RADIO EQUIPMENT DIRECTIVE ===
EN 300 328 v2.2.2: WLAN/BT equipment operating in the 2.4 GHz band.
EN 301 489-1: Common EMC requirements for radio equipment.
EN 301 489-17: Specific EMC requirements for broadband data transmission.
EN 62311:2020: Assessment of electronic equipment related to human exposure restrictions.
SAR LIMIT (EU): 2.0 W/kg averaged over 10g tissue. CE marking required.
RTTE Directive 2014/53/EU: Radio Equipment Directive requirements.

=== ISED CANADA ===
RSS-247 Issue 2: Digital transmission systems operating in 2.4 GHz and 5 GHz bands.
RSS-Gen Issue 5: General requirements applicable to all radio apparatus.
RSS-102 Issue 6: RF exposure compliance of radiocommunication apparatus.
SAR LIMIT (CA): 1.6 W/kg averaged over 1g tissue. Same as FCC. ISED certification required.

=== JAPAN MIC ===
ARIB STD-T66: Bluetooth standards for Japan.
MIC Ordinance 88: Technical standards for specified radio equipment.
Japan certification: Giteki mark required for radio devices sold in Japan.

=== BRAZIL ANATEL ===
ANATEL Resolution 715/2019: Homologation of telecommunications products.
SAR LIMIT (BR): 1.6 W/kg averaged over 1g tissue. Homologation number required on device.
"""

def load_cache():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    cache = caching.CachedContent.create(
        model=os.getenv("GEMINI_MODEL"),
        system_instruction="You are a regulatory expert for wireless device RF certification.",
        contents=[REGULATORY_CORPUS],
        ttl=datetime.timedelta(hours=8),
        display_name="labpilot_regulatory_corpus"
    )
    print(f"Cache created: {cache.name}")
    print(f"Add to .env: CACHE_NAME={cache.name}")
    return cache.name

if __name__ == "__main__":
    load_cache()
```

---

### Step 2 — FastAPI Main + SSE Endpoint

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, uuid
from orchestrator import run_project

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

projects: dict[str, dict] = {}
event_queues: dict[str, asyncio.Queue] = {}

@app.post("/api/projects")
async def create_project(body: dict):
    pid = str(uuid.uuid4())[:8]
    projects[pid] = {"status": "created", "data": body}
    event_queues[pid] = asyncio.Queue()
    return {"project_id": pid, "status": "created"}

@app.post("/api/projects/{pid}/scope")
async def start_scoping(pid: str):
    asyncio.create_task(run_project(pid, projects[pid]["data"], event_queues[pid]))
    return {"project_id": pid, "status": "scoping"}

@app.get("/api/projects/{pid}/events")
async def event_stream(pid: str):
    async def generate():
        q = event_queues[pid]
        while True:
            event = await q.get()
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["event"] == "report_ready":
                break
    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

---

### Step 3 — Orchestrator

```python
# orchestrator.py
import asyncio
import google.generativeai as genai
import os
from agents.intake import run_intake
from agents.jurisdiction import run_jurisdiction_parallel
from agents.test_plan import run_test_plan
from agents.report import run_report

async def emit(queue, event, data):
    await queue.put({"event": event, "data": data})

async def run_project(pid: str, data: dict, queue: asyncio.Queue):
    await emit(queue, "agent_start", {"agent": "intake", "message": "Parsing BOM and device specification..."})
    device_profile = await run_intake(data)
    await emit(queue, "agent_complete", {"agent": "intake", "output": str(device_profile)[:300]})

    regions = ["fcc", "eu", "ca", "jp", "br"]
    for r in regions:
        await emit(queue, "agent_start", {"agent": f"jurisdiction_{r}", "message": f"Analyzing {r.upper()} requirements..."})

    cert_matrix = await run_jurisdiction_parallel(device_profile)

    for r in regions:
        await emit(queue, "agent_complete", {"agent": f"jurisdiction_{r}", "output": cert_matrix.get(r, "")[:200]})
    await emit(queue, "phase_complete", {"phase": "scoping", "summary": f"5 jurisdictions analyzed"})

    await emit(queue, "agent_start", {"agent": "test_plan", "message": "Drafting 30-page test plan..."})
    test_plan = await run_test_plan(device_profile, cert_matrix)
    await emit(queue, "agent_complete", {"agent": "test_plan", "output": test_plan[:300]})
    await emit(queue, "phase_complete", {"phase": "test_plan", "summary": "Test plan complete"})

    report_agents = ["report_setup", "report_measurement", "report_citer", "report_narrator", "report_compliance"]
    for ra in report_agents:
        await emit(queue, "agent_start", {"agent": ra, "message": f"Composing {ra.replace('report_', '')} section..."})

    report = await run_report(test_plan, device_profile)
    for ra in report_agents:
        await emit(queue, "agent_complete", {"agent": ra, "output": "Section complete"})
    await emit(queue, "report_ready", {"download_url": f"/api/projects/{pid}/report"})
```

---

### Step 4 — Jurisdiction Agents (5 parallel, context-cached)

```python
# agents/jurisdiction.py
import asyncio
import google.generativeai as genai
import os

PROMPTS = {
    "fcc": "You are an FCC regulatory expert. Analyze this wireless device and list every required test, exact CFR citation, estimated hours, and equipment needed. Device: {profile}",
    "eu":  "You are an EU RED compliance expert. List CE marking requirements, required EN standards, SAR obligations. Device: {profile}",
    "ca":  "You are an ISED Canada expert. List required tests under RSS rules and certification path. Device: {profile}",
    "jp":  "You are a Japan MIC/ARIB expert. List required tests and Giteki certification steps. Device: {profile}",
    "br":  "You are an ANATEL Brazil expert. List homologation requirements under Resolution 715. Device: {profile}",
}

async def run_single(region: str, profile: dict) -> str:
    model = genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL"),
        cached_content=os.getenv("CACHE_NAME")
    )
    prompt = PROMPTS[region].format(profile=str(profile)[:500])
    resp = await asyncio.to_thread(model.generate_content, prompt)
    return resp.text

async def run_jurisdiction_parallel(device_profile: dict) -> dict:
    results = await asyncio.gather(
        *[run_single(r, device_profile) for r in ["fcc", "eu", "ca", "jp", "br"]]
    )
    return dict(zip(["fcc", "eu", "ca", "jp", "br"], results))
```

---

### Person 1 — Coding Agent Directive

Paste this directly into Claude Code or Cursor:

```
Build a FastAPI server on port 8000 using the google-generativeai SDK.

1. POST /api/projects — creates a project, returns project_id
2. POST /api/projects/:id/scope — starts async orchestration pipeline
3. GET /api/projects/:id/events — SSE stream of agent events

The orchestrator runs these agents in sequence:
- intake agent: parses BOM text into structured device profile
- 5 parallel jurisdiction agents (fcc, eu, ca, jp, br): each uses a pre-loaded
  Context Cache (CACHE_NAME from env) containing the full regulatory corpus
- test_plan agent: drafts test plan from certification matrix
- 5 parallel report agents: setup, measurement, citer, narrator, compliance

Each agent start/complete streams an SSE event matching this schema:
{ event: "agent_start"|"agent_complete"|"phase_complete"|"report_ready", data: {...} }

Use asyncio.Queue per project for event buffering.
Use asyncio.gather for all parallel agent calls.
CORS allow all origins.
```

---

### Person 1 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Setup env, run cache_loader.py, confirm CACHE_NAME |
| 0:30–1:30 | main.py + SSE endpoint running, mock queue emitting events |
| 1:30–2:30 | Intake + jurisdiction parallel agents returning real output |
| 2:30–3:30 | Test plan + script gen agents working |
| 3:30–4:30 | 5 parallel report agents working, full pipeline end-to-end |
| 4:30–5:30 | Full pipeline test with mock BOM, SSE events verified |
| 5:30–6:30 | Edge cases, error handling, demo run |

---

---

# PERSON 2 — Telemetry Engine, SAR Physics & Instrument Scripts

**You own:** `simulator/` on port `:8002`
**You do NOT build:** Gemini agents, frontend, Three.js

### Deliverables
1. Async SAR physics generator — streams 3D volumetric measurements over SSE
2. Planted anomaly injector — guarantees the demo climax fires
3. Real-time SAR monitor agent — Flash watches the live stream and intervenes
4. Instrument script compiler — generates valid R&S EMCvu XML from test plan

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

                # Planted anomaly cluster — guaranteed demo moment
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
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocket
import asyncio, json
from sar_physics import stream_sar_grid
from sar_monitor_agent import handle_sar_monitor

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

sim_queue: asyncio.Queue = asyncio.Queue()
sim_params: dict = {}

@app.post("/api/simulator/start")
async def start_sim(body: dict):
    global sim_params
    sim_params = body
    asyncio.create_task(stream_sar_grid(body, sim_queue))
    return {"status": "streaming"}

@app.get("/api/simulator/stream")
async def sim_stream():
    async def generate():
        while True:
            point = await sim_queue.get()
            yield f"data: {json.dumps(point)}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.websocket("/sar-monitor")
async def sar_monitor(ws: WebSocket):
    await ws.accept()
    await handle_sar_monitor(ws)
```

---

### Step 3 — Real-Time SAR Monitor Agent

Flash watches the live stream. Intervenes before a limit breach.

```python
# sar_monitor_agent.py
import google.generativeai as genai
import os, json
from fastapi import WebSocket
from collections import deque

MONITOR_PROMPT = """
You are a real-time SAR safety monitor for RF certification testing.
FCC limit: 1.6 W/kg (1g tissue average). Critical threshold: 90% = 1.44 W/kg.

Recent SAR readings at current position cluster:
{readings}

Analyze the trend. Respond ONLY in JSON, no markdown:
{{
  "status": "ok" | "warning" | "critical",
  "trend": "rising" | "stable" | "falling",
  "message": "one sentence",
  "recommendation": "one action sentence"
}}

Flag warning if 3+ consecutive readings are rising and latest exceeds 1.2 W/kg.
Flag critical if any reading exceeds 1.44 W/kg.
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

            # Call Flash every 5 points to manage rate limits
            if call_count % 5 != 0:
                await ws.send_json({"type": "ok", "sar": point["sar_w_kg"],
                                    "pct_of_limit": point["pct_of_limit"]})
                continue

            prompt = MONITOR_PROMPT.format(readings=json.dumps(list(window), indent=2))
            response = model.generate_content(prompt)
            text = response.text.strip().strip("```json").strip("```").strip()
            result = json.loads(text)

            if result["status"] == "ok":
                await ws.send_json({"type": "ok", "sar": point["sar_w_kg"],
                                    "pct_of_limit": point["pct_of_limit"]})
            elif result["status"] == "warning":
                await ws.send_json({"type": "warning", "message": result["message"],
                                    "sar": point["sar_w_kg"], "trend": result["trend"]})
            else:
                await ws.send_json({"type": "critical", "message": result["message"],
                                    "recommendation": result["recommendation"]})
    except Exception as e:
        print(f"SAR monitor error: {e}")
```

---

### Step 4 — Instrument Script Compiler

Generates valid Rohde & Schwarz EMCvu XML from the test plan.

```python
# script_compiler.py
import google.generativeai as genai
import os

COMPILER_PROMPT = """
You are an RF test automation engineer. Convert this test plan into a valid
Rohde & Schwarz EMCvu XML instrument script.

Test plan:
{test_plan}

Output a complete, schema-valid EMCvu XML file including:
- <TestConfiguration> with device metadata
- <FrequencySweep> sections for each frequency band
- <PowerLevel> entries matching the test plan power levels
- <MeasurementPositions> for each SAR test position
- <CalibrationReference> block
- <PassFailCriteria> with the regulatory limits

Output ONLY the XML, no explanation.
"""

async def compile_script(test_plan: str) -> str:
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL"),
                                   cached_content=os.getenv("CACHE_NAME"))
    resp = model.generate_content(COMPILER_PROMPT.format(test_plan=test_plan[:3000]))
    return resp.text
```

---

### Person 2 — Coding Agent Directive

```
Create a FastAPI service on port 8002 with:

1. POST /api/simulator/start — accepts antenna_x, antenna_y, frequency_mhz, power_dbm
2. GET /api/simulator/stream — SSE stream of SARPoint objects
3. WebSocket /sar-monitor — receives SARPoint, returns monitor status JSON

The SAR physics function:
  def compute_sar(x, y, z, antenna_pos, freq_mhz, power_dbm):
      r = max(sqrt((x-ax)^2 + (y-ay)^2 + (z-az)^2), 0.5)
      power_mw = 10^(power_dbm/10)
      sar = (power_mw * 0.001 * (freq_mhz/2400) * 1.8) / (2 * pi * r^2)
      return sar * normal(1.0, 0.03)

Grid sweep: X[-8 to 8 step 0.5], Y[-10 to 10 step 0.5], Z[0 to 5 step 1.0]
Override SAR to 1.49-1.58 W/kg when near coordinate (8.2, 4.4, 3.0) within radius 1.0.
Stream each point as JSON with fields: x, y, z, frequency_mhz, power_dbm, sar_w_kg,
is_anomaly (bool, true when >90% of 1.6 W/kg limit), pct_of_limit.
Sleep 12ms between points (83 points/sec).
CORS allow all origins.
```

---

### Person 2 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Setup env, confirm physics formula produces realistic values |
| 0:30–1:30 | SSE endpoint streaming grid, verify anomaly injection fires |
| 1:30–2:30 | SAR monitor WebSocket working, Flash responding to rolling window |
| 2:30–3:30 | Full grid sweep verified end-to-end, anomaly alert fires correctly |
| 3:30–4:30 | Instrument script compiler working, valid XML output |
| 4:30–5:00 | Integration test with Person 3's frontend consuming SSE |
| 5:00–6:30 | Polish, rate limit handling, reconnect logic |

**Test your SSE without the frontend:**
```bash
curl -N http://localhost:8002/api/simulator/stream
```

---

---

# PERSON 3 — Interaction Core, 3D Viewport & Live API

**You own:** `frontend/` on port `:3000`
**You do NOT build:** Python backends, SAR physics, Gemini agent calls

**Critical:** Fire all four coding agent prompts in the first 30 minutes. Run them in parallel, then integrate.

---

### Setup

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app
npm install three @react-three/fiber @react-three/drei
```

```env
# .env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SIMULATOR_URL=http://localhost:8002
NEXT_PUBLIC_MOCK_MODE=true   # flip to false when backends are ready
```

---

### Coding Agent Prompt 1 — Articulated Robot Arm

Paste into Claude Code:

```
Create a React component using react-three-fiber named RobotArm.tsx.

Build a 3-joint articulated arm using nested Group hierarchies:
- baseGroup: fixed at world position (11, 13, 11), contains a SphereGeometry joint (r=0.7)
  - shoulderGroup: rotates on Y-axis for horizontal azimuth tracking
    - upperArm: CylinderGeometry(0.15, 0.15, 8) along Y axis
    - SphereGeometry joint at end of upper arm (r=0.5)
    - elbowGroup: rotates on Z-axis for vertical elevation tracking
      - forearm: CylinderGeometry(0.12, 0.12, 6) along Y axis
      - SphereGeometry joint at end of forearm (r=0.35)
      - wristGroup: minor orientation correction
        - probe: CylinderGeometry(0.08, 0.08, 4) along Y axis
        - SphereGeometry tip at probe end (r=0.38), yellow color, emissive

All joint and arm meshes: MeshPhongMaterial color #667788.

Write a closed-form inverse kinematics function updateArm(tx, ty, tz) that:
1. Computes azimuth = atan2(tx - 11, tz - 11), sets shoulderGroup.rotation.y
2. Solves 2-link planar IK in the vertical plane using law of cosines:
   - l1 = 8 (upper arm), l2 = 6 (forearm)
   - d = distance from shoulder to target in the elevation plane
   - cosElbow = (d^2 - l1^2 - l2^2) / (2 * l1 * l2)
   - elbowAngle = acos(clamp(cosElbow, -1, 1))
   - shoulderElevation = atan2(vertical, horizontal) - atan2(l2*sin(elbowAngle), l1 + l2*cos(elbowAngle))
   - sets elbowGroup.rotation.z = elbowAngle
3. Updates smoothly using lerp(current, target, 0.12) each frame for fluid motion

Export updateArm as a ref callback so the parent scene can call it each frame.
```

---

### Coding Agent Prompt 2 — Instanced Voxel Heatmap

Paste into Claude Code:

```
Create a React component using react-three-fiber named VoxelCloud.tsx.

Build an InstancedMesh voxel point cloud:
- Geometry: BoxGeometry(0.62, 0.62, 0.62)
- Material: MeshBasicMaterial with vertexColors: true, transparent: true, opacity: 0.84
- Instance count: 2000 (max grid size)
- Initialize all instances with scale (0.001, 0.001, 0.001) — invisible until measured

Accept a prop: points: Array<{x, y, z, sar_w_kg, pct_of_limit, is_anomaly}>

When a new point arrives:
1. Find the next unrevealed instance index
2. Set its matrix position to (x, y, z) with scale (1, 1, 1)
3. Set its color using this mapping:
   - pct < 0.40: #1044bb (deep blue, safe)
   - pct < 0.65: #1a9980 (teal, moderate)
   - pct < 0.82: #f09510 (amber, caution)
   - pct < 0.92: #e03010 (orange-red, warning)
   - pct >= 0.92: #ff1020 (crimson, critical)
4. Call instanceMatrix.needsUpdate = true and instanceColor.needsUpdate = true

For anomaly voxels (is_anomaly: true):
- Each frame, oscillate their scale between 0.78 and 1.2 using sin(Date.now() * 0.007)
- This creates a pulsing effect on the danger cluster

Export a reset() method that sets all instances back to scale 0.001.
```

---

### Coding Agent Prompt 3 — Webcam Setup Verification

Paste into Claude Code:

```typescript
// Create components/WebcamPanel.tsx
// This component handles Act 1 of the demo: verifying physical setup before scan begins.

// SETUP VERIFICATION PROMPT — use exactly as written:
const PROMPT = `
You are verifying an RF probe positioning setup.

Objects in frame:
- Phone = the device under test (DUT)
- Pen = the RF probe

Requirements:
1. Phone is lying flat, screen visible
2. Pen tip is within 3cm of the phone surface
3. Pen is held approximately perpendicular to phone face (90 degrees +/- 5 degrees)
4. No large metallic objects directly touching the phone

Respond ONLY in this JSON, no markdown or code blocks:
{
  "valid": true or false,
  "issues": [{"description": "text", "severity": "warning or error", "fix": "exact correction"}],
  "message": "one-line summary"
}
`;

// Implementation requirements:
// 1. Use navigator.mediaDevices.getUserMedia({ video: true }) for webcam
// 2. Display live video feed in component
// 3. Every 1500ms: paint current frame to hidden canvas (320x240), extract base64 JPEG
// 4. Send frame to Gemini 3.5 Flash with the prompt above using fetch to /api/verify endpoint
// 5. Parse the JSON response
// 6. Display issues as overlay cards on the video feed with severity-based colors
//    (warning = amber, error = red)
// 7. Show a status badge: "Analyzing..." (gray), "Setup valid" (green), "Issues found" (red)
// 8. When valid is true: emit a "setup-verified" custom event on the window object
//    so the parent dashboard can enable the "Initialize Scan" button
// 9. The "fix" text from each issue should be displayed prominently so the engineer
//    knows exactly what to correct

// Also create pages/api/verify.ts (Next.js API route) that:
// - Accepts POST with { frame: base64_jpeg_string }
// - Calls Gemini 3.5 Flash with the frame and prompt
// - Returns the parsed JSON response
// - Handles JSON parse errors gracefully
```

---

### Coding Agent Prompt 4 — Split-Screen Dashboard

Paste into Claude Code:

```
Create the main dashboard component Dashboard.tsx for a Next.js app.

Dark mode engineering control room layout. Three columns:

LEFT COLUMN (25% width):
- Title: "Agent Stream" in monospace, small, muted
- Scrollable terminal-style feed of SSE events from http://localhost:8000/api/projects/:id/events
- Each event rendered as a card with monospace font:
  - agent_start: blue left border, agent name + message
  - agent_complete: green left border, agent name + truncated output
  - anomaly_detected: red left border, pulsing, full anomaly message
  - phase_complete: purple left border, phase summary
  - report_ready: emerald left border, "Report ready - download"
- Auto-scrolls to bottom on new events

CENTER COLUMN (55% width):
- Title: "Digital Twin — SAR Scan" 
- A Three.js canvas (react-three-fiber Canvas component) containing:
  - Semi-transparent phantom body box (BoxGeometry 15x22x8, opacity 0.07, blue)
  - Gantry wireframe box (EdgesGeometry 22x27x20, opacity 0.28)
  - RobotArm component (from Prompt 1)
  - VoxelCloud component (from Prompt 2)
  - Orbiting camera using useFrame to slowly rotate around the scene
- Below canvas: stats bar showing current SAR, % of limit, voxel count, peak SAR
- "Initialize Scan" button — disabled until setup-verified event fires
- On click: POST to simulator /api/simulator/start, then consume SSE stream
  from /api/simulator/stream and feed points to VoxelCloud

RIGHT COLUMN (20% width):
- Title: "Setup Verification" 
- WebcamPanel component (from Prompt 3) fills this column
- Below webcam: jurisdiction agent status board
  - 5 rows: FCC, EU, CA, JP, BR
  - Each row: colored dot (gray=idle, spinning=active, green=complete) + region name
  - Updates based on SSE events from backend

Background: #03030b (near black)
All text: monospace font, dim colors, engineering aesthetic
```

---

### Mock SSE Server (for development — no backend needed)

```typescript
// mocks/mock-sse.ts
// Run with: npx ts-node mocks/mock-sse.ts
import { createServer } from "http";

const EVENTS = [
  { event: "agent_start",    data: { agent: "intake", message: "Parsing BOM..." }, delay: 500 },
  { event: "agent_complete", data: { agent: "intake", output: "nRF52840 BLE + RTL8723DE WiFi detected. Body-worn: true." }, delay: 1400 },
  { event: "agent_start",    data: { agent: "jurisdiction_fcc", message: "Analyzing FCC Part 15 requirements..." }, delay: 1600 },
  { event: "agent_start",    data: { agent: "jurisdiction_eu",  message: "Analyzing EU RED requirements..." }, delay: 1600 },
  { event: "agent_start",    data: { agent: "jurisdiction_ca",  message: "Analyzing ISED Canada requirements..." }, delay: 1600 },
  { event: "agent_complete", data: { agent: "jurisdiction_fcc", output: "Requires: Part 15.247, SAR per KDB 447498, OET-65 compliance. Est: 40 robot hours." }, delay: 3500 },
  { event: "agent_complete", data: { agent: "jurisdiction_eu",  output: "Requires: EN 300 328, EN 62311 SAR (2.0 W/kg), CE marking." }, delay: 3700 },
  { event: "agent_complete", data: { agent: "jurisdiction_ca",  output: "Requires: ISED RSS-247, RSS-102 SAR (1.6 W/kg, same as FCC)." }, delay: 3900 },
  { event: "phase_complete", data: { phase: "scoping", summary: "5 jurisdictions analyzed. 14 tests required. Estimated 3 weeks lab time." }, delay: 4500 },
  { event: "agent_start",    data: { agent: "test_plan", message: "Drafting 45-page test plan with regulatory citations..." }, delay: 5000 },
  { event: "agent_complete", data: { agent: "test_plan", output: "Test plan complete: 14 test configurations, 6 frequency bands, 4 SAR positions." }, delay: 8000 },
  { event: "anomaly_detected", data: {
      id: "a1", severity: "critical",
      position: [8.2, 4.4, 3.0],
      sar: 1.54, limit: 1.6,
      message: "SAR 1.54 W/kg detected — 96% of FCC limit. Growth trajectory indicates breach within 4 steps.",
      recommendation: "Pause test matrices. Review device antenna orientation."
    }, delay: 12000 },
  { event: "report_ready", data: { download_url: "/mock-report.pdf" }, delay: 18000 },
];

createServer((req, res) => {
  if (req.url?.includes("/events")) {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    EVENTS.forEach(({ event, data, delay }) => {
      setTimeout(() => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`), delay);
    });
  }
}).listen(8003, () => console.log("Mock SSE on :8003 — set NEXT_PUBLIC_BACKEND_URL=http://localhost:8003"));
```

Flip to real backend by changing `.env.local`:
```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000   # real Person 1 backend
NEXT_PUBLIC_MOCK_MODE=false
```

---

### Person 3 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Fire all 4 coding agent prompts simultaneously. Let Claude Code generate all 4 components. |
| 0:30–1:30 | Assemble generated components into Dashboard. Mock SSE running. |
| 1:30–2:30 | ACT 1: Test webcam live against real phone + pen on desk. Verify green/red states. |
| 2:30–3:30 | ACT 2: Connect simulator SSE (:8002). Robot arm tracks points. Voxel cloud builds. |
| 3:30–4:30 | Wire Person 1 SSE to agent feed left panel. All three columns populated. |
| 4:30–5:30 | Full end-to-end: webcam → green → scan → anomaly flash → report ready. |
| 5:30–6:30 | Polish: timing, transitions, anomaly pulse intensity, demo flow rehearsal. |

---

---

## Integration Checkpoints

| Time | Who | What to verify |
|---|---|---|
| T+1:30h | P1 + P3 | P1 SSE endpoint streaming. P3 agent feed showing mock events from P1. |
| T+3:00h | P2 + P3 | P2 simulator streaming SAR points. P3 voxel cloud consuming them. Robot arm moving. |
| T+4:30h | All | Full pipeline live: BOM in → agents fire → scan starts → anomaly detected. |
| T+6:00h | All | Full demo rehearsal. 3-minute run-through. No broken states. |

---

## Google AI Studio Feature Map

| Feature | Who Uses It | Purpose |
|---|---|---|
| Gemini 3.5 Flash | P1, P2 | All agent intelligence |
| Managed Agents API | P1 | Persistent project state, sub-agent orchestration |
| Context Caching | P1 | Regulatory corpus cached once, all 5 jurisdiction agents share it |
| Live API | P3 | Webcam setup verification — native video understanding |
| Code Execution | P1 | Report chart generation via matplotlib |
| File API | P1 | Calibration certificate storage |
| Search Grounding | P1 | Live regulatory update awareness |
| Parallel function calling | P1 | 5 jurisdiction + 5 report agents simultaneously |

---

## Environment Variables

```env
# All services share this file — each service reads only what it needs

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
CACHE_NAME=              # Person 1 fills this after running cache_loader.py

# Ports
BACKEND_PORT=8000
SIMULATOR_PORT=8002

# Frontend
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SIMULATOR_URL=http://localhost:8002
NEXT_PUBLIC_MOCK_MODE=true
```

---

## Quick Start

```bash
# Terminal 1 — Person 1
cd backend
source venv/bin/activate
python cache_loader.py        # run ONCE, copy CACHE_NAME to .env
uvicorn main:app --reload --port 8000

# Terminal 2 — Person 2
cd simulator
source venv/bin/activate
uvicorn main:app --reload --port 8002

# Terminal 3 — Person 3 (dev mode with mock)
cd frontend
npx ts-node mocks/mock-sse.ts &   # mock backend for development
npm run dev                        # http://localhost:3000
```

---

## Demo Script — 3 Minutes

**[0:00–0:30]** *"Every wireless device sold anywhere in the world must pass RF certification before it can ship. The engineering work takes 2 weeks and costs $50,000. This is LabPilot."*

Paste mock BOM. Hit submit. Watch 5 jurisdiction agents fire simultaneously in the left panel.

**[0:30–1:00]** *"Before a single measurement can be taken, the physical setup must be verified."*

Show the webcam panel. Phone and pen on the desk. Deliberately misalign the pen. Flash annotates: "Pen is not perpendicular — rotate 8° clockwise." Correct it. Green light. *"Setup confirmed."*

**[1:00–2:00]** *"Flash doesn't wait for the test to finish. It monitors the live data stream."*

Click Initialize Scan. Robot arm begins moving. Voxel cloud builds. Blue → teal → amber as the heatmap accumulates. The anomaly cluster hits. Red pulse. Left panel: *"SAR 1.54 W/kg — 96% of FCC limit. Recommend pause."*

**[2:00–3:00]** *"Five agents simultaneously draft the compliance report."*

Five report agents light up in the left panel at once. Report ready fires. *"200-page TCB-ready report. What used to take 2 days."*
