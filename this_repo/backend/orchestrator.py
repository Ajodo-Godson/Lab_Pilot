"""
Per-project orchestrator: drives the managed-agent pipeline and emits SSE
events into the project's queue.

Phase A: scope (intake -> 5 jurisdictions -> test plan)
Phase B: report (5 sections in parallel -> assembler -> PDF)
"""
from __future__ import annotations

import asyncio
import traceback
from typing import Any

from agents.intake import run_intake
from agents.jurisdiction import run_jurisdiction_parallel, REGIONS
from agents.report import (
    SECTION_AGENTS,
    run_report_assembler,
    run_report_parallel,
)
from agents.test_plan import run_test_plan
from models import ScanSummary


async def emit(queue: asyncio.Queue, event: str, data: dict[str, Any]) -> None:
    await queue.put({"event": event, "data": data})


async def run_project(project_id: str, project: dict[str, Any], queue: asyncio.Queue) -> None:
    try:
        data = project["data"]

        # ---- Intake ----
        await emit(queue, "agent_start", {"agent": "intake", "message": "Parsing device BOM..."})
        profile = await run_intake(data)
        await emit(
            queue,
            "agent_complete",
            {"agent": "intake", "output": profile.model_dump_json()[:300]},
        )

        # ---- 5 jurisdiction agents in parallel ----
        for region in REGIONS:
            await emit(
                queue,
                "agent_start",
                {
                    "agent": f"jurisdiction_{region}",
                    "message": f"Analyzing {region.upper()} requirements...",
                },
            )

        cert_matrix = await run_jurisdiction_parallel(profile)

        for region in REGIONS:
            output = cert_matrix[region].summary[:240]
            await emit(
                queue,
                "agent_complete",
                {"agent": f"jurisdiction_{region}", "output": output},
            )

        await emit(
            queue,
            "phase_complete",
            {
                "phase": "scoping",
                "summary": f"{len(cert_matrix)} jurisdictions analyzed",
            },
        )

        # ---- Test plan ----
        await emit(
            queue,
            "agent_start",
            {"agent": "test_plan", "message": "Drafting test plan with citations..."},
        )
        test_plan = await run_test_plan(profile, cert_matrix)
        await emit(
            queue,
            "agent_complete",
            {"agent": "test_plan", "output": test_plan.summary[:300]},
        )
        await emit(
            queue,
            "phase_complete",
            {"phase": "test_plan", "summary": "Test plan complete"},
        )

        project["artifacts"] = {
            "device_profile": profile,
            "cert_matrix": cert_matrix,
            "test_plan": test_plan,
        }
        project["status"] = "scoped"

    except Exception as exc:
        traceback.print_exc()
        await emit(
            queue,
            "phase_complete",
            {"phase": "scoping", "summary": f"ERROR: {exc}"},
        )
        project["status"] = "error"


async def run_report_project(
    project_id: str, project: dict[str, Any], queue: asyncio.Queue
) -> None:
    try:
        artifacts = project["artifacts"]
        scan_summary: ScanSummary = project["scan_summary"]

        # Announce all section agents starting in parallel.
        for agent in SECTION_AGENTS:
            short = agent.replace("lp-report-", "")
            await emit(
                queue,
                "agent_start",
                {
                    "agent": agent.replace("lp-", "").replace("-", "_"),
                    "message": f"Composing {short} section...",
                },
            )

        sections = await run_report_parallel(
            artifacts["device_profile"],
            artifacts["cert_matrix"],
            artifacts["test_plan"],
            scan_summary,
        )

        for agent in SECTION_AGENTS:
            key = agent.replace("lp-", "").replace("-", "_")
            preview = sections.get(key, "Section complete")[:200]
            await emit(queue, "agent_complete", {"agent": key, "output": preview})

        # Final assembler — Antigravity managed agent (with local fallback).
        await emit(
            queue,
            "agent_start",
            {
                "agent": "report_assembler",
                "message": "Compiling PDF (Antigravity managed agent + local fallback)...",
            },
        )
        report, source = await run_report_assembler(
            project_id,
            artifacts["device_profile"],
            artifacts["cert_matrix"],
            artifacts["test_plan"],
            sections,
            scan_summary,
        )
        await emit(
            queue,
            "agent_complete",
            {
                "agent": "report_assembler",
                "output": f"[{source}] {report.summary[:200]}",
            },
        )

        project["report"] = report.model_dump()
        project["report_source"] = source
        project["status"] = "report_ready"

        await emit(
            queue,
            "report_ready",
            {"download_url": f"/api/projects/{project_id}/report"},
        )

    except Exception as exc:
        traceback.print_exc()
        await emit(
            queue,
            "report_ready",
            {"download_url": "", "error": str(exc)},
        )
        project["status"] = "error"
