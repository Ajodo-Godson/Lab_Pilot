"""Five jurisdiction managed agents fanned out in parallel."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent_runtime import invoke_agent_json
from models import DeviceProfile, JurisdictionResult

REGIONS = ["fcc", "eu", "ca", "jp", "br"]

_REGION_MAP = {
    "fcc": {"US", "FCC"},
    "eu": {"EU"},
    "ca": {"CA", "ISED"},
    "jp": {"JP", "JAPAN"},
    "br": {"BR", "BRAZIL"},
}

def _is_region_targeted(region: str, target_regions: list[str]) -> bool:
    allowed = _REGION_MAP.get(region, set())
    targets = {t.upper() for t in target_regions}
    return bool(allowed.intersection(targets))


async def _run_one(region: str, profile: DeviceProfile) -> JurisdictionResult:
    if not _is_region_targeted(region, profile.target_regions):
        return JurisdictionResult(
            region=region,
            summary=f"Not requested: Region {region.upper()} is not in target regions.",
            required_tests=[],
            citations=[],
            estimated_hours=0
        )

    prompt = (
        "Analyze this DeviceProfile for your jurisdiction. Use the SKILL.md "
        "mounted in your environment as the authoritative reference. Use "
        "Google Search to verify any citation you are unsure about.\n\n"
        f"DEVICE PROFILE JSON:\n{profile.model_dump_json(indent=2)}\n"
    )
    raw = await invoke_agent_json(f"lp-jurisdiction-{region}", prompt)
    raw.setdefault("region", region)
    return JurisdictionResult.model_validate(raw)


async def run_jurisdiction_parallel(profile: DeviceProfile) -> dict[str, JurisdictionResult]:
    results = await asyncio.gather(*[_run_one(r, profile) for r in REGIONS])
    return {r.region: r for r in results}
