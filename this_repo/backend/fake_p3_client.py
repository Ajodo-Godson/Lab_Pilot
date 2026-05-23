"""
Fake Person-3 client.

Drives the entire backend pipeline against a running uvicorn :8000 instance
and writes the final PDF to ./outputs/<project_id>.pdf.

Usage (in a separate terminal while uvicorn is running):
  python fake_p3_client.py
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import requests

BACKEND = "http://localhost:8000"
OUT_DIR = Path(__file__).parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)

# V4 mock device — SmartPatch X1.
DEMO_BOM = """\
SmartPatch X1 — Bill of Materials
- Nordic nRF52840 (BLE, 2.402-2.480 GHz, 0 dBm typical, +8 dBm max)
- Realtek RTL8723DE (Wi-Fi 2.4 GHz + BLE combo, 20 dBm Wi-Fi)
- Battery: 200 mAh LiPo, body-worn skin patch form factor
- Enclosure: medical-grade silicone, designed to be worn within 5 mm of skin
- Antenna: PIFA, integrated, no external connector
"""

DEMO_REQUEST = {
    "device_name": "SmartPatch X1",
    "bom_text": DEMO_BOM,
    "target_regions": ["US", "EU", "CA", "JP", "BR"],
}

# After a real P2 scan would run, P3 normally collects this from /scan_complete.
# For local Person-1-only testing we synthesize the V4 climax anomaly.
DEMO_SCAN_SUMMARY = {
    "peak_sar": 1.54,
    "anomaly_count": 3,
    "total_points": 2890,
    "anomalies": [
        {"position": [8.2, 4.4, 3.0], "sar": 1.54},
        {"position": [8.0, 4.6, 3.0], "sar": 1.50},
        {"position": [8.4, 4.2, 3.0], "sar": 1.49},
    ],
}


def _post(path: str, body: dict | None = None) -> dict:
    resp = requests.post(f"{BACKEND}{path}", json=body or {}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> dict:
    resp = requests.get(f"{BACKEND}{path}", timeout=60)
    resp.raise_for_status()
    return resp.json()


def _stream_events(project_id: str, until_event: str) -> None:
    """Tail the SSE stream until we see a specific event."""
    url = f"{BACKEND}/api/projects/{project_id}/events"
    with requests.get(url, stream=True, timeout=None) as resp:
        resp.raise_for_status()
        current_event = None
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if raw.startswith("event: "):
                current_event = raw[7:].strip()
            elif raw.startswith("data: "):
                data = raw[6:]
                print(f"  [{current_event}] {data[:160]}")
                if current_event == until_event:
                    return


def main() -> int:
    print("=== LabPilot end-to-end test (Person 1 backend only) ===\n")

    # 1. Health check
    health = _get("/health")
    print(f"[health] {health}\n")

    # 2. Create project
    print("[1/4] POST /api/projects ...")
    created = _post("/api/projects", DEMO_REQUEST)
    project_id = created["project_id"]
    print(f"  project_id = {project_id}\n")

    # 3. Kick off scope (intake + 5 jurisdictions + test plan).
    print("[2/4] POST /api/projects/{id}/scope ...")
    _post(f"/api/projects/{project_id}/scope")

    # We can't yet tail-then-also-trigger-report on the same SSE response, so
    # we open the SSE stream after every trigger separately. Practical
    # workaround: read the queue twice — once for scoping, once for report.
    # In the real frontend, the connection stays open.
    print("[2/4] streaming events until phase_complete(test_plan)...")
    _stream_until_phase(project_id, want_phase="test_plan")

    # 4. Trigger report.
    print("\n[3/4] POST /api/projects/{id}/report/generate ...")
    _post(f"/api/projects/{project_id}/report/generate", {"scan_summary": DEMO_SCAN_SUMMARY})

    print("[3/4] streaming events until report_ready ...")
    _stream_until_event(project_id, "report_ready")

    # 5. Fetch the PDF.
    print("\n[4/4] GET /api/projects/{id}/report ...")
    report = _get(f"/api/projects/{project_id}/report")
    summary = report.get("summary", "")
    pdf_b64 = report.get("pdf_base64", "")
    print(f"  summary: {summary[:300]}")
    print(f"  pdf_base64 length: {len(pdf_b64)} chars")

    if pdf_b64:
        pdf_path = OUT_DIR / f"{project_id}.pdf"
        pdf_path.write_bytes(base64.b64decode(pdf_b64))
        size_kb = pdf_path.stat().st_size / 1024
        print(f"\n  PDF saved to: {pdf_path} ({size_kb:.1f} KB)")
    else:
        print("\n  WARNING: no PDF returned. Check server logs for errors.")

    print("\n=== DONE ===")
    return 0


def _stream_until_event(project_id: str, until: str) -> None:
    url = f"{BACKEND}/api/projects/{project_id}/events"
    with requests.get(url, stream=True, timeout=None) as resp:
        resp.raise_for_status()
        current_event = None
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if raw.startswith("event: "):
                current_event = raw[7:].strip()
            elif raw.startswith("data: "):
                data = raw[6:]
                print(f"    [{current_event}] {data[:140]}")
                if current_event == until:
                    return


def _stream_until_phase(project_id: str, want_phase: str) -> None:
    """Like _stream_until_event but stops at a specific phase_complete payload."""
    url = f"{BACKEND}/api/projects/{project_id}/events"
    with requests.get(url, stream=True, timeout=None) as resp:
        resp.raise_for_status()
        current_event = None
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if raw.startswith("event: "):
                current_event = raw[7:].strip()
            elif raw.startswith("data: "):
                data = raw[6:]
                print(f"    [{current_event}] {data[:140]}")
                if current_event == "phase_complete":
                    try:
                        payload = json.loads(data)
                        if payload.get("phase") == want_phase:
                            return
                    except json.JSONDecodeError:
                        pass


if __name__ == "__main__":
    sys.exit(main())
