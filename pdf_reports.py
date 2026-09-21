from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color

A4_W, A4_H = A4


def _font_path(name: str) -> str:
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/{name}.ttf",
        f"/usr/share/fonts/truetype/dejavu/{name}.TTF",
        f"/usr/share/fonts/truetype/liberation2/{name}.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return path
    raise FileNotFoundError(f"Шрифт {name} не найден на сервере")


_REGULAR = "LilitRegular"
_BOLD = "LilitBold"


def _register_fonts() -> None:
    if _REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_REGULAR, _font_path("DejaVuSans")))
    if _BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_BOLD, _font_path("DejaVuSans-Bold")))


def _draw_background(c: canvas.Canvas, doc) -> None:
    # Deep night-sky base with a restrained violet/gold palette.
    strips = 24
    top = HexColor("#15112A")
    bottom = HexColor("#090817")
    for i in range(strips):
        t = i / max(1, strips - 1)
        r = top.red * (1 - t) + bottom.red * t
        g = top.green * (1 - t) + bottom.green * t
        b = top.blue * (1 - t) + bottom.blue * t
        c.setFillColor(Color(r, g, b))
        y = A4_H * (i / strips)
        c.rect(0, y, A4_W, A4_H / strips + 0.8, stroke=0, fill=1)

    # Soft glows.
    for radius, alpha, x, y, color_hex in [
        (72 * mm, 0.07, A4_W * 0.10, A4_H * 0.90, "#CDAA63"),
        (90 * mm, 0.055, A4_W * 0.96, A4_H * 0.18, "#8E73D8"),
        (55 * mm, 0.045, A4_W * 0.52, A4_H * 0.52, "#B998E6"),
    ]:
        col = HexColor(color_hex)
        for k in range(10, 0, -1):
            rr = radius * k / 10
            c.setFillColor(Color(col.red, col.green, col.blue, alpha * (11 - k) / 10))
            c.circle(x, y, rr, stroke=0, fill=1)

    # Moon motif.
    c.setFillColor(Color(0.88, 0.79, 0.53, alpha=0.16))
    c.circle(A4_W - 28 * mm, A4_H - 28 * mm, 12 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#15112A"))
    c.circle(A4_W - 22.5 * mm, A4_H - 25 * mm, 12 * mm, stroke=0, fill=1)

    # Main content panel keeps long text readable while preserving the decorative edges.
    c.setFillColor(Color(0.055, 0.045, 0.12, alpha=0.90))
    c.roundRect(13 * mm, 18 * mm, A4_W - 26 * mm, A4_H - 36 * mm, 8 * mm, stroke=0, fill=1)

    # Stars.
    stars = [
        (14, 275, 0.7), (28, 254, 0.45), (43, 286, 0.6), (63, 260, 0.35),
        (77, 282, 0.55), (95, 250, 0.4), (118, 286, 0.55), (136, 264, 0.35),
        (158, 286, 0.5), (177, 255, 0.4), (191, 272, 0.55), (210, 246, 0.35),
        (225, 283, 0.5), (244, 261, 0.45), (272, 286, 0.35),
    ]
    for x_mm, y_mm, r_mm in stars:
        c.setFillColor(Color(1, 0.91, 0.68, alpha=0.46))
        c.circle(x_mm * mm, y_mm * mm, r_mm * mm, stroke=0, fill=1)

    # Subtle footer ornament.
    c.setStrokeColor(Color(0.80, 0.68, 0.40, alpha=0.32))
    c.setLineWidth(0.6)
    c.line(18 * mm, 14 * mm, A4_W - 18 * mm, 14 * mm)
    c.setFont(_REGULAR, 7.5)
    c.setFillColor(Color(0.92, 0.87, 0.76, alpha=0.62))
    c.drawCentredString(A4_W / 2, 8.7 * mm, f"ЛИЛИТ · {doc.page}")


def _safe(text: str) -> str:
    return html.escape(str(text or "")).replace("\n", "<br/>")


def _plain(text: str) -> str:
    text = re.sub(r"[\t ]+", " ", str(text or "").strip())
    return text


def _split_sections(answer: str) -> list[tuple[str, str]]:
    text = str(answer or "").replace("\r\n", "\n").strip()
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_body: list[str] = []

    for block in blocks:
        first, *rest = block.split("\n", 1)
        m = re.match(r"^\s*(\d+)\.\s*(.+?)\s*$", first)
        if m:
            if current_title:
                sections.append((current_title, "\n".join(current_body).strip()))
            current_title = f"{m.group(1)}. {m.group(2)}"
            current_body = rest if rest else []
        else:
            current_body.extend(block.splitlines())

    if current_title:
        sections.append((current_title, "\n".join(current_body).strip()))
    elif text:
        sections.append(("Разбор", text))
    return sections


class _ReportDocTemplate(BaseDocTemplate):
    pass


def _build_pdf(path: str | Path, title: str, subtitle: str, meta_lines: Iterable[str], answer: str) -> str:
    _register_fonts()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    margin_x = 20 * mm
    margin_bottom = 18 * mm
    margin_top = 22 * mm
    frame = Frame(
        margin_x,
        margin_bottom,
        A4_W - 2 * margin_x,
        A4_H - margin_bottom - margin_top,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="content",
    )
    doc = _ReportDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=margin_x,
        rightMargin=margin_x,
        topMargin=margin_top,
        bottomMargin=margin_bottom,
        title=title,
        author="ЛИЛИТ",
    )
    doc.addPageTemplates([PageTemplate(id="lilit", frames=[frame], onPage=_draw_background)])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=_BOLD,
        fontSize=24,
        leading=29,
        textColor=HexColor("#F4E8C8"),
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName=_REGULAR,
        fontSize=10,
        leading=14,
        textColor=HexColor("#D7CBE8"),
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontName=_REGULAR,
        fontSize=9.5,
        leading=14,
        textColor=HexColor("#3A3149"),
        alignment=TA_LEFT,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName=_BOLD,
        fontSize=13.2,
        leading=17,
        textColor=HexColor("#E1C77B"),
        spaceBefore=2.5 * mm,
        spaceAfter=2 * mm,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName=_REGULAR,
        fontSize=10.3,
        leading=15.2,
        textColor=HexColor("#F0EAF6"),
        spaceAfter=2.2 * mm,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontName=_REGULAR,
        fontSize=8.2,
        leading=11,
        textColor=HexColor("#C8BED1"),
    )

    story = []

    # Cover card.
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph(_safe(title), title_style))
    story.append(Paragraph(_safe(subtitle), subtitle_style))

    meta = [f"<b>{_safe(x)}</b>" if i == 0 else _safe(x) for i, x in enumerate(meta_lines)]
    meta_html = "<br/>".join(meta)
    meta_para = Paragraph(meta_html, meta_style)
    story.append(Paragraph(
        f'<font color="#3A3149"><b>Исходные данные</b></font><br/>{meta_para.text}',
        ParagraphStyle(
            "MetaBox",
            parent=meta_style,
            backColor=HexColor("#F6F0E5"),
            borderColor=HexColor("#D7C4A4"),
            borderWidth=0.7,
            borderPadding=6 * mm,
            borderRadius=8,
            spaceAfter=8 * mm,
        ),
    ))
    story.append(Paragraph(
        "Персональный разбор подготовлен на основании рассчитанных астрологических показателей. "
        "В PDF вынесен основной интерпретационный текст, чтобы его было удобно сохранить или отправить другому человеку.",
        note_style,
    ))
    story.append(Spacer(1, 8 * mm))

    sections = _split_sections(answer)
    for idx, (section_title, body) in enumerate(sections):
        section_flow = [Paragraph(_safe(section_title), section_style)]
        body_parts = [p.strip() for p in re.split(r"\n+", body) if p.strip()]
        for part in body_parts:
            section_flow.append(Paragraph(_safe(part), body_style))
        story.append(KeepTogether(section_flow))
        if idx < len(sections) - 1:
            story.append(Spacer(1, 1.2 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "ЛИЛИТ · персональный астрологический разбор",
        note_style,
    ))

    doc.build(story)
    return str(out)


def build_synastry_pdf(path: str | Path, answer: str, calc: dict) -> str:
    name1 = str(calc.get("name1") or "Человек 1")
    name2 = str(calc.get("name2") or "Человек 2")
    p1 = calc.get("person1", {})
    p2 = calc.get("person2", {})
    meta = [
        f"{name1} + {name2}",
        f"{name1}: {p1.get('birth_date', '')} · {p1.get('birth_time') or 'время неизвестно'} · {p1.get('city', '')}",
        f"{name2}: {p2.get('birth_date', '')} · {p2.get('birth_time') or 'время неизвестно'} · {p2.get('city', '')}",
        f"Синастрических аспектов: {calc.get('aspect_count', 0)} · аспектов к углам: {calc.get('angle_aspect_count', 0)}",
    ]
    return _build_pdf(path, "Синастрия", "ЛИЛИТ · персональный разбор отношений", meta, answer)


def build_transit_pdf(path: str | Path, answer: str, calc: dict) -> str:
    date = str(calc.get("transit_date") or "")
    city = str(calc.get("city") or "")
    birth_date = str(calc.get("birth_date") or calc.get("natal_birth_date") or "")
    birth_time = str(calc.get("birth_time") or "")
    meta = [
        f"Прогноз на {date}",
        f"Город рождения: {city}",
        f"Дата рождения: {birth_date} · {birth_time or 'время неизвестно'}",
        f"Аспектов на выбранную дату: {len(calc.get('aspects', []))}",
    ]
    return _build_pdf(path, "Транзиты", "ЛИЛИТ · персональный прогноз на выбранную дату", meta, answer)
