"""
Report agents.

5 parallel section writers (direct Flash) + 1 Antigravity assembler.
The assembler tries Antigravity first; if it fails, errors out, or returns
unparseable JSON, we fall back to a deterministic local PDF builder.

The local fallback exists so the demo NEVER fails on stage. The Antigravity
path is the differentiator that supports the "best use of managed agents" pitch.
"""
from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent_runtime import (
    download_environment_file,
    invoke_agent,
    invoke_agent_text,
    parse_json,
)
from models import (
    DeviceProfile,
    FinalReport,
    JurisdictionResult,
    ScanSummary,
    TestPlanResult,
)
from pdf_builder import build_pdf

SECTION_AGENTS = [
    "lp-report-setup",
    "lp-report-measurement",
    "lp-report-citer",
    "lp-report-narrator",
    "lp-report-compliance",
]


async def _section(agent_id: str, base_prompt: str) -> tuple[str, str]:
    text = await invoke_agent_text(agent_id, base_prompt)
    key = agent_id.replace("lp-", "").replace("-", "_")
    return key, text


async def run_report_parallel(
    profile: DeviceProfile,
    cert_matrix: dict[str, JurisdictionResult],
    test_plan: TestPlanResult,
    scan_summary: ScanSummary,
) -> dict[str, str]:
    matrix_json = {r: cert_matrix[r].model_dump() for r in cert_matrix}
    base_prompt = (
        "Compose your assigned section of the compliance report. Be honest "
        "that the SAR data is from a physics-based digital twin simulator "
        "(LabPilot), not a physical SPEAG DASY8 scan.\n\n"
        f"DEVICE PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"TEST PLAN:\n{test_plan.model_dump_json(indent=2)}\n\n"
        f"CERTIFICATION MATRIX:\n{json.dumps(matrix_json, indent=2)}\n\n"
        f"SCAN SUMMARY:\n{scan_summary.model_dump_json(indent=2)}\n"
    )
    results = await asyncio.gather(*[_section(a, base_prompt) for a in SECTION_AGENTS])
    return dict(results)


async def run_report_assembler(
    project_id: str,
    profile: DeviceProfile,
    cert_matrix: dict[str, JurisdictionResult],
    test_plan: TestPlanResult,
    sections: dict[str, str],
    scan_summary: ScanSummary,
) -> tuple[FinalReport, str]:
    """
    Returns (FinalReport, source_label).
    source_label is "antigravity" or "local_fallback" so we can surface it
    in SSE / logs.
    """
    matrix_json = {r: cert_matrix[r].model_dump() for r in cert_matrix}
    payload_dict = {
        "project_id": project_id,
        "device_profile": profile.model_dump(),
        "cert_matrix": matrix_json,
        "test_plan": test_plan.model_dump(),
        "sections": sections,
        "scan_summary": scan_summary.model_dump(),
    }
    payload_json = json.dumps(payload_dict, indent=2)

    # 1. Try Antigravity managed agent (with hard timeout — Tier 1 sometimes
    # hangs the assembler for minutes due to TPM throttling. We never let that
    # block the demo.)
    try:
        prompt = (
            "Render the final compliance PDF for this project per your system "
            "instructions. The full payload follows.\n\n"
            f"PAYLOAD:\n{payload_json}\n"
        )
        interaction = await asyncio.wait_for(
            invoke_agent("lp-report-assembler", prompt),
            timeout=45.0,
        )
        try:
            parsed = parse_json(interaction.output_text)
            pdf_b64 = parsed.get("pdf_base64", "")
            summary = parsed.get("summary", "")
            if pdf_b64:
                return FinalReport(
                    pdf_base64=pdf_b64, summary=summary, sections=sections
                ), "antigravity"
        except Exception:
            pass
        # Try to download from sandbox snapshot.
        try:
            pdf_bytes = download_environment_file(interaction.environment_id, "report.pdf")
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
            return FinalReport(
                pdf_base64=pdf_b64,
                summary="Report assembled by Antigravity managed agent (Code Execution).",
                sections=sections,
            ), "antigravity"
        except Exception as snap_exc:
            print(f"[report] antigravity snapshot path failed: {snap_exc}")
    except asyncio.TimeoutError:
        print("[report] antigravity timed out after 45s — using local fallback")
    except Exception as exc:
        print(f"[report] antigravity invocation failed: {exc}")

    # 2. Local fallback.
    pdf_b64, summary = build_pdf(
        project_id=project_id,
        profile=profile.model_dump(),
        cert_matrix=matrix_json,
        test_plan=test_plan.model_dump(),
        sections=sections,
        scan_summary=scan_summary.model_dump(),
    )
    return FinalReport(
        pdf_base64=pdf_b64, summary=summary, sections=sections
    ), "local_fallback"
