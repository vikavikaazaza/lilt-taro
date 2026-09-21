from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.pdfgen import canvas

from astro_reports import synastry_pdf_sections, transit_pdf_sections

A4_W, A4_H = A4
_REGULAR = 'LilitRegular'
_BOLD = 'LilitBold'


def _font_path(bold: bool = False) -> str:
    try:
        import fontpkg
        for args in (({'weight': 700 if bold else 400}), ({'bold': bold}), ({'style': 'bold' if bold else 'regular'})):
            try:
                path = fontpkg.path('Noto Sans', **args)
                if path and Path(str(path)).is_file():
                    return str(path)
            except Exception:
                pass
    except Exception:
        pass

    try:
        import subprocess
        pattern = f'sans:style={"bold" if bold else "regular"}:lang=ru'
        r = subprocess.run(['fc-match', '-f', '%{file}', pattern], check=False, capture_output=True, text=True, timeout=4)
        if r.stdout.strip() and Path(r.stdout.strip()).is_file():
            return r.stdout.strip()
    except Exception:
        pass

    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf' if bold else '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for path in candidates:
        if Path(path).is_file():
            return path
    raise FileNotFoundError('Не найден TTF-шрифт с поддержкой кириллицы.')


def _register_fonts() -> None:
    if _REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_REGULAR, _font_path(False)))
    if _BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_BOLD, _font_path(True)))


def _draw_background(c: canvas.Canvas, doc) -> None:
    top = HexColor('#15112A'); bottom = HexColor('#090817')
    strips = 24
    for i in range(strips):
        t = i / (strips - 1)
        col = Color(top.red*(1-t)+bottom.red*t, top.green*(1-t)+bottom.green*t, top.blue*(1-t)+bottom.blue*t)
        c.setFillColor(col); c.rect(0, A4_H*i/strips, A4_W, A4_H/strips+1, stroke=0, fill=1)
    for radius, alpha, x, y, hx in [
        (70*mm, .06, A4_W*.08, A4_H*.90, '#CDAA63'),
        (90*mm, .05, A4_W*.95, A4_H*.18, '#8E73D8'),
    ]:
        col = HexColor(hx)
        for k in range(10, 0, -1):
            rr = radius*k/10
            c.setFillColor(Color(col.red, col.green, col.blue, alpha*(11-k)/10))
            c.circle(x, y, rr, stroke=0, fill=1)
    c.setFillColor(Color(.96, .90, .75, .14)); c.circle(A4_W-25*mm, A4_H-25*mm, 11*mm, stroke=0, fill=1)
    c.setFillColor(top); c.circle(A4_W-20*mm, A4_H-22*mm, 11*mm, stroke=0, fill=1)
    c.setFillColor(Color(.05, .04, .11, .90)); c.roundRect(11*mm, 15*mm, A4_W-22*mm, A4_H-30*mm, 7*mm, stroke=0, fill=1)
    for x_mm, y_mm, r_mm in [(16,276,.6),(36,255,.4),(60,286,.5),(85,262,.45),(112,282,.55),(140,254,.45),(168,286,.5),(198,264,.4),(222,285,.55),(260,250,.45)]:
        c.setFillColor(Color(1,.92,.69,.42)); c.circle(x_mm*mm,y_mm*mm,r_mm*mm,stroke=0,fill=1)
    c.setStrokeColor(Color(.8,.68,.4,.28)); c.setLineWidth(.6); c.line(18*mm,13*mm,A4_W-18*mm,13*mm)
    c.setFont(_REGULAR, 7.5); c.setFillColor(Color(.92,.87,.76,.60)); c.drawCentredString(A4_W/2,8*mm,f'ЛИЛИТ · {doc.page}')


def _safe(text: str) -> str:
    return html.escape(str(text or '')).replace('\n','<br/>')


class _ReportDocTemplate(BaseDocTemplate):
    pass


def _styles():
    ss = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('T', parent=ss['Title'], fontName=_BOLD, fontSize=24, leading=28, textColor=HexColor('#F4E8C8'), alignment=TA_CENTER, spaceAfter=5*mm),
        'subtitle': ParagraphStyle('ST', parent=ss['Normal'], fontName=_REGULAR, fontSize=10, leading=13, textColor=HexColor('#D7CBE8'), alignment=TA_CENTER, spaceAfter=7*mm),
        'section': ParagraphStyle('S', parent=ss['Heading2'], fontName=_BOLD, fontSize=13, leading=16, textColor=HexColor('#E4C979'), spaceBefore=4*mm, spaceAfter=2*mm, keepWithNext=True),
        'body': ParagraphStyle('B', parent=ss['BodyText'], fontName=_REGULAR, fontSize=9.25, leading=12.8, textColor=HexColor('#F0EAF6'), spaceAfter=1.4*mm),
        'small': ParagraphStyle('SM', parent=ss['BodyText'], fontName=_REGULAR, fontSize=8, leading=10.8, textColor=HexColor('#CFC7D9'), spaceAfter=1.2*mm),
        'meta': ParagraphStyle('M', parent=ss['BodyText'], fontName=_REGULAR, fontSize=8.7, leading=12, textColor=HexColor('#302A3A')),
        'table': ParagraphStyle('TB', parent=ss['BodyText'], fontName=_REGULAR, fontSize=7.8, leading=10, textColor=HexColor('#2D2836')),
        'tableb': ParagraphStyle('TBB', parent=ss['BodyText'], fontName=_BOLD, fontSize=7.8, leading=10, textColor=HexColor('#2D2836')),
    }


def _table_rows(rows: list[str], style, prefix: str = '- ') -> list[list[Paragraph]]:
    return [[Paragraph(_safe(prefix + row), style)] for row in rows]


def _section_story(title: str, rows: list[str], styles: dict) -> list:
    story = [Paragraph(_safe(title), styles['section'])]
    for row in rows:
        story.append(Paragraph(_safe(row), styles['body']))
    return story


def _build_report(path: str|Path, title: str, subtitle: str, meta_lines: Iterable[str], sections: list[tuple[str,list[str]]]) -> str:
    _register_fonts()
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    mx=18*mm; mb=17*mm; mt=22*mm
    frame = Frame(mx, mb, A4_W-2*mx, A4_H-mb-mt, leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,id='main')
    doc = _ReportDocTemplate(str(out), pagesize=A4, leftMargin=mx,rightMargin=mx,topMargin=mt,bottomMargin=mb,title=title,author='ЛИЛИТ')
    doc.addPageTemplates([PageTemplate(id='lilit', frames=[frame], onPage=_draw_background)])
    st=_styles(); story=[]
    story += [Spacer(1, 12*mm), Paragraph(_safe(title), st['title']), Paragraph(_safe(subtitle), st['subtitle'])]
    meta_data = [['Исходные данные'], *[[x] for x in meta_lines]]
    tbl = Table([[Paragraph(_safe(row[0]), st['tableb'] if i==0 else st['table'])] for i,row in enumerate(meta_data)], colWidths=[A4_W-2*mx])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),HexColor('#E6D5AA')), ('BACKGROUND',(0,1),(-1,-1),HexColor('#F6F0E5')),
        ('BOX',(0,0),(-1,-1),.7,HexColor('#C8B38A')), ('INNERGRID',(0,1),(-1,-1),.25,HexColor('#DDD0B4')),
        ('LEFTPADDING',(0,0),(-1,-1),5*mm),('RIGHTPADDING',(0,0),(-1,-1),5*mm),('TOPPADDING',(0,0),(-1,-1),2.3*mm),('BOTTOMPADDING',(0,0),(-1,-1),2.3*mm),
    ]))
    story += [tbl, Spacer(1,5*mm)]
    story.append(Paragraph('Основной текст собран в цельные тематические блоки простым языком и построен локально по расчётным данным, без генерации ИИ. Полные технические аспекты и положения планет оставлены отдельно для проверки.', st['small']))
    for title_sec, rows in sections:
        story.extend(_section_story(title_sec, rows, st))
    doc.build(story)
    return str(out)


def build_synastry_pdf(path: str|Path, answer: str, calc: dict) -> str:
    n1=str(calc.get('name1') or 'Человек 1'); n2=str(calc.get('name2') or 'Человек 2')
    p1,p2=calc.get('person1',{}),calc.get('person2',{})
    meta=[f'{n1} + {n2}',f'{n1}: {p1.get("birth_date","")} · {p1.get("birth_time") or "время неизвестно"} · {p1.get("city","")}',f'{n2}: {p2.get("birth_date","")} · {p2.get("birth_time") or "время неизвестно"} · {p2.get("city","")}']
    return _build_report(path,'Синастрия','ЛИЛИТ · подробный технический отчёт',meta,synastry_pdf_sections(calc))


def build_transit_pdf(path: str|Path, answer: str, calc: dict) -> str:
    date=str(calc.get('transit_date') or ''); city=str(calc.get('city') or '')
    meta=[f'Прогноз на {date}',f'Город рождения: {city}',f'Дата рождения: {calc.get("birth_date","")} · {calc.get("birth_time") or "время неизвестно"}',f'Активных аспектов: {len(calc.get("aspects",[]))}']
    return _build_report(path,'Транзиты','ЛИЛИТ · подробный технический отчёт на выбранную дату',meta,transit_pdf_sections(calc))
