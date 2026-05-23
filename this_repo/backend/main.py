from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from orchestrator import run_project, run_report_project

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="LabPilot Backend")
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
    return {"status": "ok", "service": "backend"}


@app.post("/api/projects")
async def create_project(body: dict[str, Any]) -> dict[str, str]:
    project_id = str(uuid.uuid4())[:8]
    projects[project_id] = {
        "status": "created",
        "data": body,
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
async def generate_report(project_id: str, body: dict[str, Any]) -> dict[str, str]:
    project = _project_or_404(project_id)
    if not project.get("artifacts"):
        raise HTTPException(status_code=409, detail="Run /scope before generating a report.")
    if "scan_summary" not in body:
        raise HTTPException(status_code=400, detail="Missing scan_summary.")
    project["scan_summary"] = body["scan_summary"]
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
        raise HTTPException(status_code=404, detail="Report not ready.")
    return JSONResponse(report)


def _project_or_404(project_id: str) -> dict[str, Any]:
    project = projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project
