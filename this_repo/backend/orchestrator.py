from __future__ import annotations

import asyncio
from typing import Any

from agents.intake import run_intake
from agents.jurisdiction import run_jurisdiction_parallel
from agents.report import run_report_parallel
from agents.test_plan import run_test_plan


async def emit(queue: asyncio.Queue, event: str, data: dict[str, Any]) -> None:
    await queue.put({"event": event, "data": data})


async def run_project(project_id: str, project: dict[str, Any], queue: asyncio.Queue) -> None:
    data = project["data"]

    await emit(queue, "agent_start", {"agent": "intake", "message": "Parsing device BOM..."})
    device_profile = await run_intake(data)
    await emit(queue, "agent_complete", {"agent": "intake", "output": str(device_profile)[:300]})

    regions = ["fcc", "eu", "ca", "jp", "br"]
    for region in regions:
        await emit(
            queue,
            "agent_start",
            {"agent": f"jurisdiction_{region}", "message": f"Analyzing {region.upper()} requirements..."},
        )

    cert_matrix = await run_jurisdiction_parallel(device_profile)

    for region in regions:
        await emit(
            queue,
            "agent_complete",
            {"agent": f"jurisdiction_{region}", "output": cert_matrix.get(region, "")[:200]},
        )

    await emit(queue, "phase_complete", {"phase": "scoping", "summary": "5 jurisdictions analyzed"})

    await emit(queue, "agent_start", {"agent": "test_plan", "message": "Drafting test plan with citations..."})
    test_plan = await run_test_plan(device_profile, cert_matrix)
    await emit(queue, "agent_complete", {"agent": "test_plan", "output": test_plan[:300]})
    await emit(queue, "phase_complete", {"phase": "test_plan", "summary": "Test plan complete"})

    project["artifacts"] = {
        "device_profile": device_profile,
        "cert_matrix": cert_matrix,
        "test_plan": test_plan,
    }
    project["status"] = "scoped"


async def run_report_project(project_id: str, project: dict[str, Any], queue: asyncio.Queue) -> None:
    artifacts = project["artifacts"]
    scan_summary = project["scan_summary"]

    report_agents = [
        "report_setup",
        "report_measurement",
        "report_citer",
        "report_narrator",
        "report_compliance",
    ]
    for agent in report_agents:
        await emit(queue, "agent_start", {"agent": agent, "message": f"Composing {agent.replace('report_', '')} section..."})

    sections = await run_report_parallel(
        artifacts["test_plan"],
        artifacts["device_profile"],
        scan_summary,
    )

    for agent in report_agents:
        await emit(queue, "agent_complete", {"agent": agent, "output": sections.get(agent, "Section complete")[:240]})

    project["report"] = {
        "pdf_base64": "",
        "summary": "Placeholder report generated from simulated SAR scan summary.",
        "sections": sections,
    }
    project["status"] = "report_ready"
    await emit(queue, "report_ready", {"download_url": f"/api/projects/{project_id}/report"})
