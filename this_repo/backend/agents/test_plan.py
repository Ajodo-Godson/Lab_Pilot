"""Test plan managed agent — drafts a structured test plan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent_runtime import invoke_agent_json
from models import DeviceProfile, JurisdictionResult, TestPlanResult


async def run_test_plan(
    profile: DeviceProfile,
    cert_matrix: dict[str, JurisdictionResult],
) -> TestPlanResult:
    matrix_json = {r: cert_matrix[r].model_dump() for r in cert_matrix}
    prompt = (
        "Draft a test plan for this device that covers every required test "
        "across all jurisdictions in the certification matrix. Be specific "
        "about frequencies, body positions, and modes.\n\n"
        f"DEVICE PROFILE:\n{profile.model_dump_json(indent=2)}\n\n"
        f"CERTIFICATION MATRIX:\n{json.dumps(matrix_json, indent=2)}\n"
    )
    raw = await invoke_agent_json("lp-test-plan", prompt)
    return TestPlanResult.model_validate(raw)
