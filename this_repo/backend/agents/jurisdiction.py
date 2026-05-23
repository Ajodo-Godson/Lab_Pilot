from __future__ import annotations

import asyncio
from typing import Any


async def run_jurisdiction_parallel(device_profile: dict[str, Any]) -> dict[str, str]:
    regions = ["fcc", "eu", "ca", "jp", "br"]
    results = await asyncio.gather(*[_run_single(region, device_profile) for region in regions])
    return dict(zip(regions, results))


async def _run_single(region: str, device_profile: dict[str, Any]) -> str:
    await asyncio.sleep(0.4)
    labels = {
        "fcc": "FCC: Part 15.247 plus SAR evaluation under KDB 447498.",
        "eu": "EU: RED, EN 300 328, EN 62311 human exposure assessment.",
        "ca": "Canada: ISED RSS-247 and RSS-102 SAR evaluation.",
        "jp": "Japan: MIC/ARIB radio certification path.",
        "br": "Brazil: ANATEL homologation path.",
    }
    return f"{labels[region]} Device={device_profile.get('device_name')}. Placeholder result."
