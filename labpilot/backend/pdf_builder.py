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
import re
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


PHANTOM_LABELS = {
    "handset": "handset phantom surface",
    "tablet": "tablet phantom surface",
    "wearable": "body-worn wrist phantom",
    "laptop": "laptop phantom surface",
    "iot": "IoT device phantom surface",
    "speaker": "desktop exposure surface",
    "gateway": "desktop exposure surface",
}


def _anomaly_scatter(anomalies: list[dict], form_factor: str = "handset") -> bytes:
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
    label = PHANTOM_LABELS.get(form_factor, "test surface")
    ax.set_title(f"Anomaly cluster — {label}")
    ax.grid(linestyle=":", alpha=0.5)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _format_inline(text: str) -> str:
    # Safety net: strip HTML <br> tags (agents like to use them inside table cells)
    # before we escape the angle brackets.  Replace with " / " so concatenated
    # citation lists stay readable on one line.
    text = re.sub(r"<\s*br\s*/?\s*>", " / ", text, flags=re.IGNORECASE)
    # Strip LaTeX math markers ($...$ and $$...$$). The agents sometimes wrap
    # coordinates and variables in LaTeX which ReportLab cannot render.
    text = re.sub(r"\$\$([^$]+)\$\$", r"\1", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    # Escape XML/HTML special characters first so they don't break ReportLab's parser.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert bold: **text** -> <b>text</b> or __text__ -> <b>text</b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.*?)__", r"<b>\1</b>", text)
    # Convert italic: *text* -> <i>text</i> or _text_ -> <i>text</i>
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)
    # Convert inline code: `text` -> <font name="Courier">\1</font>
    text = re.sub(r"`(.*?)`", r'<font name="Courier">\1</font>', text)
    return text


def _split_md_table_row(row: str) -> list[str]:
    """Split a markdown table row '| a | b | c |' into ['a', 'b', 'c']."""
    parts = row.strip().strip("|").split("|")
    return [p.strip() for p in parts]


def _is_md_table_separator(row: str) -> bool:
    """Detect markdown table separator rows like '| :--- | --- | ---: |'."""
    cells = _split_md_table_row(row)
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c)


def _build_md_table(rows: list[str], body_style) -> Any:
    """Build a ReportLab Table from a sequence of markdown table row strings."""
    parsed_rows = [_split_md_table_row(r) for r in rows if not _is_md_table_separator(r)]
    if not parsed_rows:
        return None
    col_count = max(len(r) for r in parsed_rows)
    normalized = [r + [""] * (col_count - len(r)) for r in parsed_rows]
    cell_style = ParagraphStyle("TableCell", parent=body_style, fontSize=8.5, leading=10, spaceAfter=0)
    table_data = [
        [Paragraph(_format_inline(cell), cell_style) for cell in row]
        for row in normalized
    ]
    usable_width = 6.6 * inch
    col_widths = [usable_width / col_count] * col_count
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1d4a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def parse_markdown_to_flowables(text: str, styles_dict: dict[str, Any]) -> list[Any]:
    if not text:
        return []

    h2_style = styles_dict["H2"]
    h3_style = styles_dict["H3"]
    body_style = styles_dict["Body"]
    bullet_style = styles_dict["Bullet"]

    # Standardize newlines
    text = text.replace("\r\n", "\n")
    # If the model produced table rows but jammed them onto a single line,
    # insert newlines before each '|' that starts a new row.
    text = re.sub(r"(?<!\n)\s*\|\s*(?=[^\|\n]{1,200}\s*\|)", "\n| ", text)
    lines = text.split("\n")

    flowables: list[Any] = []
    current_paragraph_lines: list[str] = []
    pending_table_rows: list[str] = []

    def flush_paragraph():
        if current_paragraph_lines:
            joined = " ".join(current_paragraph_lines)
            formatted = _format_inline(joined)
            flowables.append(Paragraph(formatted, body_style))
            flowables.append(Spacer(1, 6))
            current_paragraph_lines.clear()

    def flush_table():
        if pending_table_rows:
            tbl = _build_md_table(pending_table_rows, body_style)
            if tbl is not None:
                flowables.append(Spacer(1, 4))
                flowables.append(tbl)
                flowables.append(Spacer(1, 6))
            pending_table_rows.clear()

    for line in lines:
        stripped = line.strip()

        # Table row detection: line starts and ends with '|' and has multiple cells.
        if stripped.startswith("|") and stripped.count("|") >= 2:
            flush_paragraph()
            pending_table_rows.append(stripped)
            continue
        else:
            flush_table()

        if not stripped:
            flush_paragraph()
            continue

        if stripped.startswith("#"):
            flush_paragraph()
            level = 0
            while level < len(stripped) and stripped[level] == "#":
                level += 1
            header_text = stripped[level:].strip()
            formatted = _format_inline(header_text)
            if level == 1:
                flowables.append(Paragraph(formatted, h2_style))
            else:
                flowables.append(Paragraph(formatted, h3_style))
            continue

        if stripped.startswith("* ") or stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
            if stripped.startswith("* ") or stripped.startswith("- "):
                item_text = stripped[2:].strip()
                formatted = f"&bull; {_format_inline(item_text)}"
            else:
                m = re.match(r"^(\d+)\.\s(.*)", stripped)
                num = m.group(1)
                item_text = m.group(2).strip()
                formatted = f"{num}. {_format_inline(item_text)}"
            flowables.append(Paragraph(formatted, bullet_style))
            continue

        if stripped in ("---", "***", "___"):
            flush_paragraph()
            hr_table = Table([[""]], colWidths=[6.5 * inch])
            hr_table.setStyle(TableStyle([
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            flowables.append(Spacer(1, 4))
            flowables.append(hr_table)
            flowables.append(Spacer(1, 4))
            continue

        current_paragraph_lines.append(stripped)

    flush_paragraph()
    flush_table()
    return flowables


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
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4,
                         textColor=colors.HexColor("#0b1d4a"))
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4,
                         textColor=colors.HexColor("#333333"))
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10.5, leading=14, spaceAfter=6)
    bullet = ParagraphStyle(
        "Bullet", parent=styles["Normal"], fontSize=10.5, leading=14,
        leftIndent=15, firstLineIndent=-10, spaceAfter=4
    )

    styles_dict = {
        "H1": h1,
        "H2": h2,
        "H3": h3,
        "Body": body,
        "Bullet": bullet,
    }

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
    story.extend(parse_markdown_to_flowables(sections.get("report_compliance", "—"), styles_dict))
    story.append(Spacer(1, 8))

    # Charts.
    chart1 = _peak_vs_limit_chart(scan_summary.get("peak_sar", 0))
    story.append(Image(io.BytesIO(chart1), width=6.5 * inch, height=3.0 * inch))
    story.append(PageBreak())

    # Test Setup.
    story.append(_para("1. Test Setup", h1))
    story.extend(parse_markdown_to_flowables(sections.get("report_setup", "—"), styles_dict))

    # Measurement Results.
    story.append(_para("2. Measurement Results", h1))
    story.extend(parse_markdown_to_flowables(sections.get("report_measurement", "—"), styles_dict))
    story.append(Spacer(1, 8))
    chart2 = _anomaly_scatter(scan_summary.get("anomalies", []), profile.get("form_factor", "handset"))
    story.append(Image(io.BytesIO(chart2), width=6.5 * inch, height=3.0 * inch))
    story.append(PageBreak())

    # Regulatory Traceability.
    story.append(_para("3. Regulatory Traceability", h1))
    story.extend(parse_markdown_to_flowables(sections.get("report_citer", "—"), styles_dict))

    # Anomaly Analysis.
    story.append(_para("4. Anomaly Analysis", h1))
    story.extend(parse_markdown_to_flowables(sections.get("report_narrator", "—"), styles_dict))
    story.append(PageBreak())

    # Per-jurisdiction summaries.
    story.append(_para("5. Per-Jurisdiction Summary", h1))
    cell_style = ParagraphStyle(
        "JurisCell", parent=body, fontSize=8.5, leading=11, spaceAfter=0
    )
    header_cell_style = ParagraphStyle(
        "JurisHeader", parent=body, fontSize=9, leading=11, spaceAfter=0,
        textColor=colors.white, fontName="Helvetica-Bold",
    )
    header_labels = ["Jurisdiction", "Limit", "Tissue avg.", "Required tests", "Est. hrs"]
    rows: list[list[Any]] = [
        [Paragraph(h, header_cell_style) for h in header_labels]
    ]
    for region_code, label_tuple in JURISDICTION_LIMITS.items():
        label, limit, avg = label_tuple
        entry = cert_matrix.get(region_code, {})
        tests = entry.get("required_tests", []) if isinstance(entry, dict) else []
        hours = entry.get("estimated_hours", "—") if isinstance(entry, dict) else "—"
        if not tests:
            continue
        tests_text = ", ".join(tests[:4]) + ("..." if len(tests) > 4 else "")
        rows.append([
            Paragraph(label, cell_style),
            Paragraph(f"{limit} W/kg", cell_style),
            Paragraph(avg, cell_style),
            Paragraph(tests_text, cell_style),
            Paragraph(str(hours), cell_style),
        ])
    j_table = Table(rows, colWidths=[1.1 * inch, 0.7 * inch, 0.7 * inch, 3.3 * inch, 0.6 * inch])
    j_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1d4a")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(j_table)
    story.append(Spacer(1, 14))

    # Test plan summary.
    story.append(_para("6. Test Plan", h1))
    story.extend(parse_markdown_to_flowables(test_plan.get("summary", "—"), styles_dict))
    if test_plan.get("configurations"):
        story.append(_para("Configurations", h2))
        for cfg in test_plan["configurations"]:
            story.append(Paragraph(f"&bull; {_format_inline(cfg)}", bullet))
    if test_plan.get("citations"):
        story.append(_para("Citations", h2))
        story.append(_para(", ".join(test_plan["citations"]), body))

    # Honest framing footer (uses ReportLab inline tags, NOT _para which escapes them).
    story.append(Spacer(1, 18))
    footer_style = ParagraphStyle(
        "Footer", parent=body, fontSize=9, leading=12, textColor=colors.HexColor("#555555")
    )
    story.append(Paragraph(
        "<i>LabPilot is an engineering-intelligence demo. The SAR data above "
        "is generated by a physics-based digital twin simulator and is not a "
        "substitute for a physical SPEAG DASY8 measurement campaign. The "
        "regulatory analysis, citations, test plan structure, and report "
        "assembly are produced by Gemini agents.</i>",
        footer_style,
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
