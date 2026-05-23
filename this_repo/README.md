# LabPilot V4 Initial Repo

Shared starter repo for the hackathon build.

## Ownership

| Area | Owner | Path | Port |
|---|---|---|---|
| AI core + compliance agents | Person 1 | `backend/` | `8000` |
| SAR simulator + monitor | Person 2 | `simulator/` | `8002` |
| Dashboard + vision UI | Person 3 | `frontend/` | `3000` |
| Shared contracts | Everyone | `contracts/` | - |

## Setup

Copy the unified env file. All three services read this root `.env`; the frontend loads it through `frontend/next.config.mjs`.

```powershell
Copy-Item .env.example .env
```

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Simulator:

```powershell
cd simulator
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Optional mock backend SSE for Person 3:

```powershell
cd frontend
npm run mock:sse
```

## Demo Flow

1. Create project with a BOM.
2. Start scope pipeline on backend.
3. Verify setup or use manual override.
4. Start simulator scan.
5. Frontend renders SAR points and forwards them to the SAR monitor.
6. On `scan_complete`, frontend sends `scan_summary` to `POST /api/projects/:id/report/generate`.
7. Backend report agents emit `report_ready`.

## Honest Framing

The hackathon scan is synthetic. The SAR values are physics-simulated, not physically measured. In production, the simulator stream would be replaced by DASY/cSAR/lab instrument exports.
