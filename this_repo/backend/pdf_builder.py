"""
Local PDF builder — the deterministic fallback for the report assembler.

Used when:
  - Antigravity is unavailable / over quota
  - We're running in MOCK_AGENTS=true mode
  - The Antigravity assembler returns invalid output

Produces a multi-page compliance-style PDF with two matplotlib charts so
the demo always has something visual to show.
"""
from __future__ import annotations

import base64
import io
from datetime import date
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


JURISDICTION_LIMITS = {
    "fcc": ("FCC (US)", 1.6, "1 g"),
    "eu": ("EU RED", 2.0, "10 g"),
    "ca": ("ISED Canada", 1.6, "1 g"),
    "jp": ("Japan MIC", 2.0, "10 g"),
    "br": ("ANATEL Brazil", 1.6, "1 g"),
}


def _peak_vs_limit_chart(peak_sar: float) -> bytes:
    """Bar chart of peak SAR vs each jurisdiction's limit."""
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
    labels = [v[0] for v in JURISDICTION_LIMITS.values()]
    limits = [v[1] for v in JURISDICTION_LIMITS.values()]
    peaks = [peak_sar] * len(labels)

    x = range(len(labels))
    ax.bar([i - 0.18 for i in x], peaks, width=0.36, label="Simulated peak", color="#1f77b4")
    ax.bar([i + 0.18 for i in x], limits, width=0.36, label="Regulatory limit", color="#d62728")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("SAR (W/kg)")
    ax.set_title("Peak simulated SAR vs jurisdictional limits")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _anomaly_scatter(anomalies: list[dict]) -> bytes:
    """X-Y scatter colored by SAR for anomaly cluster."""
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
    if anomalies:
        xs = [a["position"][0] for a in anomalies]
        ys = [a["position"][1] for a in anomalies]
        cs = [a["sar"] for a in anomalies]
        sc = ax.scatter(xs, ys, c=cs, cmap="hot_r", s=200, edgecolor="k", vmin=1.0, vmax=1.6)
        plt.colorbar(sc, ax=ax, label="SAR (W/kg)")
        for a in anomalies:
            ax.annotate(
                f"{a['sar']:.2f}",
                (a["position"][0], a["position"][1]),
                textcoords="offset points",
                xytext=(8, 8),
                fontsize=8,
            )
    else:
        ax.text(0.5, 0.5, "No anomalies above threshold", ha="center", va="center")
    ax.set_xlabel("X (cm)")
    ax.set_ylabel("Y (cm)")
    ax.set_title("Anomaly cluster — body-worn surface")
    ax.grid(linestyle=":", alpha=0.5)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _para(text: str, style) -> Paragraph:
    # Reportlab is picky about ampersands and angle brackets.
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def build_pdf(
    project_id: str,
    profile: dict,
    cert_matrix: dict[str, dict],
    test_plan: dict,
    sections: dict[str, str],
    scan_summary: dict,
) -> tuple[str, str]:
    """
    Returns (pdf_base64, summary_string).
    """
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], fontSize=22, spaceAfter=18, textColor=colors.HexColor("#0b1d4a")
    )
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15, spaceBefore=14, spaceAfter=6,
                         textColor=colors.HexColor("#0b1d4a"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10.5, leading=14)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title=f"LabPilot Compliance Report — {profile.get('device_name', 'Device')}",
    )

    story: list[Any] = []

    # Cover page.
    story.append(_para("LabPilot", title_style))
    story.append(_para("Wireless Certification Compliance Report", h1))
    story.append(Spacer(1, 24))
    cover_data = [
        ["Device", profile.get("device_name", "—")],
        ["Form factor", profile.get("form_factor", "—")],
        ["Body-worn", "Yes" if profile.get("body_worn") else "No"],
        ["Target regions", ", ".join(profile.get("target_regions", []))],
        ["Project ID", project_id],
        ["Report date", date.today().isoformat()],
        ["Data source", "LabPilot physics-based SAR digital twin (simulated)"],
    ]
    t = Table(cover_data, colWidths=[1.6 * inch, 4.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2fb")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())

    # Executive Summary.
    story.append(_para("Executive Summary", h1))
    story.append(_para(sections.get("report_compliance", "—"), body))
    story.append(Spacer(1, 8))

    # Charts.
    chart1 = _peak_vs_limit_chart(scan_summary.get("peak_sar", 0))
    story.append(Image(io.BytesIO(chart1), width=6.5 * inch, height=3.0 * inch))
    story.append(PageBreak())

    # Test Setup.
    story.append(_para("1. Test Setup", h1))
    story.append(_para(sections.get("report_setup", "—"), body))

    # Measurement Results.
    story.append(_para("2. Measurement Results", h1))
    story.append(_para(sections.get("report_measurement", "—"), body))
    story.append(Spacer(1, 8))
    chart2 = _anomaly_scatter(scan_summary.get("anomalies", []))
    story.append(Image(io.BytesIO(chart2), width=6.5 * inch, height=3.0 * inch))
    story.append(PageBreak())

    # Regulatory Traceability.
    story.append(_para("3. Regulatory Traceability", h1))
    story.append(_para(sections.get("report_citer", "—"), body))

    # Anomaly Analysis.
    story.append(_para("4. Anomaly Analysis", h1))
    story.append(_para(sections.get("report_narrator", "—"), body))
    story.append(PageBreak())

    # Per-jurisdiction summaries.
    story.append(_para("5. Per-Jurisdiction Summary", h1))
    rows = [["Jurisdiction", "Limit", "Tissue avg.", "Required tests", "Est. hrs"]]
    for region_code, label_tuple in JURISDICTION_LIMITS.items():
        label, limit, avg = label_tuple
        entry = cert_matrix.get(region_code, {})
        tests = entry.get("required_tests", []) if isinstance(entry, dict) else []
        hours = entry.get("estimated_hours", "—") if isinstance(entry, dict) else "—"
        rows.append([
            label,
            f"{limit} W/kg",
            avg,
            ", ".join(tests[:4]) + ("..." if len(tests) > 4 else ""),
            str(hours),
        ])
    j_table = Table(rows, colWidths=[1.3 * inch, 0.8 * inch, 0.8 * inch, 3.0 * inch, 0.7 * inch])
    j_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1d4a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(j_table)
    story.append(Spacer(1, 14))

    # Test plan summary.
    story.append(_para("6. Test Plan", h1))
    story.append(_para(test_plan.get("summary", "—"), body))
    if test_plan.get("configurations"):
        story.append(_para("Configurations", h2))
        for cfg in test_plan["configurations"]:
            story.append(_para(f"• {cfg}", body))
    if test_plan.get("citations"):
        story.append(_para("Citations", h2))
        story.append(_para(", ".join(test_plan["citations"]), body))

    # Honest framing footer.
    story.append(Spacer(1, 18))
    story.append(_para(
        "<i>LabPilot is an engineering-intelligence demo. The SAR data above "
        "is generated by a physics-based digital twin simulator and is not a "
        "substitute for a physical SPEAG DASY8 measurement campaign. The "
        "regulatory analysis, citations, test plan structure, and report "
        "assembly are produced by Gemini agents.</i>",
        body,
    ))

    doc.build(story)
    buf.seek(0)
    pdf_bytes = buf.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    summary = (
        f"Compliance report for {profile.get('device_name', 'device')}. "
        f"Peak simulated SAR: {scan_summary.get('peak_sar', 0):.2f} W/kg across "
        f"{scan_summary.get('total_points', 0)} sample points. "
        f"{scan_summary.get('anomaly_count', 0)} anomalies above 90% threshold."
    )
    return pdf_b64, summary
