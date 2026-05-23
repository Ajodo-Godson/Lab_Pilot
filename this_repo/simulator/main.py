from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from sar_monitor_agent import handle_sar_monitor
from sar_physics import stream_sar_grid

# Load .env from project root (Lab_Pilot/) or this_repo/
_here = Path(__file__).resolve().parent
for _candidate in [_here.parent / ".env", _here.parents[1] / ".env"]:
    if _candidate.exists():
        load_dotenv(_candidate)
        break

app = FastAPI(title="LabPilot Simulator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sim_queue: asyncio.Queue = asyncio.Queue()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "simulator"}


@app.post("/api/simulator/start")
async def start_sim(body: dict[str, Any]) -> dict[str, str]:
    global sim_queue
    sim_queue = asyncio.Queue()
    asyncio.create_task(stream_sar_grid(body, sim_queue))
    return {"status": "streaming"}


@app.get("/api/simulator/stream")
async def sim_stream() -> StreamingResponse:
    async def generate():
        while True:
            event = await sim_queue.get()
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["event"] == "scan_complete":
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.websocket("/sar-monitor")
async def sar_monitor_ws(ws: WebSocket) -> None:
    await ws.accept()
    await handle_sar_monitor(ws)
