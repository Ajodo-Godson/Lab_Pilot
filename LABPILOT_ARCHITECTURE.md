# LabPilot — Architectural Plan
### Google I/O Hackathon · Gemini 3.5 Flash · 6.5-Hour Sprint

---

## Overview

LabPilot automates the engineering intelligence layer of RF/wireless certification testing — from client email intake to TCB-ready report — using Gemini 3.5 Flash managed agents, the Live API for real-time video verification, and a physics-based SAR simulation engine.

**The three services are fully independent. Each person owns one service end-to-end. Interfaces are mocked from minute zero so no one waits.**

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       GOOGLE AI STUDIO                           │
│  Gemini 3.5 Flash · Managed Agents · Live API · Context Cache   │
│  Code Execution · File API · Search Grounding                    │
└───────────────┬─────────────────────┬───────────────────────────┘
                │                     │
                ▼                     ▼
┌──────────────────────┐   ┌──────────────────────┐
│   BACKEND SERVICE    │   │   LIVE SERVICE        │
│   Person 1           │   │   Person 2            │
│   FastAPI :8000      │   │   FastAPI :8001        │
│   Agents + Sim       │   │   Webcam + Monitor    │
└──────────┬───────────┘   └──────────┬────────────┘
           │  SSE /events              │  WS /webcam
           └──────────────┬────────────┘
                          ▼
            ┌──────────────────────────┐
            │      FRONTEND            │
            │      Person 3            │
            │      Next.js :3000       │
            │      Three.js · Tailwind │
            └──────────────────────────┘
```

---

## ⚠️ Read First: Shared Contracts

**These schemas are law. All three people implement against them before writing any other code. Do not deviate.**

### REST API (Backend :8000)

```typescript
// POST /api/projects
Request:  { device_name: string, bom_text: string, target_regions: string[] }
Response: { project_id: string, status: "created" }

// POST /api/projects/:id/scope
Request:  {}
Response: { project_id: string, status: "scoping" }

// POST /api/projects/:id/simulate
Request:  { antenna_x: number, antenna_y: number, frequency_mhz: number, power_dbm: number }
Response: { project_id: string, status: "simulating" }

// GET /api/projects/:id/report
Response: { pdf_base64: string, summary: string }

// GET /api/projects/:id/events   ← SSE stream
// See SSE event schema below
```

### SSE Event Schema (Backend → Frontend)

```typescript
type SSEEvent =
  | { event: "agent_start";       data: { agent: AgentName; message: string } }
  | { event: "agent_complete";    data: { agent: AgentName; output: string } }
  | { event: "agent_error";       data: { agent: AgentName; error: string } }
  | { event: "sar_measurement";   data: SARPoint }
  | { event: "anomaly_detected";  data: Anomaly }
  | { event: "phase_complete";    data: { phase: PhaseName; summary: string } }
  | { event: "report_ready";      data: { download_url: string } }

type AgentName =
  | "intake" | "jurisdiction_fcc" | "jurisdiction_eu" | "jurisdiction_ca"
  | "jurisdiction_jp" | "jurisdiction_br" | "test_plan" | "script_gen"
  | "anomaly_detector" | "report_setup" | "report_measurement"
  | "report_citer" | "report_narrator" | "report_compliance"

type SARPoint = {
  x: number; y: number; z: number
  frequency_mhz: number; power_dbm: number; sar_w_kg: number
  is_anomaly: boolean; pct_of_limit: number
}

type Anomaly = {
  id: string; severity: "warning" | "critical"
  position: [number, number, number]
  sar: number; limit: number
  message: string; recommendation: string
}

type PhaseName = "intake" | "scoping" | "test_plan" | "simulation" | "report"
```

### WebSocket Schema (Live Service :8001)

```typescript
// ws://localhost:8001/webcam
// Client sends: { type: "frame", data: base64_jpeg }
// Server sends:
type WebcamMessage =
  | { type: "annotation"; issue: string; severity: "ok"|"warning"|"error"; bbox: [number,number,number,number] }
  | { type: "setup_valid"; message: string }
  | { type: "setup_invalid"; issues: string[] }

// ws://localhost:8001/sar-monitor
// Client sends: SARPoint (same as above)
// Server sends:
type SARMonitorMessage =
  | { type: "ok"; sar: number; pct_of_limit: number }
  | { type: "warning"; message: string; sar: number; trend: "rising"|"stable"|"falling" }
  | { type: "critical"; message: string; recommendation: string }
```

### Mock Device BOM (use this for demo)

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

| Layer | Tech | Notes |
|---|---|---|
| Backend | Python 3.11 + FastAPI + uvicorn | Async throughout |
| AI | google-generativeai SDK | Gemini 3.5 Flash |
| Live | google-generativeai Live API | Separate service |
| Frontend | Next.js 14 + Tailwind + TypeScript | App router |
| 3D | Three.js | SAR heatmap |
| Real-time | SSE (backend→frontend), WebSocket (live→frontend) | |
| Mock | json-server | P3 uses during development |

---

## Repository Structure

```
labpilot/
├── .env.example
├── contracts/
│   └── types.ts          ← shared schema (all three reference this)
│
├── backend/              ← Person 1 owns
│   ├── requirements.txt
│   ├── main.py
│   ├── orchestrator.py
│   ├── cache_loader.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── intake.py
│   │   ├── jurisdiction.py
│   │   ├── test_plan.py
│   │   ├── script_gen.py
│   │   ├── anomaly.py
│   │   └── report.py
│   ├── simulator/
│   │   ├── sar_physics.py
│   │   └── anomaly_injector.py
│   └── prompts/
│       ├── intake.txt
│       ├── jurisdiction_fcc.txt
│       ├── jurisdiction_eu.txt
│       ├── test_plan.txt
│       ├── anomaly.txt
│       └── report_*.txt
│
├── live-service/         ← Person 2 owns
│   ├── requirements.txt
│   ├── main.py
│   ├── webcam_agent.py
│   └── sar_monitor_agent.py
│
├── frontend/             ← Person 3 owns
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx
│   │   └── project/[id]/page.tsx
│   ├── components/
│   │   ├── ProjectDashboard.tsx
│   │   ├── AgentFeed.tsx
│   │   ├── SARViewer.tsx
│   │   ├── WebcamPanel.tsx
│   │   └── ReportViewer.tsx
│   └── mocks/
│       ├── db.json        ← json-server mock data
│       └── mock-sse.ts    ← mock SSE stream
│
└── demo/
    ├── mock_bom.json
    ├── mock_sar_data.csv  ← pre-generated with anomalies planted
    └── mock_calibration_cert.json
```

---

---

# PERSON 1 — Backend + Agents + Simulation

**You own:** `backend/` entirely. The frontend and live service treat your API as a black box.

**Your deliverables:**
1. FastAPI server on `:8000` matching the REST + SSE contract exactly
2. Managed Agents orchestrator running all phases
3. 5 parallel jurisdiction agents with context-cached regulatory corpus
4. SAR physics simulator streaming realistic data with planted anomalies
5. All agent prompts tuned and tested

**You do NOT build:** webcam, WebSocket, Three.js, or any frontend code.

---

### Setup

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn google-generativeai python-dotenv numpy asyncio-sse
```

```env
# .env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
PORT=8000
```

---

### Step 1 — Regulatory Corpus + Context Cache (do this first, takes ~10 min)

The entire FCC KDB + EU standards corpus is cached once. All jurisdiction agents reference the cache ID — no re-sending tokens.

```python
# cache_loader.py
import google.generativeai as genai
from google.generativeai import caching
import datetime, os

FCC_CORPUS = """
[PASTE: FCC Part 15.247, 15.249, OET-65 key excerpts]
[PASTE: KDB 447498 SAR procedures]
[PASTE: KDB 616217, KDB 648474]
SAR limit: 1.6 W/kg averaged over 1g tissue (portable devices)
FCC ID labeling requirements per 47 CFR 2.925...
"""

EU_CORPUS = """
EN 300 328 v2.2.2 — WLAN/BT requirements
EN 301 489-1, EN 301 489-17 — EMC
EN 62311:2020 — SAR limit 2.0 W/kg over 10g tissue
CE marking requirements...
"""

CA_CORPUS = """
ISED RSS-247 Issue 2 — 2.4 GHz / 5 GHz
RSS-Gen Issue 5 — general requirements
RSS-102 Issue 6 — SAR limit 1.6 W/kg (1g, same as FCC)
"""

JP_CORPUS = "ARIB STD-T66 — Bluetooth. MIC Ordinance 88 — technical standards..."

BR_CORPUS = "ANATEL Resolution 715/2019. Homologation requirements. SAR limit 1.6 W/kg..."

def load_cache():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    cache = caching.CachedContent.create(
        model=os.getenv("GEMINI_MODEL"),
        system_instruction="You are a regulatory expert for wireless device certification.",
        contents=[FCC_CORPUS, EU_CORPUS, CA_CORPUS, JP_CORPUS, BR_CORPUS],
        ttl=datetime.timedelta(hours=8),
        display_name="regulatory_corpus"
    )
    print(f"Cache created: {cache.name}")
    return cache.name

if __name__ == "__main__":
    print(load_cache())
```

Run this once at the start: `python cache_loader.py` → save the cache name in `.env` as `CACHE_NAME=...`

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory project store (sufficient for hackathon)
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
            if event['event'] == 'report_ready':
                break
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/projects/{pid}/simulate")
async def start_simulation(pid: str, body: dict):
    from simulator.sar_physics import stream_sar
    asyncio.create_task(stream_sar(pid, body, event_queues[pid]))
    return {"project_id": pid, "status": "simulating"}
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
from agents.script_gen import run_script_gen
from agents.report import run_report

async def run_project(pid: str, data: dict, queue: asyncio.Queue):
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL"))

    # Phase 1: Intake
    await queue.put({"event": "agent_start", "data": {"agent": "intake", "message": "Parsing BOM..."}})
    device_profile = await run_intake(model, data)
    await queue.put({"event": "agent_complete", "data": {"agent": "intake", "output": str(device_profile)}})

    # Phase 2: 5 jurisdiction agents in parallel
    regions = ["fcc", "eu", "ca", "jp", "br"]
    for r in regions:
        await queue.put({"event": "agent_start", "data": {"agent": f"jurisdiction_{r}", "message": f"Analyzing {r.upper()} requirements..."}})

    cert_matrix = await run_jurisdiction_parallel(model, device_profile)
    for r in regions:
        await queue.put({"event": "agent_complete", "data": {"agent": f"jurisdiction_{r}", "output": cert_matrix.get(r, "")}})
    await queue.put({"event": "phase_complete", "data": {"phase": "scoping", "summary": f"{len(cert_matrix)} jurisdictions analyzed"}})

    # Phase 3: Test plan
    await queue.put({"event": "agent_start", "data": {"agent": "test_plan", "message": "Drafting test plan..."}})
    test_plan = await run_test_plan(model, device_profile, cert_matrix)
    await queue.put({"event": "agent_complete", "data": {"agent": "test_plan", "output": test_plan[:500]}})
    await queue.put({"event": "phase_complete", "data": {"phase": "test_plan", "summary": "Test plan complete"}})

    # Phase 4: Script gen
    await queue.put({"event": "agent_start", "data": {"agent": "script_gen", "message": "Generating R&S EMCvu XML..."}})
    script = await run_script_gen(model, test_plan)
    await queue.put({"event": "agent_complete", "data": {"agent": "script_gen", "output": "Script generated"}})
```

---

### Step 4 — Jurisdiction Agents (parallel with context cache)

```python
# agents/jurisdiction.py
import asyncio
import google.generativeai as genai
import os

REGION_PROMPTS = {
    "fcc": "Analyze this device under FCC Part 15 rules. List every required test, the exact procedure citation, estimated hours, and equipment needed. Device profile: {profile}",
    "eu":  "Analyze this device under EU Radio Equipment Directive. List CE marking requirements, EN standards required, SAR obligations. Device profile: {profile}",
    "ca":  "Analyze this device under ISED Canada RSS rules. List every required test and certification path. Device profile: {profile}",
    "jp":  "Analyze this device under ARIB/MIC Japan technical standards. List required tests. Device profile: {profile}",
    "br":  "Analyze this device under ANATEL Brazil Resolution 715. List homologation requirements. Device profile: {profile}",
}

async def run_single_jurisdiction(region: str, profile: dict, cache_name: str) -> str:
    model = genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL"),
        cached_content=cache_name  # regulatory corpus pre-cached
    )
    prompt = REGION_PROMPTS[region].format(profile=str(profile))
    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text

async def run_jurisdiction_parallel(model, device_profile: dict) -> dict:
    cache_name = os.getenv("CACHE_NAME")
    tasks = {
        region: run_single_jurisdiction(region, device_profile, cache_name)
        for region in ["fcc", "eu", "ca", "jp", "br"]
    }
    results = await asyncio.gather(*tasks.values())
    return dict(zip(tasks.keys(), results))
```

---

### Step 5 — SAR Physics Simulator

```python
# simulator/sar_physics.py
import numpy as np
import asyncio
import json

SAR_LIMIT_FCC = 1.6   # W/kg
SAR_LIMIT_EU  = 2.0   # W/kg

def compute_sar(x, y, z, antenna_pos, freq_mhz, power_dbm):
    """Simplified near-field SAR approximation."""
    ax, ay, az = antenna_pos
    r = max(np.sqrt((x-ax)**2 + (y-ay)**2 + (z-az)**2), 0.5)
    power_mw = 10 ** (power_dbm / 10)
    freq_factor = freq_mhz / 2400
    tissue_conductivity = 1.8  # S/m, approximate muscle tissue at 2.4 GHz
    sar = (power_mw * 0.001 * freq_factor * tissue_conductivity) / (2 * np.pi * r**2)
    noise = np.random.normal(1.0, 0.03)
    return round(sar * noise, 4)

async def stream_sar(pid: str, params: dict, queue: asyncio.Queue):
    """Stream SAR measurements in real time, mimicking robot scan."""
    antenna_pos = (params.get("antenna_x", 0), params.get("antenna_y", 0), 2.0)
    freq = params.get("frequency_mhz", 2412)
    power = params.get("power_dbm", 20)

    # Scan grid: 2mm steps, 20x15x10 cm volume
    xs = np.arange(-10, 10, 0.4)
    ys = np.arange(-7.5, 7.5, 0.4)
    zs = np.arange(0, 5, 0.4)

    for xi in xs:
        for yi in ys:
            for zi in zs:
                sar = compute_sar(xi, yi, zi, antenna_pos, freq, power)

                # Inject anomaly: near-limit cluster around (8.2, 4.4, 3.0)
                if abs(xi - 8.2) < 0.8 and abs(yi - 4.4) < 0.8:
                    sar = round(np.random.uniform(1.48, 1.57), 4)

                pct = sar / SAR_LIMIT_FCC
                is_anomaly = pct > 0.90

                point = {
                    "x": round(xi, 2), "y": round(yi, 2), "z": round(zi, 2),
                    "frequency_mhz": freq, "power_dbm": power,
                    "sar_w_kg": sar, "is_anomaly": is_anomaly,
                    "pct_of_limit": round(pct, 3)
                }

                await queue.put({"event": "sar_measurement", "data": point})

                if is_anomaly:
                    await queue.put({
                        "event": "anomaly_detected",
                        "data": {
                            "id": f"anomaly_{xi}_{yi}",
                            "severity": "critical" if pct > 0.95 else "warning",
                            "position": [xi, yi, zi],
                            "sar": sar, "limit": SAR_LIMIT_FCC,
                            "message": f"SAR {sar} W/kg is {round(pct*100)}% of the 1.6 W/kg FCC limit.",
                            "recommendation": "Recommend pausing scan and reviewing device configuration."
                        }
                    })

                await asyncio.sleep(0.015)  # ~67 points/sec, smooth visualization
```

---

### Step 6 — Report Generation (5 parallel sub-agents)

```python
# agents/report.py
import asyncio
import google.generativeai as genai
import os

REPORT_AGENTS = {
    "report_setup":       "Write the test setup section. Describe equipment used, phantom type, probe model, environmental conditions. Data: {data}",
    "report_measurement": "Generate measurement summary tables and describe key findings. Data: {data}",
    "report_citer":       "For each measurement value, cite the exact regulatory paragraph it satisfies. Data: {data}",
    "report_narrator":    "Write prose explaining each anomaly found and how it was resolved. Data: {data}",
    "report_compliance":  "Draft the executive compliance statement. Conclude with pass/fail per jurisdiction. Data: {data}",
}

async def run_report(model, test_plan: str, sar_results: list, anomalies: list) -> dict:
    data = {"test_plan": test_plan[:2000], "sar_summary": str(sar_results[:10]), "anomalies": anomalies}
    cache_name = os.getenv("CACHE_NAME")

    async def run_section(name: str, prompt_template: str) -> tuple[str, str]:
        m = genai.GenerativeModel(model_name=os.getenv("GEMINI_MODEL"), cached_content=cache_name)
        prompt = prompt_template.format(data=str(data))
        resp = await asyncio.to_thread(m.generate_content, prompt)
        return name, resp.text

    tasks = [run_section(k, v) for k, v in REPORT_AGENTS.items()]
    results = await asyncio.gather(*tasks)
    return dict(results)
```

---

### Person 1 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Env setup, run `cache_loader.py`, confirm cache name |
| 0:30–1:30 | `main.py` + `/api/projects` + SSE endpoint running with mock queue |
| 1:30–2:30 | Intake agent + jurisdiction parallel agents working |
| 2:30–3:30 | Test plan + script gen agents working, full phase 2→3 pipeline |
| 3:30–4:30 | SAR simulator streaming correctly, anomaly injection confirmed |
| 4:30–5:30 | Report agents (5 parallel) working end-to-end |
| 5:30–6:00 | Full pipeline test, mock BOM → report in one run |
| 6:00–6:30 | Fix bugs, ensure SSE events match schema exactly |

---

---

# PERSON 2 — Live Service (Webcam + SAR Monitor)

**You own:** `live-service/` entirely. This is a completely separate FastAPI service on `:8001`.

**Your deliverables:**
1. WebSocket endpoint `/webcam` — receives video frames, returns setup annotations via Gemini Live API
2. WebSocket endpoint `/sar-monitor` — receives SAR points, flags trends using Flash
3. Both endpoints match the WebSocket schema exactly

**You do NOT build:** the SAR physics simulator, the main REST API, or any frontend code.

---

### Setup

```bash
cd live-service
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn websockets google-generativeai python-dotenv pillow
```

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash
PORT=8001
```

---

### Step 1 — Service Entry Point

```python
# main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from webcam_agent import handle_webcam
from sar_monitor_agent import handle_sar_monitor

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.websocket("/webcam")
async def webcam_endpoint(ws: WebSocket):
    await ws.accept()
    await handle_webcam(ws)

@app.websocket("/sar-monitor")
async def sar_monitor_endpoint(ws: WebSocket):
    await ws.accept()
    await handle_sar_monitor(ws)
```

---

### Step 2 — Webcam Setup Verification Agent

This uses Gemini's native vision to watch the physical test setup and validate it against the test plan spec.

```python
# webcam_agent.py
import google.generativeai as genai
import os, json, base64
from fastapi import WebSocket

TEST_PLAN_SPEC = """
Required setup for SmartPatch X1 body-worn SAR test:
- Device flat against phantom surface, screen facing outward
- Probe positioned perpendicular to phantom surface (90° ± 2°)
- Minimum 5mm separation between device back and phantom surface
- No metal objects within 20cm of device
- Cables routed away from phantom, minimum 30cm separation
"""

VERIFICATION_PROMPT = f"""
You are an RF test setup verification agent.
Reference specification:
{TEST_PLAN_SPEC}

Look at this image of the test setup. Check every requirement.
Respond in JSON only:
{{
  "valid": true/false,
  "issues": [
    {{ "description": "...", "severity": "warning|error", "bbox": [x_pct, y_pct, w_pct, h_pct] }}
  ],
  "message": "one-line summary"
}}
"""

async def handle_webcam(ws: WebSocket):
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL"))

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "frame":
                continue

            # Decode base64 JPEG frame
            img_data = base64.b64decode(msg["data"])
            image_part = {"mime_type": "image/jpeg", "data": img_data}

            response = model.generate_content([VERIFICATION_PROMPT, image_part])
            result = json.loads(response.text.strip().strip("```json").strip("```"))

            if result.get("valid"):
                await ws.send_json({"type": "setup_valid", "message": result["message"]})
            else:
                for issue in result.get("issues", []):
                    await ws.send_json({
                        "type": "annotation",
                        "issue": issue["description"],
                        "severity": issue["severity"],
                        "bbox": issue.get("bbox", [0, 0, 0, 0])
                    })
                await ws.send_json({"type": "setup_invalid", "issues": [i["description"] for i in result["issues"]]})

    except Exception as e:
        await ws.send_json({"type": "annotation", "issue": str(e), "severity": "error", "bbox": [0,0,0,0]})
```

---

### Step 3 — Real-Time SAR Monitor Agent

Receives SAR points from the frontend (which is streaming them from backend SSE), watches for trends approaching the regulatory limit.

```python
# sar_monitor_agent.py
import google.generativeai as genai
import os, json
from fastapi import WebSocket
from collections import deque

MONITOR_PROMPT = """
You are a real-time SAR safety monitor for RF certification testing.
FCC limit: 1.6 W/kg (1g tissue average).

Recent SAR readings at this position cluster:
{readings}

Analyze the trend. Respond in JSON only:
{{
  "status": "ok|warning|critical",
  "trend": "rising|stable|falling",
  "message": "...",
  "recommendation": "..." 
}}

Critical threshold: any reading above 1.44 W/kg (90% of limit).
Warn if 3+ consecutive readings are rising and the last exceeds 1.2 W/kg.
"""

async def handle_sar_monitor(ws: WebSocket):
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL"))
    recent_readings = deque(maxlen=10)  # rolling window

    try:
        while True:
            point = await ws.receive_json()
            recent_readings.append(point)

            # Only invoke Flash every 5 points to manage rate limits
            if len(recent_readings) % 5 != 0:
                await ws.send_json({"type": "ok", "sar": point["sar_w_kg"], "pct_of_limit": point["pct_of_limit"]})
                continue

            prompt = MONITOR_PROMPT.format(readings=json.dumps(list(recent_readings), indent=2))
            response = model.generate_content(prompt)
            result = json.loads(response.text.strip().strip("```json").strip("```"))

            if result["status"] == "ok":
                await ws.send_json({"type": "ok", "sar": point["sar_w_kg"], "pct_of_limit": point["pct_of_limit"]})
            elif result["status"] == "warning":
                await ws.send_json({
                    "type": "warning",
                    "message": result["message"],
                    "sar": point["sar_w_kg"],
                    "trend": result["trend"]
                })
            else:
                await ws.send_json({
                    "type": "critical",
                    "message": result["message"],
                    "recommendation": result["recommendation"]
                })

    except Exception as e:
        print(f"SAR monitor error: {e}")
```

---

### Person 2 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Env setup, confirm Live API access, test basic Flash vision call |
| 0:30–1:30 | WebSocket server running, accept connections, echo test |
| 1:30–2:30 | Webcam agent: single image → Flash → annotation JSON working |
| 2:30–3:30 | Webcam agent: continuous frame stream, annotation loop |
| 3:30–4:30 | SAR monitor agent: rolling window + Flash analysis working |
| 4:30–5:30 | Test both endpoints with mock data (use wscat or simple script) |
| 5:30–6:30 | Polish: error handling, rate limiting, reconnect logic |

**Testing your endpoints without frontend:**
```bash
# Install wscat
npm install -g wscat

# Test webcam endpoint
wscat -c ws://localhost:8001/webcam
> {"type": "frame", "data": "<base64_jpeg>"}

# Test SAR monitor
wscat -c ws://localhost:8001/sar-monitor
> {"x":8.2,"y":4.4,"z":3.0,"frequency_mhz":2412,"power_dbm":20,"sar_w_kg":1.54,"is_anomaly":true,"pct_of_limit":0.963}
```

---

---

# PERSON 3 — Frontend

**You own:** `frontend/` entirely. You develop against mock data from minute zero — never blocked by P1 or P2.

**Your deliverables:**
1. Project creation form → live agent activity feed
2. Three.js 3D SAR heatmap, updating in real time from SSE
3. Webcam panel with live annotation overlays
4. Anomaly cards with dismiss/flag UI
5. Report viewer panel

**You do NOT build:** any Python, any Gemini calls, any SAR physics.

---

### Setup

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app
npm install three @types/three eventsource
```

---

### Step 1 — Mock Server (start here, never wait for P1)

```json
// mocks/db.json
{
  "projects": [
    {
      "id": "demo01",
      "device_name": "SmartPatch X1",
      "status": "simulating"
    }
  ]
}
```

```typescript
// mocks/mock-sse.ts — run this to simulate backend SSE
// Usage: npx ts-node mocks/mock-sse.ts
import { createServer } from "http";

const EVENTS = [
  { event: "agent_start",    data: { agent: "intake", message: "Parsing BOM..." }, delay: 500 },
  { event: "agent_complete", data: { agent: "intake", output: "nRF52840 BLE + RTL8723DE WiFi detected" }, delay: 1200 },
  { event: "agent_start",    data: { agent: "jurisdiction_fcc", message: "Analyzing FCC requirements..." }, delay: 1400 },
  { event: "agent_start",    data: { agent: "jurisdiction_eu",  message: "Analyzing EU requirements..." }, delay: 1400 },
  { event: "agent_start",    data: { agent: "jurisdiction_ca",  message: "Analyzing ISED requirements..." }, delay: 1400 },
  { event: "agent_complete", data: { agent: "jurisdiction_fcc", output: "Requires: FCC Part 15.247, SAR per KDB 447498" }, delay: 3000 },
  { event: "agent_complete", data: { agent: "jurisdiction_eu",  output: "Requires: EN 300 328, EN 62311 SAR" }, delay: 3200 },
  { event: "phase_complete", data: { phase: "scoping", summary: "3 jurisdictions analyzed, 11 tests required" }, delay: 4000 },
  { event: "anomaly_detected", data: {
    id: "a1", severity: "warning", position: [8.2, 4.4, 3.0],
    sar: 1.54, limit: 1.6,
    message: "SAR 1.54 W/kg is 96% of the 1.6 W/kg FCC limit.",
    recommendation: "Recommend pausing scan to review device configuration."
  }, delay: 8000 },
  { event: "report_ready", data: { download_url: "/mock-report.pdf" }, delay: 12000 },
];

// Serve SSE on :8002 with CORS
createServer((req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  EVENTS.forEach(({ event, data, delay }) => {
    setTimeout(() => {
      res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
    }, delay);
  });
}).listen(8002, () => console.log("Mock SSE on :8002"));
```

Switch from mock to real by changing one env var:
```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8002   # mock
# NEXT_PUBLIC_API_URL=http://localhost:8000  # real — flip when P1 is ready
NEXT_PUBLIC_LIVE_URL=ws://localhost:8001
```

---

### Step 2 — Agent Activity Feed

```typescript
// components/AgentFeed.tsx
"use client";
import { useEffect, useState } from "react";

type AgentEvent = {
  id: string;
  event: string;
  agent?: string;
  message?: string;
  output?: string;
  timestamp: number;
};

export default function AgentFeed({ projectId }: { projectId: string }) {
  const [events, setEvents] = useState<AgentEvent[]>([]);

  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_API_URL}/api/projects/${projectId}/events`;
    const es = new EventSource(url);

    const handlers = ["agent_start", "agent_complete", "phase_complete", "anomaly_detected", "report_ready"];
    handlers.forEach(eventType => {
      es.addEventListener(eventType, (e: MessageEvent) => {
        const data = JSON.parse(e.data);
        setEvents(prev => [...prev, {
          id: `${eventType}-${Date.now()}`,
          event: eventType,
          ...data,
          timestamp: Date.now()
        }]);
      });
    });

    return () => es.close();
  }, [projectId]);

  const statusColor = (event: string) => ({
    "agent_start":     "bg-blue-50 border-blue-200 text-blue-800",
    "agent_complete":  "bg-green-50 border-green-200 text-green-800",
    "anomaly_detected":"bg-red-50 border-red-300 text-red-800",
    "phase_complete":  "bg-purple-50 border-purple-200 text-purple-800",
    "report_ready":    "bg-emerald-50 border-emerald-300 text-emerald-800",
  }[event] ?? "bg-gray-50 border-gray-200 text-gray-700");

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto">
      {events.map(ev => (
        <div key={ev.id} className={`p-3 rounded-lg border text-sm ${statusColor(ev.event)}`}>
          <div className="flex items-center justify-between">
            <span className="font-mono font-medium">{ev.agent ?? ev.event}</span>
            <span className="text-xs opacity-60">{new Date(ev.timestamp).toLocaleTimeString()}</span>
          </div>
          {(ev.message ?? ev.output) && (
            <p className="mt-1 opacity-80">{ev.message ?? ev.output}</p>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

### Step 3 — Three.js SAR Heatmap

```typescript
// components/SARViewer.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

type SARPoint = {
  x: number; y: number; z: number;
  sar_w_kg: number; is_anomaly: boolean; pct_of_limit: number;
};

function sarToColor(pct: number): THREE.Color {
  // Blue (safe) → yellow → red (near limit)
  if (pct < 0.5) return new THREE.Color(0x3b8bd4);
  if (pct < 0.75) return new THREE.Color().lerpColors(new THREE.Color(0x3b8bd4), new THREE.Color(0xef9f27), (pct - 0.5) * 4);
  if (pct < 0.9)  return new THREE.Color().lerpColors(new THREE.Color(0xef9f27), new THREE.Color(0xe24b4a), (pct - 0.75) * 6.7);
  return new THREE.Color(0xe24b4a);
}

export default function SARViewer({ projectId }: { projectId: string }) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene>();
  const [pointCount, setPointCount] = useState(0);
  const [maxSAR, setMaxSAR] = useState(0);

  useEffect(() => {
    if (!mountRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    const camera = new THREE.PerspectiveCamera(60, mountRef.current.clientWidth / 400, 0.1, 1000);
    camera.position.set(25, 20, 30);
    camera.lookAt(0, 0, 5);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mountRef.current.clientWidth, 400);
    mountRef.current.appendChild(renderer.domElement);

    // Phantom body outline (simple box)
    const phantomGeo = new THREE.BoxGeometry(20, 30, 10);
    const phantomMat = new THREE.MeshBasicMaterial({ color: 0x888888, wireframe: true, opacity: 0.15, transparent: true });
    scene.add(new THREE.Mesh(phantomGeo, phantomMat));

    // Animate
    let animId: number;
    const animate = () => { animId = requestAnimationFrame(animate); renderer.render(scene, camera); };
    animate();

    // Cleanup
    return () => {
      cancelAnimationFrame(animId);
      renderer.dispose();
      mountRef.current?.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_API_URL}/api/projects/${projectId}/events`;
    const es = new EventSource(url);

    es.addEventListener("sar_measurement", (e: MessageEvent) => {
      const point: SARPoint = JSON.parse(e.data);
      if (!sceneRef.current) return;

      const geo = new THREE.SphereGeometry(point.is_anomaly ? 0.4 : 0.15, 6, 6);
      const mat = new THREE.MeshBasicMaterial({ color: sarToColor(point.pct_of_limit) });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(point.x, point.z * 3, point.y);
      sceneRef.current.add(mesh);

      setPointCount(p => p + 1);
      setMaxSAR(m => Math.max(m, point.sar_w_kg));
    });

    return () => es.close();
  }, [projectId]);

  return (
    <div>
      <div ref={mountRef} className="w-full rounded-lg overflow-hidden" />
      <div className="flex gap-6 mt-3 text-sm text-gray-600">
        <span>Points scanned: <strong>{pointCount.toLocaleString()}</strong></span>
        <span>Peak SAR: <strong className={maxSAR > 1.44 ? "text-red-600" : "text-green-600"}>{maxSAR.toFixed(3)} W/kg</strong></span>
        <span>FCC limit: <strong>1.6 W/kg</strong></span>
      </div>
      <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
        <span className="w-4 h-2 rounded" style={{background: "#3b8bd4"}} /> Safe
        <span className="w-4 h-2 rounded ml-2" style={{background: "#ef9f27"}} /> Caution
        <span className="w-4 h-2 rounded ml-2" style={{background: "#e24b4a"}} /> Near limit
      </div>
    </div>
  );
}
```

---

### Step 4 — Webcam Panel

```typescript
// components/WebcamPanel.tsx
"use client";
import { useEffect, useRef, useState } from "react";

type Annotation = { issue: string; severity: string; bbox: number[] };

export default function WebcamPanel() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket>();
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [status, setStatus] = useState<"idle"|"valid"|"invalid">("idle");

  useEffect(() => {
    // Start webcam
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(stream => { if (videoRef.current) videoRef.current.srcObject = stream; });

    // Connect to live service
    const ws = new WebSocket(`${process.env.NEXT_PUBLIC_LIVE_URL}/webcam`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "setup_valid") { setStatus("valid"); setAnnotations([]); }
      if (msg.type === "setup_invalid") { setStatus("invalid"); }
      if (msg.type === "annotation") { setAnnotations(prev => [...prev.slice(-5), msg]); }
    };

    // Send frame every 2 seconds
    const interval = setInterval(() => {
      if (!videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN) return;
      const ctx = canvasRef.current.getContext("2d")!;
      canvasRef.current.width = 320;
      canvasRef.current.height = 240;
      ctx.drawImage(videoRef.current, 0, 0, 320, 240);
      ws.send(JSON.stringify({ type: "frame", data: canvasRef.current.toDataURL("image/jpeg", 0.7).split(",")[1] }));
    }, 2000);

    return () => { clearInterval(interval); ws.close(); };
  }, []);

  return (
    <div className="space-y-3">
      <div className="relative">
        <video ref={videoRef} autoPlay muted className="w-full rounded-lg" />
        <canvas ref={canvasRef} className="hidden" />
        <div className={`absolute top-2 right-2 px-2 py-1 rounded text-xs font-medium ${
          status === "valid" ? "bg-green-500 text-white" :
          status === "invalid" ? "bg-red-500 text-white" : "bg-gray-500 text-white"
        }`}>
          {status === "valid" ? "✓ Setup valid" : status === "invalid" ? "⚠ Issues found" : "Analyzing..."}
        </div>
      </div>
      {annotations.map((a, i) => (
        <div key={i} className={`p-2 rounded text-sm ${a.severity === "error" ? "bg-red-50 text-red-700" : "bg-yellow-50 text-yellow-700"}`}>
          {a.issue}
        </div>
      ))}
    </div>
  );
}
```

---

### Person 3 — Hour-by-Hour

| Time | Goal |
|---|---|
| 0:00–0:30 | Next.js setup, mock SSE server running on :8002 |
| 0:30–1:30 | AgentFeed consuming mock SSE, styled and working |
| 1:30–2:30 | Three.js SAR viewer rendering mock point cloud |
| 2:30–3:30 | Webcam panel + annotation overlays (mock WebSocket) |
| 3:30–4:30 | Project dashboard: intake form + all panels assembled |
| 4:30–5:00 | Flip `NEXT_PUBLIC_API_URL` to real backend (P1 ready by now) |
| 5:00–5:30 | Flip WebSocket to real live service (P2 ready by now) |
| 5:30–6:30 | Demo polish: animations, anomaly cards, report download |

---

---

## Integration Checkpoints

These are the only moments all three people need to coordinate (5 min each):

| Time | Checkpoint | What to verify |
|---|---|---|
| T+1:30h | Contract check | P1: POST /api/projects returns `{project_id, status}`. P3 can create a project. |
| T+3:00h | SSE live | P1 streaming SSE events. P3 flips mock → real for AgentFeed only. |
| T+4:30h | SAR stream | P1 simulator streaming SAR points. P3 Three.js viewer shows live points. |
| T+5:00h | Live service | P2 webcam endpoint ready. P3 WebcamPanel connects and shows annotations. |
| T+6:00h | Full run | All three services running. Full demo walkthrough once before submission. |

---

## Google AI Studio Feature Map

| Feature | Where Used | Why It Matters |
|---|---|---|
| **Gemini 3.5 Flash** | All agents | Intelligence layer |
| **Managed Agents API** | Orchestrator | Persistent state across phases |
| **Context Caching** | All jurisdiction + report agents | Regulatory corpus cached once, saves quota |
| **Live API (video)** | Webcam setup verifier | Native video understanding, not OCR |
| **Code Execution** | Report measurement agent | matplotlib charts from raw CSV |
| **File API** | Calibration cert storage | Cross-session document reference |
| **Search Grounding** | Jurisdiction agents | Live regulatory update awareness |
| **Parallel function calling** | Jurisdiction (5x) + Report (5x) | Two 5-agent parallel bursts |

---

## Demo Script (3 minutes)

**0:00–0:30** — "Every wireless device sold anywhere in the world must pass RF certification. The engineering work alone takes 2 weeks and costs $50,000. This is LabPilot."

**0:30–1:00** — Type device name + paste BOM. Hit submit. Watch 5 jurisdiction agents fire simultaneously in the feed. Certification matrix appears.

**1:00–1:30** — Point webcam at phone on desk. Watch Flash annotate the setup in real time. Adjust the phone. Watch it clear to green.

**1:30–2:30** — Start simulation. Watch Three.js heatmap build live. SAR values climb toward the antenna. At the anomaly cluster: Flash interrupts — "SAR 1.54 W/kg — 96% of limit. Recommend pausing."

**2:30–3:00** — Report assembles in parallel. 5 agents visible in feed simultaneously. PDF materializes. "This is what used to take 2 days."

---

## Environment Variables Reference

```env
# Shared (.env at root, each service copies what it needs)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
CACHE_NAME=                    # Set by Person 1 after running cache_loader.py

# Backend (Person 1)
PORT=8000

# Live Service (Person 2)
PORT=8001

# Frontend (Person 3)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_LIVE_URL=ws://localhost:8001
```

---

## Quick Start (all three, simultaneously)

```bash
# Terminal 1 — Person 1
cd backend && source venv/bin/activate
python cache_loader.py          # run once, save CACHE_NAME
uvicorn main:app --reload --port 8000

# Terminal 2 — Person 2
cd live-service && source venv/bin/activate
uvicorn main:app --reload --port 8001

# Terminal 3 — Person 3
cd frontend
npx ts-node mocks/mock-sse.ts   # during development
npm run dev                     # http://localhost:3000
```
