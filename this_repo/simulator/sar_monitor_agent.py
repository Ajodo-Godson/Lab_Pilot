from __future__ import annotations

import json
import os
import time
from collections import deque
from typing import Any

from fastapi import WebSocket

MONITOR_PROMPT = """
You are a real-time SAR safety monitor for RF certification testing.
FCC limit: 1.6 W/kg (1g tissue). Critical threshold: 90% = 1.44 W/kg.

Recent SAR readings:
{readings}

Analyze trend. Respond ONLY in JSON, no markdown:
{{
  "status": "ok" | "warning" | "critical",
  "trend": "rising" | "stable" | "falling",
  "message": "one sentence",
  "recommendation": "one action sentence"
}}

Flag warning if: 3+ consecutive readings rising AND latest > 1.2 W/kg.
Flag critical if: any reading > 1.44 W/kg.
"""


async def handle_sar_monitor(ws: WebSocket) -> None:
    """Monitor SAR data stream via WebSocket.

    Uses Gemini Flash when API key is available and readings are near the limit.
    Falls back to deterministic logic otherwise.
    """
    window: deque[dict[str, Any]] = deque(maxlen=8)
    last_model_call = 0.0
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    try:
        while True:
            point = await ws.receive_json()
            window.append(point)
            pct = float(point.get("pct_of_limit", 0))
            sar = float(point.get("sar_w_kg", 0))

            # Decide whether to call Gemini: only near risk, at most once every 1.5s
            should_call_gemini = (
                api_key
                and pct >= 0.75
                and time.monotonic() - last_model_call >= 1.5
            )

            if should_call_gemini:
                last_model_call = time.monotonic()
                result = await _call_gemini(api_key, model_name, list(window))

                if result:
                    if result["status"] == "critical":
                        await ws.send_json({
                            "type": "critical",
                            "message": result.get("message", f"SAR {sar:.2f} W/kg exceeds safety threshold."),
                            "recommendation": result.get("recommendation", "Pause scan and review."),
                        })
                    elif result["status"] == "warning":
                        await ws.send_json({
                            "type": "warning",
                            "message": result.get("message", f"SAR trending up: {sar:.2f} W/kg."),
                            "sar": sar,
                            "trend": result.get("trend", "rising"),
                        })
                    else:
                        await ws.send_json({"type": "ok", "sar": sar, "pct_of_limit": pct})
                else:
                    # Gemini call failed — fall back to deterministic
                    await _deterministic_response(ws, sar, pct)
            else:
                # Below threshold or rate-limited — use deterministic logic
                await _deterministic_response(ws, sar, pct)

    except Exception as e:
        print(f"SAR monitor connection closed: {e}")


async def _deterministic_response(ws: WebSocket, sar: float, pct: float) -> None:
    """Fallback deterministic monitor when Gemini is unavailable."""
    if pct >= 0.90:
        await ws.send_json({
            "type": "critical",
            "message": f"SAR {sar:.2f} W/kg is {pct * 100:.0f}% of the FCC limit.",
            "recommendation": "Pause scan and review antenna orientation.",
        })
    elif pct >= 0.75:
        await ws.send_json({
            "type": "warning",
            "message": f"SAR trend approaching FCC limit: {sar:.2f} W/kg.",
            "sar": sar,
            "trend": "rising",
        })
    else:
        await ws.send_json({"type": "ok", "sar": sar, "pct_of_limit": pct})


async def _call_gemini(api_key: str, model_name: str, readings: list[dict]) -> dict | None:
    """Call Gemini Flash for SAR trend analysis. Returns parsed JSON or None on failure."""
    import asyncio

    import google.generativeai as genai

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        prompt = MONITOR_PROMPT.format(readings=json.dumps(readings, indent=2))

        # Run in thread to avoid blocking the event loop
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = response.text.strip()

        # Strip markdown fences if present
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)

    except Exception as e:
        print(f"Gemini SAR monitor error: {e}")
        return None
