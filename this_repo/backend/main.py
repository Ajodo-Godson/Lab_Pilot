"""LabPilot backend (Person 1) — FastAPI :8000.

Endpoints (matching LABPILOT_V4 contracts):
  POST /api/projects                      create project
  POST /api/projects/{id}/scope           run intake + 5 jurisdictions + test plan
  POST /api/projects/{id}/report/generate run 5 report sections + PDF assembly
  GET  /api/projects/{id}/events          SSE stream of agent events
  GET  /api/projects/{id}/report          {pdf_base64, summary}

Streaming uses an asyncio.Queue per project. All agent work runs on the
Managed Agents API (Antigravity) via google-genai.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

# Load .env from this_repo/ before importing modules that read env vars.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from gemini_client import ensure_agents  # noqa: E402
from models import (  # noqa: E402
    CreateProjectRequest,
    GenerateReportRequest,
    ScanSummary,
)
from orchestrator import run_project, run_report_project  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Provision the 13 managed agents on startup. Idempotent.
    try:
        ids = await asyncio.to_thread(ensure_agents)
        print(f"[startup] managed agents ready: {len(ids)} agents")
    except Exception as exc:
        print(f"[startup] WARN — agent provisioning failed: {exc}")
    yield


app = FastAPI(title="LabPilot Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

projects: dict[str, dict[str, Any]] = {}
queues: dict[str, asyncio.Queue] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "labpilot-backend"}


@app.post("/api/projects")
async def create_project(body: CreateProjectRequest) -> dict[str, str]:
    project_id = str(uuid.uuid4())[:8]
    projects[project_id] = {
        "status": "created",
        "data": body.model_dump(),
        "artifacts": {},
        "report": None,
    }
    queues[project_id] = asyncio.Queue()
    return {"project_id": project_id, "status": "created"}


@app.post("/api/projects/{project_id}/scope")
async def start_scoping(project_id: str) -> dict[str, str]:
    project = _project_or_404(project_id)
    project["status"] = "scoping"
    asyncio.create_task(run_project(project_id, project, queues[project_id]))
    return {"project_id": project_id, "status": "scoping"}


@app.post("/api/projects/{project_id}/report/generate")
async def generate_report(project_id: str, body: GenerateReportRequest) -> dict[str, str]:
    project = _project_or_404(project_id)
    if not project.get("artifacts"):
        raise HTTPException(409, "Run /scope before generating a report.")
    project["scan_summary"] = body.scan_summary
    project["status"] = "reporting"
    asyncio.create_task(run_report_project(project_id, project, queues[project_id]))
    return {"project_id": project_id, "status": "reporting"}


@app.get("/api/projects/{project_id}/events")
async def event_stream(project_id: str) -> StreamingResponse:
    _project_or_404(project_id)

    async def generate():
        queue = queues[project_id]
        while True:
            event = await queue.get()
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["event"] == "report_ready":
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/projects/{project_id}/report")
async def get_report(project_id: str) -> JSONResponse:
    project = _project_or_404(project_id)
    report = project.get("report")
    if not report:
        raise HTTPException(404, "Report not ready.")
    return JSONResponse(
        {"pdf_base64": report.get("pdf_base64", ""), "summary": report.get("summary", "")}
    )


@app.get("/api/projects/{project_id}/state")
async def project_state(project_id: str) -> dict[str, Any]:
    """Debug endpoint for inspecting project status during development."""
    project = _project_or_404(project_id)
    return {
        "project_id": project_id,
        "status": project["status"],
        "has_artifacts": bool(project.get("artifacts")),
        "has_report": bool(project.get("report")),
    }


def _project_or_404(project_id: str) -> dict[str, Any]:
    project = projects.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    return project
