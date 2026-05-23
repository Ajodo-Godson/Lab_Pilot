"""
Centralized Gemini client + Managed Agent provisioning.

LabPilot uses 11 Managed Agents (Antigravity) so that the project is a strong
contender for the "best use of managed agents" prize.

  Agent ID                    Role
  --------------------------  --------------------------------------------------
  lp-intake                   Parses BOM into a DeviceProfile
  lp-jurisdiction-fcc         FCC analyst (FCC skill mounted)
  lp-jurisdiction-eu          EU RED analyst
  lp-jurisdiction-ca          ISED Canada analyst
  lp-jurisdiction-jp          Japan MIC analyst
  lp-jurisdiction-br          ANATEL Brazil analyst
  lp-test-plan                Drafts the test plan from device + cert matrix
  lp-report-setup             Test setup / phantom / equipment narrative
  lp-report-measurement       Measurement summary using simulated SAR data
  lp-report-citer             Citations & traceability for every value
  lp-report-narrator          Anomaly narrative & resolution
  lp-report-compliance        Final pass/fail per jurisdiction
  lp-report-assembler         Renders the final 200-page-style PDF

Each saved agent is created once and reused. We probe with `agents.get(...)` and
fall back to `agents.create(...)` if it doesn't exist.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from google import genai

BASE_AGENT = os.getenv("MANAGED_AGENT_BASE", "antigravity-preview-05-2026")
SKILLS_DIR = Path(__file__).parent / "skills"


def _read_skill(name: str) -> str:
    """Read a skill markdown file. Public-ish: agent_runtime imports this."""
    return (SKILLS_DIR / f"{name}.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    """Singleton genai.Client."""
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


# ---------- Agent definitions ----------

INTAKE_INSTRUCTION = """\
You are the LabPilot intake agent. You parse a BOM (bill of materials) for a
wireless device and emit a strict JSON DeviceProfile.

DeviceProfile schema:
  device_name: string
  form_factor: one of "handset" | "tablet" | "wearable" | "laptop" | "iot" | "speaker" | "gateway" | "other"
  body_worn: boolean (true if typically used within 20 cm of body)
  held_to_head: boolean (true for handsets used against the ear)
  radios: list of { chip: string, type: string, freq_mhz: number, power_dbm: number }
  target_regions: list of ISO country codes
  notes: short string with anything notable (DFS, UWB, NFC, etc.)

Respond ONLY with JSON. No markdown fences. No prose."""

JURISDICTION_INSTRUCTION = """\
You are a regulatory analyst for {region_label}. The skill files mounted into
/.agents/skills contain authoritative regulatory references that you MUST cite.

You will be given a DeviceProfile JSON. You must determine, for the {region_label}
jurisdiction only:
  - Which regulatory tests apply
  - The exact citation for each test (CFR section, EN standard, RSS number, etc.)
  - A reasonable estimate of lab hours

Use Google Search to verify any citation you are unsure about. Be conservative —
do not invent citations.

Respond ONLY with JSON matching:
{{
  "region": "{region_code}",
  "summary": "<one paragraph>",
  "required_tests": ["<short name>", ...],
  "citations": ["<exact regulation>", ...],
  "estimated_hours": <integer>
}}
"""

TEST_PLAN_INSTRUCTION = """\
You are the LabPilot test plan author. Given:
  - A DeviceProfile
  - A certification matrix (5 jurisdiction analyses)

Produce a structured test plan. Respond ONLY with JSON:
{
  "summary": "<paragraph: scope, frequency bands, body positions>",
  "configurations": ["<test config 1>", "<test config 2>", ...],
  "citations": ["<regulation 1>", ...]
}

Be specific about frequencies, power levels, antenna positions, and body-worn
phantoms where relevant."""

_PROSE_RULES = (
    "\n\nFORMATTING RULES (strict):\n"
    "- Output plain prose paragraphs and bulleted lists ONLY.\n"
    "- DO NOT use markdown tables (no '|' pipe characters).\n"
    "- DO NOT use HTML tags such as <br>, <b>, <i>, <table>.\n"
    "- DO NOT use LaTeX math like $...$ or $$...$$. Write coordinates and values inline as plain text.\n"
    "- Use '-' or '*' for bullets; use '# ' or '## ' for headings only.\n"
)

REPORT_SECTION_INSTRUCTIONS = {
    "report_setup": (
        "You write the *Test Setup* section of an FCC certification report. "
        "Describe equipment (DASY8 robot, phantom type, anechoic chamber), "
        "environmental conditions, and calibration. Output prose only, ~250 "
        "words, no markdown headers."
        + _PROSE_RULES
    ),
    "report_measurement": (
        "You write the *Measurement Results* section. You will be given a "
        "JSON ScanSummary with peak_sar, anomaly_count, total_points, and "
        "anomaly positions. Summarize the simulated SAR scan in prose, ~250 "
        "words. Cite KDB 447498. Be honest that the data is from a physics "
        "simulator (LabPilot digital twin), not a physical SPEAG scan."
        + _PROSE_RULES
    ),
    "report_citer": (
        "You write the *Regulatory Traceability* section. For every measurement "
        "type referenced (SAR, RF power, occupied bandwidth, spurious, EMC), "
        "cite the exact regulation it would be evaluated against. Output a "
        "compact reference list, prose form. Use bulleted lists, never tables."
        + _PROSE_RULES
    ),
    "report_narrator": (
        "You write the *Anomaly Analysis* section. Given the anomaly list from "
        "the ScanSummary, narrate the cause and resolution path for each. "
        "Reference engineering practice: antenna detuning, body proximity, "
        "thermal drift, etc. Output ~200 words of prose."
        + _PROSE_RULES
    ),
    "report_compliance": (
        "You write the *Executive Compliance Statement*. Compare peak SAR to "
        "each jurisdiction's limit (FCC 1.6 W/kg @ 1g, EU 2.0 @ 10g, ISED 1.6 "
        "@ 1g, MIC 2.0 @ 10g, ANATEL 1.6 @ 1g). State Pass/Fail per region. "
        "End with a one-sentence overall conclusion."
        + _PROSE_RULES
    ),
}

REPORT_ASSEMBLER_INSTRUCTION = """\
You are the LabPilot report assembler. You will receive a JSON payload with:
  - device_profile
  - cert_matrix (5 jurisdiction analyses)
  - test_plan
  - sections (5 prose sections: setup, measurement, citer, narrator, compliance)
  - scan_summary (peak_sar, anomaly_count, total_points, anomalies)

You must use Code Execution to:
  1. Generate a SAR distribution chart (matplotlib): bar chart of peak SAR per
     jurisdiction limit. Save as /workspace/sar_chart.png.
  2. Generate a coverage chart: anomaly position scatter colored by SAR.
     Save as /workspace/anomaly_chart.png.
  3. Build a multi-page PDF using ReportLab at /workspace/report.pdf containing:
       Cover page (device name, project ID, date)
       Executive Summary (use the compliance section)
       Test Setup (use the setup section)
       Measurement Results (use the measurement section + sar_chart.png)
       Regulatory Traceability (use the citer section)
       Anomaly Analysis (use the narrator section + anomaly_chart.png)
       Per-jurisdiction summaries from cert_matrix
       Final compliance statement

Then read /workspace/report.pdf, base64-encode it, and respond with strict JSON:
{
  "pdf_base64": "<base64 string>",
  "summary": "<2 sentence executive summary>"
}

No markdown, no prose outside the JSON. Use ReportLab's SimpleDocTemplate.
Make the PDF look professional. Use matplotlib's 'seaborn-v0_8-whitegrid' style.
"""

AGENT_SPECS: list[dict] = [
    {
        "id": "lp-intake",
        "system_instruction": INTAKE_INSTRUCTION,
        "skills": [],
    },
    {
        "id": "lp-jurisdiction-fcc",
        "system_instruction": JURISDICTION_INSTRUCTION.format(
            region_label="the United States Federal Communications Commission",
            region_code="fcc",
        ),
        "skills": ["fcc"],
    },
    {
        "id": "lp-jurisdiction-eu",
        "system_instruction": JURISDICTION_INSTRUCTION.format(
            region_label="the European Union (Radio Equipment Directive 2014/53/EU)",
            region_code="eu",
        ),
        "skills": ["eu"],
    },
    {
        "id": "lp-jurisdiction-ca",
        "system_instruction": JURISDICTION_INSTRUCTION.format(
            region_label="ISED Canada",
            region_code="ca",
        ),
        "skills": ["ca"],
    },
    {
        "id": "lp-jurisdiction-jp",
        "system_instruction": JURISDICTION_INSTRUCTION.format(
            region_label="Japan MIC / ARIB",
            region_code="jp",
        ),
        "skills": ["jp"],
    },
    {
        "id": "lp-jurisdiction-br",
        "system_instruction": JURISDICTION_INSTRUCTION.format(
            region_label="ANATEL Brazil",
            region_code="br",
        ),
        "skills": ["br"],
    },
    {
        "id": "lp-test-plan",
        "system_instruction": TEST_PLAN_INSTRUCTION,
        "skills": ["fcc", "eu", "ca", "jp", "br"],
    },
    {
        "id": "lp-report-setup",
        "system_instruction": REPORT_SECTION_INSTRUCTIONS["report_setup"],
        "skills": [],
    },
    {
        "id": "lp-report-measurement",
        "system_instruction": REPORT_SECTION_INSTRUCTIONS["report_measurement"],
        "skills": ["fcc"],
    },
    {
        "id": "lp-report-citer",
        "system_instruction": REPORT_SECTION_INSTRUCTIONS["report_citer"],
        "skills": ["fcc", "eu", "ca", "jp", "br"],
    },
    {
        "id": "lp-report-narrator",
        "system_instruction": REPORT_SECTION_INSTRUCTIONS["report_narrator"],
        "skills": [],
    },
    {
        "id": "lp-report-compliance",
        "system_instruction": REPORT_SECTION_INSTRUCTIONS["report_compliance"],
        "skills": ["fcc", "eu", "ca", "jp", "br"],
    },
    {
        "id": "lp-report-assembler",
        "system_instruction": REPORT_ASSEMBLER_INSTRUCTION,
        "skills": [],
    },
]


def _build_environment(skills: list[str]) -> dict:
    """Build a base_environment dict with skill files mounted."""
    sources = []
    for skill in skills:
        sources.append({
            "type": "inline",
            "target": f".agents/skills/{skill}/SKILL.md",
            "content": _read_skill(skill),
        })
    return {"type": "remote", "sources": sources}


def ensure_agents() -> dict[str, str]:
    """
    Ensure the managed agents we actually invoke exist.

    LabPilot's hybrid runtime calls Antigravity ONLY for the report assembler
    (the call that needs Code Execution to render charts and the final PDF).
    Everything else routes through direct Gemini Flash calls in
    `agent_runtime.py`, which is much cheaper and does not eat the 200K TPM
    Antigravity cap.

    We keep the full AGENT_SPECS table around because (a) the system
    instructions are reused as Flash prompts and (b) on a higher-quota
    project you can flip every agent to Antigravity by changing one constant
    in `agent_runtime.py`.

    Idempotent: safe to call on every backend startup.
    """
    client = get_client()
    try:
        existing = {a.id for a in client.agents.list().agents}
    except Exception as exc:
        print(f"[agents] list failed (will skip provisioning): {exc}")
        return {}

    # Only register agents the runtime will actually invoke.
    from agent_runtime import _MANAGED_AGENT_IDS
    needed = [s for s in AGENT_SPECS if s["id"] in _MANAGED_AGENT_IDS]

    created: dict[str, str] = {}
    for spec in needed:
        agent_id = spec["id"]
        if agent_id in existing:
            created[agent_id] = agent_id
            continue
        env = _build_environment(spec["skills"])
        try:
            client.agents.create(
                id=agent_id,
                base_agent=BASE_AGENT,
                system_instruction=spec["system_instruction"],
                base_environment=env if env["sources"] else "remote",
            )
            created[agent_id] = agent_id
            print(f"[agents] created {agent_id}")
        except Exception as exc:
            print(f"[agents] {agent_id} skipped: {exc}")
            created[agent_id] = agent_id
    return created
