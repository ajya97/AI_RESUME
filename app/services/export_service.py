"""PDF exports (ReportLab): resume templates and analysis reports."""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from app.services import template_service as ts


def _t(text) -> str:
    """Escape for ReportLab mini-HTML and fold to the base-14 font charset (cp1252)."""
    s = str(text if text is not None else "")
    s = s.encode("cp1252", "replace").decode("cp1252")
    return escape(s)


def resume_pdf(content: dict, template_key: str) -> bytes:
    spec = ts.TEMPLATES[template_key]
    accent = colors.HexColor(spec["accent"])
    align = TA_CENTER if spec["align"] == "center" else TA_LEFT
    body = ParagraphStyle("body", fontName=spec["font"], fontSize=spec["body_size"],
                          leading=spec["body_size"] * 1.35)
    name = ParagraphStyle("name", parent=body, fontName=spec["font_bold"], fontSize=spec["name_size"],
                          leading=spec["name_size"] * 1.2, alignment=align, textColor=accent)
    contact = ParagraphStyle("contact", parent=body, alignment=align, textColor=colors.HexColor("#333333"))
    head = ParagraphStyle("head", parent=body, fontName=spec["font_bold"], fontSize=spec["head_size"],
                          leading=spec["head_size"] * 1.3, textColor=accent, spaceBefore=9, spaceAfter=2)
    entry_head = ParagraphStyle("eh", parent=body, fontName=spec["font_bold"], spaceBefore=3)

    buf = io.BytesIO()
    margin = 14 * mm if template_key == "compact" else 18 * mm
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=margin,
                            bottomMargin=margin, title=_t(content.get("name") or "Resume"),
                            author=_t(content.get("name") or ""))
    story = []
    story.append(Paragraph(_t(content.get("name") or "Your Name"), name))
    cl = ts.contact_line(content)
    if cl:
        story.append(Paragraph(_t("  |  ".join(cl)), contact))

    for key, label in ts.SECTION_ORDER:
        val = content.get(key)
        if not val:
            continue
        title = label.upper() if spec["caps"] else label
        story.append(Paragraph(_t(title), head))
        if spec["rule"]:
            story.append(HRFlowable(width="100%", thickness=0.6, color=accent, spaceAfter=3))
        if key == "summary":
            story.append(Paragraph(_t(val), body))
        elif key == "skills":
            story.append(Paragraph(_t(", ".join(val)), body))
        elif key in ("certifications", "achievements"):
            story.append(ListFlowable([ListItem(Paragraph(_t(i), body), leftIndent=10) for i in val],
                                      bulletType="bullet", start="•", leftIndent=10))
        else:
            for entry in val:
                headline, bullets = ts.split_entry(entry)
                story.append(Paragraph(_t(headline), entry_head))
                if bullets:
                    story.append(ListFlowable([ListItem(Paragraph(_t(b), body), leftIndent=10) for b in bullets],
                                              bulletType="bullet", start="•", leftIndent=10))
    if len(story) <= 2 and not any(content.get(k) for k, _ in ts.SECTION_ORDER):
        story.append(Spacer(1, 6))
        story.append(Paragraph(_t("Add content to your resume to see it here."), body))
    doc.build(story)
    return buf.getvalue()


# ─── Analysis report PDFs ──────────────────────────────────────────────────
def _styles():
    base = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14)
    return {
        "title": ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=4),
        "h": ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=12.5, spaceBefore=12, spaceAfter=4,
                            textColor=colors.HexColor("#1d4ed8")),
        "b": base,
        "small": ParagraphStyle("s", parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555")),
    }


def _bullets(items, style):
    items = [i for i in items if i]
    if not items:
        return []
    return [ListFlowable([ListItem(Paragraph(_t(i), style), leftIndent=10) for i in items],
                         bulletType="bullet", start="•", leftIndent=10)]


def report_pdf(report, user_name: str = "") -> bytes:
    st = _styles()
    d = report.data or {}
    story = [Paragraph(_t(report.title), st["title"]),
             Paragraph(_t(f"Generated {report.created_at:%Y-%m-%d %H:%M} UTC"
                          f"{' for ' + user_name if user_name else ''}"), st["small"])]

    if report.type == "ats":
        ats = d.get("ats", {})
        story.append(Paragraph(_t(f"ATS compatibility score: {ats.get('total_score')}/100 ({ats.get('rating')})"), st["h"]))
        story.append(Paragraph(_t(d.get("ats_note", "")), st["small"]))
        story.append(Paragraph("Section breakdown", st["h"]))
        for k, v in (ats.get("sections") or {}).items():
            story.append(Paragraph(_t(f"{k.replace('_', ' ').title()}: {v['score']}/{v['max']}"), st["b"]))
        if d.get("errors"):
            story.append(Paragraph("Issues detected", st["h"]))
            story += _bullets([f"[{e['severity']}] {e['type']} — {e['fix']}" for e in d["errors"]], st["b"])
        if d.get("missing_sections"):
            story.append(Paragraph("Missing sections", st["h"]))
            story += _bullets([f"{m['section']}: {m['suggestion']}" for m in d["missing_sections"]], st["b"])
        g = d.get("gpt_analysis") or {}
        if g:
            story.append(Paragraph("AI summary", st["h"]))
            story.append(Paragraph(_t(g.get("profile_summary", "")), st["b"]))
            story.append(Paragraph(_t(g.get("overall_feedback", "")), st["b"]))
            story.append(Paragraph("Improvement suggestions", st["h"]))
            story += _bullets([f"[{s['priority']}] {s['category']}: {s['suggestion']}"
                               for s in g.get("improvement_suggestions", [])], st["b"])
            story.append(Paragraph(_t("AI-generated feedback is advisory and not an employer assessment."), st["small"]))
    elif report.type == "job_match":
        c = d.get("comparison", {})
        a = d.get("advice", {})
        story.append(Paragraph(_t(f"Match score: {c.get('score')}%"), st["h"]))
        story.append(Paragraph(_t(c.get("methodology", "")), st["small"]))
        story.append(Paragraph("Matching skills", st["h"]))
        story.append(Paragraph(_t(", ".join(c.get("matched_skills", [])) or "None detected"), st["b"]))
        story.append(Paragraph("Missing required skills", st["h"]))
        story.append(Paragraph(_t(", ".join(c.get("missing_required_skills", [])) or "None"), st["b"]))
        story.append(Paragraph("Missing preferred skills", st["h"]))
        story.append(Paragraph(_t(", ".join(c.get("missing_preferred_skills", [])) or "None"), st["b"]))
        story.append(Paragraph("AI summary", st["h"]))
        story.append(Paragraph(_t(a.get("summary", "")), st["b"]))
        story.append(Paragraph("Tailored suggestions", st["h"]))
        story += _bullets([f"{s['section']}: {s['suggestion']}" for s in a.get("tailored_suggestions", [])], st["b"])
    elif report.type == "skill_gap":
        gap, plan = d.get("gap", {}), d.get("plan", {})
        story.append(Paragraph(_t(f"Skill coverage for the role: {gap.get('coverage_percent')}%"), st["h"]))
        story.append(Paragraph(_t(gap.get("verification_note", "")), st["small"]))
        story.append(Paragraph("Missing skills", st["h"]))
        story.append(Paragraph(_t(", ".join(gap.get("missing_skills", [])) or "None"), st["b"]))
        story.append(Paragraph("Learning plan", st["h"]))
        story += _bullets([f"[{i['priority']}] {i['skill']} (~{i['estimated_weeks']} wks) — {i['why']}"
                           for i in plan.get("learning_plan", [])], st["b"])
        story.append(Paragraph("Project ideas", st["h"]))
        story += _bullets([f"{p['title']} — {p['description']}" for p in plan.get("project_ideas", [])], st["b"])

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=16 * mm, title=_t(report.title)).build(story)
    return buf.getvalue()
