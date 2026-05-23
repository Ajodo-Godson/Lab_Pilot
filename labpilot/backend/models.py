"""Pydantic schemas shared between agents and orchestrator."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- Inbound from frontend ----------

class CreateProjectRequest(BaseModel):
    device_name: str
    bom_text: str
    target_regions: list[str] = Field(default_factory=lambda: ["US", "EU", "CA", "JP", "BR"])


class Anomaly(BaseModel):
    position: list[float]
    sar: float


class ScanSummary(BaseModel):
    peak_sar: float
    anomaly_count: int
    total_points: int
    anomalies: list[Anomaly] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    scan_summary: ScanSummary


# ---------- Agent outputs ----------

class Radio(BaseModel):
    chip: str
    type: str
    freq_mhz: float
    power_dbm: float


FORM_FACTORS = {"handset", "tablet", "wearable", "laptop", "iot", "speaker", "gateway", "other"}


class DeviceProfile(BaseModel):
    """Structured output of the intake agent."""
    device_name: str
    form_factor: str  # handset | tablet | wearable | laptop | iot | speaker | gateway | other
    body_worn: bool
    held_to_head: bool = False
    radios: list[Radio]
    target_regions: list[str]
    notes: str = ""


class JurisdictionResult(BaseModel):
    region: str
    summary: str
    required_tests: list[str]
    citations: list[str]
    estimated_hours: int


class TestPlanResult(BaseModel):
    summary: str
    configurations: list[str]
    citations: list[str]


class ReportSection(BaseModel):
    name: str
    body: str


class FinalReport(BaseModel):
    pdf_base64: str
    summary: str
    sections: dict[str, str]
