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
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color

from astro_reports import synastry_pdf_sections, transit_pdf_sections

A4_W, A4_H = A4
_REGULAR = 'LilitRegular'
_BOLD = 'LilitBold'


def _font_path(bold: bool = False) -> str:
    try:
        import fontpkg
        path = fontpkg.path('Noto Sans', weight=700 if bold else 400)
        if path and Path(str(path)).is_file():
            return str(path)
    except Exception:
        pass
    try:
        import subprocess
        pattern = f'sans:style={"bold" if bold else "regular"}:lang=ru'
        result = subprocess.run(['fc-match', '-f', '%{file}', pattern], check=False, capture_output=True, text=True, timeout=5)
        path = result.stdout.strip()
        if path and Path(path).is_file():
            return path
    except Exception:
        pass
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf' if bold else '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    roots = [Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.fonts']
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for fp in root.rglob('*.ttf'):
                low = fp.name.lower()
                if bold and 'bold' not in low:
                    continue
                if not bold and any(tag in low for tag in ('bold', 'italic', 'oblique')):
                    continue
                if any(tag in low for tag in ('dejavu', 'noto', 'liberation', 'freesans', 'roboto', 'carlito')):
                    return str(fp)
        except Exception:
            continue
    raise FileNotFoundError('Не найден шрифт с поддержкой кириллицы. Установите зависимость fontpkg-noto-sans==2.15 в requirements.txt.')


def _register_fonts() -> None:
    if _REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_REGULAR, _font_path(False)))
    if _BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_BOLD, _font_path(True)))


def _draw_background(c: canvas.Canvas, doc) -> None:
    strips = 24
    top = HexColor('#15112A'); bottom = HexColor('#090817')
    for i in range(strips):
        t = i / max(1, strips - 1)
        r = top.red * (1-t) + bottom.red * t
        g = top.green * (1-t) + bottom.green * t
        b = top.blue * (1-t) + bottom.blue * t
        c.setFillColor(Color(r, g, b))
        c.rect(0, A4_H * i / strips, A4_W, A4_H / strips + 0.8, stroke=0, fill=1)
    for radius, alpha, x, y, hx in [
        (72*mm, .07, A4_W*.10, A4_H*.90, '#CDAA63'),
        (90*mm, .055, A4_W*.96, A4_H*.18, '#8E73D8'),
        (55*mm, .045, A4_W*.52, A4_H*.52, '#B998E6'),
    ]:
        col = HexColor(hx)
        for k in range(10, 0, -1):
            rr = radius*k/10
            c.setFillColor(Color(col.red, col.green, col.blue, alpha*(11-k)/10))
            c.circle(x, y, rr, stroke=0, fill=1)
    c.setFillColor(Color(.88, .79, .53, alpha=.16)); c.circle(A4_W-28*mm, A4_H-28*mm, 12*mm, stroke=0, fill=1)
    c.setFillColor(HexColor('#15112A')); c.circle(A4_W-22.5*mm, A4_H-25*mm, 12*mm, stroke=0, fill=1)
    c.setFillColor(Color(.055, .045, .12, alpha=.90)); c.roundRect(13*mm,18*mm,A4_W-26*mm,A4_H-36*mm,8*mm,stroke=0,fill=1)
    for x_mm,y_mm,r_mm in [(14,275,.7),(28,254,.45),(43,286,.6),(63,260,.35),(77,282,.55),(95,250,.4),(118,286,.55),(136,264,.35),(158,286,.5),(177,255,.4),(191,272,.55),(210,246,.35),(225,283,.5),(244,261,.45),(272,286,.35)]:
        c.setFillColor(Color(1,.91,.68,alpha=.46)); c.circle(x_mm*mm,y_mm*mm,r_mm*mm,stroke=0,fill=1)
    c.setStrokeColor(Color(.80,.68,.40,alpha=.32)); c.setLineWidth(.6); c.line(18*mm,14*mm,A4_W-18*mm,14*mm)
    c.setFont(_REGULAR,7.5); c.setFillColor(Color(.92,.87,.76,alpha=.62)); c.drawCentredString(A4_W/2,8.7*mm,f'ЛИЛИТ · {doc.page}')


def _safe(text: str) -> str:
    return html.escape(str(text or '')).replace('\n','<br/>')


def _paragraph_chunks(text: str, target: int = 900) -> list[str]:
    text = ' '.join(str(text or '').split()).strip()
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: list[str] = []
    cur = ''
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if cur and len(cur) + 1 + len(sentence) > target:
            chunks.append(cur)
            cur = sentence
        else:
            cur = (cur + ' ' + sentence).strip()
    if cur:
        chunks.append(cur)
    return chunks


class _ReportDocTemplate(BaseDocTemplate):
    pass


def _build_pdf(path: str|Path, title: str, subtitle: str, meta_lines: Iterable[str], sections: list[tuple[str,list[str]]]) -> str:
    _register_fonts()
    out=Path(path); out.parent.mkdir(parents=True,exist_ok=True)
    margin_x=20*mm; margin_bottom=18*mm; margin_top=22*mm
    frame=Frame(margin_x,margin_bottom,A4_W-2*margin_x,A4_H-margin_bottom-margin_top,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,id='content')
    doc=_ReportDocTemplate(str(out),pagesize=A4,leftMargin=margin_x,rightMargin=margin_x,topMargin=margin_top,bottomMargin=margin_bottom,title=title,author='ЛИЛИТ')
    doc.addPageTemplates([PageTemplate(id='lilit',frames=[frame],onPage=_draw_background)])
    ss=getSampleStyleSheet()
    title_style=ParagraphStyle('TitleX',parent=ss['Title'],fontName=_BOLD,fontSize=24,leading=29,textColor=HexColor('#F4E8C8'),alignment=TA_CENTER,spaceAfter=6*mm)
    subtitle_style=ParagraphStyle('SubX',parent=ss['Normal'],fontName=_REGULAR,fontSize=10,leading=14,textColor=HexColor('#D7CBE8'),alignment=TA_CENTER,spaceAfter=8*mm)
    meta_style=ParagraphStyle('MetaX',parent=ss['Normal'],fontName=_REGULAR,fontSize=9.5,leading=14,textColor=HexColor('#3A3149'),alignment=TA_LEFT)
    section_style=ParagraphStyle('SectionX',parent=ss['Heading2'],fontName=_BOLD,fontSize=13.2,leading=17,textColor=HexColor('#E1C77B'),spaceBefore=3.6*mm,spaceAfter=2.2*mm,keepWithNext=True)
    body_style=ParagraphStyle('BodyX',parent=ss['BodyText'],fontName=_REGULAR,fontSize=10.15,leading=15.0,textColor=HexColor('#F0EAF6'),spaceAfter=3.0*mm)
    note_style=ParagraphStyle('NoteX',parent=ss['Normal'],fontName=_REGULAR,fontSize=8.2,leading=11,textColor=HexColor('#C8BED1'))
    tech_style=ParagraphStyle('TechX',parent=ss['BodyText'],fontName=_REGULAR,fontSize=8.1,leading=11,textColor=HexColor('#F2EBDD'),spaceAfter=1.2*mm)
    story=[]
    story += [Spacer(1,18*mm),Paragraph(_safe(title),title_style),Paragraph(_safe(subtitle),subtitle_style)]
    meta_html='<br/>'.join(_safe(x) for x in meta_lines)
    meta_box=Paragraph(meta_html,ParagraphStyle('MetaBoxX',parent=meta_style,backColor=HexColor('#F6F0E5'),borderColor=HexColor('#D7C4A4'),borderWidth=.7,borderPadding=6*mm,borderRadius=8,spaceAfter=7*mm))
    story.append(meta_box)
    story.append(Paragraph('Ниже находится основной персональный разбор. Он собран по расчётным данным без ИИ: сначала даётся понятная интерпретация по жизненным темам, а в самом конце оставлена техническая таблица для тех, кто хочет проверить исходные связи.',note_style))
    story.append(Spacer(1,7*mm))
    tech_started=False
    for title_sec, rows in sections:
        if title_sec.startswith('Техническая таблица'):
            if not tech_started:
                story.append(PageBreak()); tech_started=True
        story.append(Paragraph(_safe(title_sec),section_style))
        style = tech_style if tech_started else body_style
        for row in rows:
            if tech_started:
                story.append(Paragraph(_safe(row),style))
            else:
                chunks = _paragraph_chunks(row, target=900)
                for chunk in chunks:
                    story.append(Paragraph(_safe(chunk),style))
        story.append(Spacer(1,1.2*mm))
    story.append(Spacer(1,4*mm)); story.append(Paragraph('ЛИЛИТ · персональный астрологический разбор',note_style))
    doc.build(story)
    return str(out)


def build_synastry_pdf(path: str|Path, answer: str, calc: dict) -> str:
    name1=str(calc.get('name1') or 'Человек 1'); name2=str(calc.get('name2') or 'Человек 2')
    p1=calc.get('person1',{}); p2=calc.get('person2',{})
    meta=[f'{name1} + {name2}',f'{name1}: {p1.get("birth_date","")} · {p1.get("birth_time") or "время неизвестно"} · {p1.get("city","")}',f'{name2}: {p2.get("birth_date","")} · {p2.get("birth_time") or "время неизвестно"} · {p2.get("city","")}',f'Рассчитано межпланетных связей: {calc.get("aspect_count",0)} · связей с углами: {calc.get("angle_aspect_count",0)}']
    sections=synastry_pdf_sections(calc)
    return _build_pdf(path,'Синастрия','ЛИЛИТ · подробный разбор отношений',meta,sections)


def build_transit_pdf(path: str|Path, answer: str, calc: dict) -> str:
    date=str(calc.get('transit_date') or ''); city=str(calc.get('city') or '')
    meta=[f'Прогноз на {date}',f'Город рождения: {city}',f'Дата рождения: {calc.get("birth_date","")} · {calc.get("birth_time") or "время неизвестно"}',f'Активных связей на выбранную дату: {len(calc.get("aspects",[]))}']
    sections=transit_pdf_sections(calc)
    return _build_pdf(path,'Транзиты','ЛИЛИТ · подробный прогноз на выбранную дату',meta,sections)
