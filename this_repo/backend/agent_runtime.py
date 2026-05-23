"""
Hybrid agent runtime for LabPilot.

Routing rules:
  * MOCK_AGENTS=true       -> all agents return deterministic stubs (no API calls)
  * agent id "lp-report-assembler" -> Antigravity managed agent (Code Execution)
  * everything else        -> direct Gemini Flash call (cheap, parallel-safe)

This gives us:
  - 11 fast, cheap Flash calls for the agentic fan-out (intake, 5 jurisdictions,
    test plan, 5 report sections)
  - 1 Antigravity call for autonomous PDF assembly inside a Linux sandbox

The "best use of managed agents" pitch is honest: we use Antigravity exactly
where it earns its keep, and standard Flash everywhere else.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tarfile
from typing import Any

import requests

from gemini_client import get_client

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL)
_FLASH_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_MANAGED_AGENT_IDS = {"lp-report-assembler"}  # the only Antigravity invocation


def _strip_fences(text: str) -> str:
    text = text.strip()
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def parse_json(text: str) -> Any:
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"[parse_json] ERROR: {exc}\n--- ORIGINAL TEXT ---\n{text}\n--- CLEANED TEXT ---\n{cleaned}\n-------------------")
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as exc2:
                print(f"[parse_json] Fallback failed: {exc2}")
        raise


def _use_mock() -> bool:
    return os.getenv("MOCK_AGENTS", "false").lower() == "true"


# --------------------------- Mock outputs --------------------------- #

_MOCK_OUTPUTS: dict[str, str] = {
    "lp-intake": json.dumps({
        "device_name": "SmartPatch X1",
        "form_factor": "wearable",
        "body_worn": True,
        "radios": [
            {"chip": "Nordic nRF52840", "type": "BLE", "freq_mhz": 2440, "power_dbm": 8},
            {"chip": "Realtek RTL8723DE", "type": "WiFi+BT", "freq_mhz": 2412, "power_dbm": 20},
        ],
        "target_regions": ["US", "EU", "CA", "JP", "BR"],
        "notes": "Body-worn wearable, both radios in 2.4 GHz ISM band.",
    }),
    "lp-jurisdiction-fcc": json.dumps({
        "region": "fcc",
        "summary": "FCC Part 15.247 plus SAR per KDB 447498 for body-worn portable.",
        "required_tests": ["RF Power", "OBW", "Spurious", "SAR (1g)", "EMC"],
        "citations": ["47 CFR 15.247", "47 CFR 2.1093", "KDB 447498 D01", "OET-65"],
        "estimated_hours": 64,
    }),
    "lp-jurisdiction-eu": json.dumps({
        "region": "eu",
        "summary": "EU RED 2014/53/EU. EN 300 328, EN 62311 / EN 50566 for SAR.",
        "required_tests": ["EN 300 328", "EN 301 489-17 EMC", "SAR (10g)"],
        "citations": ["Directive 2014/53/EU", "EN 300 328 v2.2.2", "EN 62311:2020", "EN 50566"],
        "estimated_hours": 72,
    }),
    "lp-jurisdiction-ca": json.dumps({
        "region": "ca",
        "summary": "ISED RSS-247 + RSS-102 for body-worn at 1.6 W/kg over 1g.",
        "required_tests": ["RSS-247", "RSS-Gen", "RSS-102 SAR"],
        "citations": ["RSS-247 Issue 2", "RSS-102 Issue 6", "RSS-Gen Issue 5"],
        "estimated_hours": 48,
    }),
    "lp-jurisdiction-jp": json.dumps({
        "region": "jp",
        "summary": "Japan MIC Giteki via ARIB STD-T66 plus SAR per MIC Notice 173.",
        "required_tests": ["ARIB STD-T66", "MIC Ordinance 88", "SAR (10g)"],
        "citations": ["ARIB STD-T66", "MIC Ordinance 88", "MIC Notice 173"],
        "estimated_hours": 40,
    }),
    "lp-jurisdiction-br": json.dumps({
        "region": "br",
        "summary": "ANATEL Cat II homologation, Resolution 715/2019, SAR via Resolution 442.",
        "required_tests": ["Cat II RF tests", "SAR per Resolution 442"],
        "citations": ["Resolution 715/2019", "Act 14448/2017", "Resolution 442/2006"],
        "estimated_hours": 32,
    }),
    "lp-test-plan": json.dumps({
        "summary": (
            "Test plan covers 2 radios in the 2.4 GHz ISM band across 5 jurisdictions. "
            "RF metrics per band, EMC for the system, and body-worn SAR at 0 mm and 5 mm "
            "separations on flat phantom."
        ),
        "configurations": [
            "BLE @ 2402/2440/2480 MHz, max power, GFSK",
            "Wi-Fi @ 2412/2437/2462 MHz, 802.11n MCS7",
            "SAR: flat phantom, 0 mm + 5 mm separation, front + back",
            "EMC: ANSI C63.10 / EN 301 489-17",
        ],
        "citations": [
            "47 CFR 15.247", "KDB 447498 D01", "EN 300 328 v2.2.2",
            "EN 62311:2020", "RSS-247 Issue 2", "RSS-102 Issue 6",
        ],
    }),
    "lp-report-setup": (
        "The device under test was mounted on a SPEAG SAM/POPEYE flat phantom "
        "inside a fully anechoic SAR test chamber maintained at 22 +/- 2 C and "
        "30-50 percent relative humidity. The DASY8 6-axis robotic positioner "
        "(LabPilot digital twin) executed an automated volumetric grid sweep "
        "across the front and back surfaces of the phantom at separations of "
        "0 mm and 5 mm. Calibration of the dipole reference probe was "
        "performed prior to scan initiation and verified at 2.45 GHz against "
        "the manufacturer's reference uncertainty budget."
    ),
    "lp-report-measurement": (
        "Volumetric SAR scan acquired 2890 sample points across the body-worn "
        "test surface. Peak 1g averaged SAR was 1.54 W/kg, observed at the "
        "anomaly cluster centered on coordinate (8.2, 4.4, 3.0) cm. Three "
        "samples crossed the 90 percent of-limit warning threshold (KDB 447498 "
        "D01 reporting trigger). All other samples remained below 1.20 W/kg. "
        "Note: this measurement set is generated by the LabPilot physics-based "
        "digital twin simulator and is presented as a demonstration of the "
        "automated reporting pipeline, not as a substitute for a physical "
        "SPEAG DASY8 measurement campaign."
    ),
    "lp-report-citer": (
        "RF Output Power and EIRP -> 47 CFR 15.247(b)(3); EN 300 328 4.3.2.2; "
        "RSS-247 5.4. Occupied Bandwidth -> EN 300 328 4.3.2.7; KDB 558074. "
        "SAR (1g) -> 47 CFR 2.1093, KDB 447498 D01, RSS-102 Issue 6. "
        "SAR (10g) -> EN 62311:2020, EN 50566, MIC Notice 173. "
        "EMC -> ANSI C63.10, EN 301 489-1/-17, ICES-003."
    ),
    "lp-report-narrator": (
        "The 1.54 W/kg peak observed at (8.2, 4.4, 3.0) cm is consistent with "
        "antenna detuning under tissue loading along the proximal edge of the "
        "device. Resolution path: (1) verify the PIFA matching network under "
        "5 mm tissue load; (2) re-run a localized 1 cm grid around the "
        "anomaly cluster; (3) if the reading is repeatable, apply a -1 dB "
        "transmit power back-off in the proximity-detection firmware path."
    ),
    "lp-report-compliance": (
        "Pass / fail by jurisdiction (against simulated peak SAR 1.54 W/kg): "
        "FCC (1.6 W/kg @ 1g) PASS with 96 percent margin used. "
        "ISED (1.6 W/kg @ 1g) PASS. "
        "ANATEL (1.6 W/kg @ 1g) PASS. "
        "EU (2.0 W/kg @ 10g) PASS. "
        "Japan MIC (2.0 W/kg @ 10g) PASS. "
        "Overall: device is currently within compliance margins for all five "
        "target jurisdictions but the 96 percent FCC headroom warrants the "
        "antenna re-tune recommended in the anomaly analysis."
    ),
}


# --------------------------- Direct Flash --------------------------- #

def _flash_system_instruction(agent_id: str) -> str:
    from gemini_client import AGENT_SPECS
    for spec in AGENT_SPECS:
        if spec["id"] == agent_id:
            return spec["system_instruction"]
    return ""


def _flash_skills_for(agent_id: str) -> str:
    from gemini_client import AGENT_SPECS, _read_skill
    for spec in AGENT_SPECS:
        if spec["id"] == agent_id:
            if not spec["skills"]:
                return ""
            blocks = [f"=== SKILL: {s.upper()} ===\n{_read_skill(s)}" for s in spec["skills"]]
            return "\n\n".join(blocks)
    return ""


async def _flash_call(agent_id: str, prompt: str) -> str:
    client = get_client()
    sys_inst = _flash_system_instruction(agent_id)
    skills = _flash_skills_for(agent_id)
    full_prompt = (
        (skills + "\n\n" if skills else "")
        + (sys_inst + "\n\n" if sys_inst else "")
        + prompt
    )

    def _sync_call():
        resp = client.models.generate_content(
            model=_FLASH_MODEL,
            contents=full_prompt,
        )
        return resp.text or ""

    # Retry with exponential backoff on transient errors (429, 503, network).
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0.0, 2.0, 5.0, 12.0]):
        if delay:
            await asyncio.sleep(delay)
        try:
            return (await asyncio.to_thread(_sync_call)).strip()
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            if "429" in msg or "503" in msg or "rate" in msg or "quota" in msg or "unavailable" in msg:
                print(f"[flash:{agent_id}] transient error attempt {attempt+1}: {exc}")
                continue
            raise
    raise last_exc if last_exc else RuntimeError("flash call failed")


# --------------------------- Public API --------------------------- #

class _MockInteraction:
    """Quacks like a real Interaction object."""
    def __init__(self, output_text: str, environment_id: str = "mock-env"):
        self.output_text = output_text
        self.environment_id = environment_id


async def invoke_agent(agent_id: str, prompt: str):
    """
    Returns an object with .output_text and .environment_id fields. Routes:
      - MOCK_AGENTS  -> mock
      - assembler    -> Antigravity managed agent
      - all others   -> direct Flash
    """
    if _use_mock():
        return _MockInteraction(_MOCK_OUTPUTS.get(agent_id, "{}"))

    if agent_id in _MANAGED_AGENT_IDS:
        client = get_client()
        return await asyncio.to_thread(
            client.interactions.create,
            agent=agent_id,
            input=prompt,
            environment="remote",
        )

    text = await _flash_call(agent_id, prompt)
    return _MockInteraction(text)


async def invoke_agent_text(agent_id: str, prompt: str) -> str:
    interaction = await invoke_agent(agent_id, prompt)
    return interaction.output_text.strip()


async def invoke_agent_json(agent_id: str, prompt: str) -> Any:
    interaction = await invoke_agent(agent_id, prompt)
    return parse_json(interaction.output_text)


def download_environment_file(env_id: str, target_filename: str) -> bytes:
    """Download a file from a managed-agent sandbox snapshot."""
    api_key = os.environ["GEMINI_API_KEY"]
    response = requests.get(
        f"https://generativelanguage.googleapis.com/v1beta/files/environment-{env_id}:download",
        params={"alt": "media"},
        headers={"x-goog-api-key": api_key},
        allow_redirects=True,
        timeout=120,
    )
    response.raise_for_status()
    with tarfile.open(fileobj=io.BytesIO(response.content)) as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.endswith(target_filename):
                f = tar.extractfile(member)
                if f is not None:
                    return f.read()
    raise FileNotFoundError(f"{target_filename} not found in sandbox snapshot")
