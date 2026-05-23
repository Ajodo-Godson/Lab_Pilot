"""SAR Monitor using Gemini Live API for real-time bidirectional streaming.

Stretch goal implementation. The Live API maintains a persistent WebSocket
session to Gemini, enabling lower-latency responses compared to individual
generate_content calls.

Current limitation: gemini-3.1-flash-live-preview only supports AUDIO response
modality. For our text-based SAR monitoring, we use send_client_content to seed
context and send_realtime_input for text updates. If the Live API model doesn't
support our use case, we fall back gracefully to the standard generate_content
approach (which already works well for the demo).

The architecture is ready for when text-only Live API sessions become available.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from typing import Any

from fastapi import WebSocket

# Try importing the genai SDK; if unavailable, Live API won't be used
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

SYSTEM_INSTRUCTION = """You are a real-time SAR safety monitor for RF certification testing.
FCC limit: 1.6 W/kg (1g tissue). Critical threshold: 90% = 1.44 W/kg.

You will receive batches of SAR measurement points. Analyze the trend and respond
with a brief spoken assessment:
- If any reading > 1.44 W/kg: say CRITICAL with the value and recommend pausing
- If readings are rising and latest > 1.2 W/kg: say WARNING with the trend
- Otherwise: say readings are nominal
Keep responses to one sentence.
"""


async def handle_sar_monitor_live(ws: WebSocket) -> None:
    """Monitor SAR data using Gemini Live API with fallback.

    Attempts to establish a Live API session for lower-latency monitoring.
    If the Live API is unavailable or the model doesn't support our modality,
    falls back to the standard generate_content approach.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not HAS_GENAI:
        await _run_deterministic(ws)
        return

    model_name = "gemini-3.1-flash-live-preview"
    client = genai.Client(api_key=api_key)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_INSTRUCTION,
        output_audio_transcription={},
    )

    window: deque[dict[str, Any]] = deque(maxlen=8)
    last_send_time = 0.0

    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            print("Live API session established for SAR monitoring")

            # Background task to collect transcription responses
            response_queue: asyncio.Queue[str] = asyncio.Queue()

            async def receive_responses():
                try:
                    async for response in session.receive():
                        content = response.server_content
                        if content and content.output_transcription:
                            text = content.output_transcription.text
                            if text and text.strip():
                                await response_queue.put(text.strip())
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Live API receive error: {e}")

            recv_task = asyncio.create_task(receive_responses())

            try:
                while True:
                    point = await ws.receive_json()
                    window.append(point)
                    pct = float(point.get("pct_of_limit", 0))
                    sar = float(point.get("sar_w_kg", 0))

                    should_send = (
                        pct >= 0.75
                        and time.monotonic() - last_send_time >= 1.0
                    )

                    if should_send:
                        last_send_time = time.monotonic()
                        readings_text = json.dumps(list(window), indent=1)

                        # Send text as realtime input
                        await session.send_realtime_input(
                            text=f"SAR batch: {readings_text}"
                        )

                        # Wait for transcription
                        try:
                            transcript = await asyncio.wait_for(
                                response_queue.get(), timeout=3.0
                            )
                            lower = transcript.lower()
                            if "critical" in lower:
                                await ws.send_json({
                                    "type": "critical",
                                    "message": transcript,
                                    "recommendation": "Pause scan and review antenna orientation.",
                                })
                            elif "warning" in lower:
                                await ws.send_json({
                                    "type": "warning",
                                    "message": transcript,
                                    "sar": sar,
                                    "trend": "rising",
                                })
                            else:
                                await ws.send_json({"type": "ok", "sar": sar, "pct_of_limit": pct})
                        except asyncio.TimeoutError:
                            await _send_deterministic(ws, sar, pct)
                    else:
                        await _send_deterministic(ws, sar, pct)

            finally:
                recv_task.cancel()

    except Exception as e:
        print(f"Live API unavailable ({type(e).__name__}): falling back to generate_content monitor.")
        # Fall back to the standard generate_content approach
        await _run_with_generate_content(ws, api_key, window)


async def _run_with_generate_content(
    ws: WebSocket,
    api_key: str,
    initial_window: deque[dict[str, Any]],
) -> None:
    """Fallback: use standard generate_content calls (same as sar_monitor_agent)."""
    import google.generativeai as genai_legacy

    genai_legacy.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    model = genai_legacy.GenerativeModel(model_name)

    window = initial_window
    last_call = 0.0

    prompt_template = """You are a real-time SAR safety monitor.
FCC limit: 1.6 W/kg. Critical threshold: 90% = 1.44 W/kg.

Recent readings:
{readings}

Respond ONLY in JSON:
{{"status": "ok"|"warning"|"critical", "trend": "rising"|"stable"|"falling", "message": "one sentence", "recommendation": "one action"}}
"""

    try:
        while True:
            point = await ws.receive_json()
            window.append(point)
            pct = float(point.get("pct_of_limit", 0))
            sar = float(point.get("sar_w_kg", 0))

            should_call = (
                pct >= 0.75
                and time.monotonic() - last_call >= 1.5
            )

            if should_call:
                last_call = time.monotonic()
                prompt = prompt_template.format(readings=json.dumps(list(window), indent=2))
                try:
                    response = await asyncio.to_thread(model.generate_content, prompt)
                    text = response.text.strip()
                    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    result = json.loads(text)

                    if result["status"] == "critical":
                        await ws.send_json({
                            "type": "critical",
                            "message": result.get("message", f"SAR {sar:.2f} W/kg exceeds threshold."),
                            "recommendation": result.get("recommendation", "Pause scan."),
                        })
                    elif result["status"] == "warning":
                        await ws.send_json({
                            "type": "warning",
                            "message": result.get("message", f"SAR rising: {sar:.2f} W/kg."),
                            "sar": sar,
                            "trend": result.get("trend", "rising"),
                        })
                    else:
                        await ws.send_json({"type": "ok", "sar": sar, "pct_of_limit": pct})
                except Exception:
                    await _send_deterministic(ws, sar, pct)
            else:
                await _send_deterministic(ws, sar, pct)

    except Exception as e:
        print(f"SAR monitor (generate_content) closed: {e}")


async def _run_deterministic(ws: WebSocket) -> None:
    """Full deterministic monitor loop."""
    try:
        while True:
            point = await ws.receive_json()
            pct = float(point.get("pct_of_limit", 0))
            sar = float(point.get("sar_w_kg", 0))
            await _send_deterministic(ws, sar, pct)
    except Exception as e:
        print(f"SAR monitor connection closed: {e}")


async def _send_deterministic(ws: WebSocket, sar: float, pct: float) -> None:
    """Send a single deterministic response."""
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
