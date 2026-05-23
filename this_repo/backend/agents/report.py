from __future__ import annotations

import asyncio
from typing import Any


async def run_report_parallel(
    test_plan: str,
    device_profile: dict[str, Any],
    scan_summary: dict[str, Any],
) -> dict[str, str]:
    agents = [
        "report_setup",
        "report_measurement",
        "report_citer",
        "report_narrator",
        "report_compliance",
    ]
    results = await asyncio.gather(*[_section(agent, test_plan, device_profile, scan_summary) for agent in agents])
    return dict(zip(agents, results))


async def _section(
    agent: str,
    test_plan: str,
    device_profile: dict[str, Any],
    scan_summary: dict[str, Any],
) -> str:
    await asyncio.sleep(0.25)
    peak = scan_summary.get("peak_sar", "N/A")
    anomalies = scan_summary.get("anomaly_count", 0)
    return (
        f"{agent}: placeholder section for {device_profile.get('device_name')}. "
        f"Simulated peak SAR={peak} W/kg, anomalies={anomalies}. "
        "Replace with Gemini report agent."
    )
