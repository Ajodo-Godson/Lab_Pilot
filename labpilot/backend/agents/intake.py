"""Intake managed agent — BOM text -> DeviceProfile."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Allow `from gemini_client import ...` when run via uvicorn from the backend dir.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent_runtime import invoke_agent_json
from models import DeviceProfile


async def run_intake(payload: dict[str, Any]) -> DeviceProfile:
    """
    payload comes from the POST /api/projects body:
      { device_name, bom_text, target_regions }
    """
    prompt = (
        "Parse the following BOM into a DeviceProfile JSON. Use Google Search "
        "if you need to look up an unfamiliar chip's RF type or power class.\n\n"
        f"DEVICE NAME (hint): {payload.get('device_name', 'unknown')}\n"
        f"TARGET REGIONS (hint): {payload.get('target_regions', [])}\n\n"
        f"BOM TEXT:\n{payload.get('bom_text', '')}\n"
    )
    raw = await invoke_agent_json("lp-intake", prompt)
    # Tolerate either raw dict or wrapped {"DeviceProfile": {...}}
    if "device_name" not in raw and len(raw) == 1:
        raw = next(iter(raw.values()))
    return DeviceProfile.model_validate(raw)
