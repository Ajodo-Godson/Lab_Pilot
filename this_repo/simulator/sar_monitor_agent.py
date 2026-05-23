from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import WebSocket


async def handle_sar_monitor(ws: WebSocket) -> None:
    window: deque[dict[str, Any]] = deque(maxlen=8)
    last_alert = 0.0

    while True:
        point = await ws.receive_json()
        window.append(point)
        pct = float(point.get("pct_of_limit", 0))
        sar = float(point.get("sar_w_kg", 0))

        # Placeholder deterministic monitor. Replace with Gemini when the API key/quota is ready.
        if pct >= 0.90 and time.monotonic() - last_alert >= 1.5:
            last_alert = time.monotonic()
            await ws.send_json(
                {
                    "type": "critical",
                    "message": f"SAR {sar:.2f} W/kg is {pct * 100:.0f}% of the FCC limit.",
                    "recommendation": "Pause scan and review antenna orientation.",
                }
            )
        elif pct >= 0.75 and time.monotonic() - last_alert >= 1.5:
            last_alert = time.monotonic()
            await ws.send_json(
                {
                    "type": "warning",
                    "message": f"SAR trend is approaching the FCC limit: {sar:.2f} W/kg.",
                    "sar": sar,
                    "trend": "rising",
                }
            )
        else:
            await ws.send_json({"type": "ok", "sar": sar, "pct_of_limit": pct})
