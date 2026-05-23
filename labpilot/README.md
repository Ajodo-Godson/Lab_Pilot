# LabPilot

**AI-powered RF/wireless certification testing automation platform.**

LabPilot is a full-stack application that uses Gemini AI agents to automate the regulatory compliance workflow for wireless devices. It combines a physics-based SAR (Specific Absorption Rate) digital twin simulator, multimodal vision for setup verification and device identification, and an 11-agent orchestration pipeline that produces certification-ready compliance reports.

## Key Features

- **Agentic Orchestration** -- 11 Gemini-powered agents (intake, 5 jurisdiction analysts, test plan author, 5 report section writers, PDF assembler) run in a fan-out pipeline via SSE streaming
- **Multi-Device Support** -- Automatically detects device type from BOM text (handset, tablet, wearable, laptop, IoT, speaker, gateway). No manual selection needed -- the intake agent classifies the device and the entire pipeline adapts
- **Physics-Based SAR Simulator** -- Volumetric grid scan with device-specific presets (grid bounds, phantom geometry, anomaly center, tissue depth), inverse-square SAR model with Gaussian hotspot gradients
- **Real-Time 3D Visualization** -- Three.js/React Three Fiber voxel heatmap with device-aware phantom meshes, IK-driven robot arm animation, and live color gradients (blue -> teal -> amber -> crimson)
- **Multimodal Vision** -- Gemini vision verifies probe/DUT positioning from webcam feed and can identify unknown devices (make, model, radios, form factor) from a single photo
- **Live SAR Monitor** -- WebSocket-connected Gemini agent watches SAR readings in real-time, issues warnings at 90% threshold, and triggers critical alerts with resolution recommendations
- **Automated PDF Reports** -- Multi-page compliance reports with matplotlib charts (peak SAR vs jurisdiction limits, anomaly scatter), per-jurisdiction pass/fail, and regulatory traceability citations
- **Managed Agents (Antigravity)** -- The report assembler uses Gemini Code Execution to autonomously render charts and compile the final PDF inside a sandboxed Linux environment

## Architecture

```
Frontend (Next.js :3000)          Backend (FastAPI :8000)         Simulator (FastAPI :8002)
+-----------------------+         +----------------------+        +---------------------+
| Dashboard             |--POST-->| /api/projects        |        |                     |
| AgentFeed (SSE)       |<--SSE---| /api/projects/:id/   |        | /api/simulator/     |
| SARViewport (Three.js)|--POST-->|   events             |        |   start (POST)      |
| WebcamPanel (Vision)  |         | Orchestrator         |        |   stream (SSE)      |
| VoxelCloud            |<--SSE---|   Intake agent       |        | /sar-monitor (WS)   |
| RobotArm (IK)        |--WS---->|   5x Jurisdiction    |        | sar_physics.py      |
+-----------------------+         |   Test plan          |        |   device presets     |
                                  |   5x Report sections |        |   anomaly injection  |
                                  |   PDF assembler      |        +---------------------+
                                  +----------------------+
```

## Device Type Detection Flow

1. User enters a BOM (bill of materials) description in the text area
2. The Gemini intake agent parses the BOM and classifies the device:
   - `form_factor`: handset, tablet, wearable, laptop, iot, speaker, gateway, other
   - `radios`: chip, type, frequency, power for each wireless radio
   - `body_worn`, `held_to_head`: usage classification
3. A `device_profile` SSE event streams the full profile to the frontend
4. The simulator adapts its grid geometry, anomaly center, and phantom shape per device type
5. The 3D viewport renders a device-appropriate mesh (phone slab, watch, tablet, laptop, etc.)
6. Radio frequency and power from the detected profile drive the SAR scan parameters
7. The PDF report uses device-specific phantom labels in charts and analysis

Alternatively, the webcam can identify a device visually using Gemini vision, populating the BOM automatically.

## Supported Device Types

| Form Factor | Phantom | Grid Size | Use Case |
|---|---|---|---|
| Handset | Flat body | 16x16x5 cm | Phones, portable radios |
| Tablet | Large flat | 20x28x4 cm | Tablets, e-readers |
| Wearable | Small body | 8x8x3 cm | Watches, patches, bands |
| Laptop | Wide flat | 28x20x4 cm | Laptops, portable PCs |
| IoT | Compact | 10x10x4 cm | Sensors, trackers, boards |
| Speaker | Desktop | 12x12x5 cm | Smart speakers, hubs |
| Gateway | Desktop | 12x12x5 cm | Routers, access points |

## Setup

```bash
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

**Backend (Terminal 1):**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --port 8000 --reload
```

**Simulator (Terminal 2):**

```bash
cd simulator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --port 8002 --reload
```

**Frontend (Terminal 3):**

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

## Demo Walkthrough

1. **Create Project** -- Enter a device BOM in the left panel and click "Create project + scope". The intake agent detects the device type and radios, then 5 jurisdiction agents analyze regulatory requirements in parallel.
2. **Verify Setup** -- Point your webcam at a device + probe. Gemini vision verifies positioning and estimates simulator parameters. Or use "Lock current setup" to skip.
3. **Start SAR Scan** -- Click "Initialize scan". The 3D viewport shows voxels streaming in with a color gradient that builds toward the anomaly cluster. The phantom and device mesh match the detected form factor.
4. **Watch for Anomalies** -- Around 70% through the scan, the planted anomaly fires. The SAR monitor issues a critical alert, which appears in both the center panel and the agent feed.
5. **Generate Report** -- After scan completes, click "Generate report". The backend assembles a multi-page PDF with charts, regulatory analysis, and per-jurisdiction pass/fail.

## Mock Mode

For frontend development without backend/simulator:

```bash
# In .env
NEXT_PUBLIC_MOCK_MODE=true

# Optional: run the mock SSE server
cd frontend && npm run mock:sse
```

## Health Checks

| Service | URL | Expected |
|---|---|---|
| Backend | http://localhost:8000/docs | FastAPI Swagger UI |
| Simulator | http://localhost:8002/docs | FastAPI Swagger UI |
| Frontend | http://localhost:3000 | LabPilot dashboard |

## Honest Framing

The SAR data is generated by a physics-based digital twin simulator and is not a substitute for a physical SPEAG DASY8 measurement campaign. The regulatory analysis, citations, test plan structure, and report assembly are produced by Gemini agents. In production, the simulator stream would be replaced by real lab instrument exports (DASY/cSAR).

## Tech Stack

- **Frontend**: Next.js 16, React, Three.js, React Three Fiber, TypeScript
- **Backend**: Python, FastAPI, Google Gemini (genai SDK), Pydantic, ReportLab, Matplotlib
- **Simulator**: Python, FastAPI, NumPy, WebSocket SAR monitor with Gemini Live API
- **AI**: Gemini 3.5 Flash (11 agents), Managed Agents / Antigravity (PDF assembly), Multimodal Vision (setup verification + device identification)
