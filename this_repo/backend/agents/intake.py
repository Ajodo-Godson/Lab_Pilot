from __future__ import annotations

import asyncio
from typing import Any


async def run_intake(data: dict[str, Any]) -> dict[str, Any]:
    await asyncio.sleep(0.2)
    bom_text = data.get("bom_text", "")
    return {
        "device_name": data.get("device_name", "SmartPatch X1"),
        "target_regions": data.get("target_regions", ["US", "EU", "CA"]),
        "body_worn": "wearable" in bom_text.lower() or "body_worn" in bom_text.lower(),
        "radios": ["BLE", "WiFi"],
        "notes": "Placeholder intake. Replace with Gemini structured extraction.",
    }
