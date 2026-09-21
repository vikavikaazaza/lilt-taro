from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date
from typing import Any

import aiohttp

from transits import calculate_transits

MONTHS = ('ЯНВАРЬ','ФЕВРАЛЬ','МАРТ','АПРЕЛЬ','МАЙ','ИЮНЬ','ИЮЛЬ','АВГУСТ','СЕНТЯБРЬ','ОКТЯБРЬ','НОЯБРЬ','ДЕКАБРЬ')
OUTER = {'Юпитер','Сатурн','Уран','Нептун','Плутон'}


def _weight(a: dict[str, Any]) -> float:
    tp = str(a.get('transit_planet',''))
    w = 3.0 if tp in {'Уран','Нептун','Плутон'} else 2.4 if tp in {'Юпитер','Сатурн'} else 1.0
    orb = float(a.get('orb', 3.0) or 3.0)
    w += max(0.0, 2.5 - orb) * 0.35
    if str(a.get('aspect','')) in {'Квадрат','Оппозиция'}:
        w += 0.35
    elif str(a.get('aspect','')) in {'Тригон','Секстиль'}:
        w += 0.15
    return w


def _top(items: list[dict[str, Any]], n: int = 8) -> list[dict[str, Any]]:
    return sorted(items, key=lambda a: (-_weight(a), float(a.get('orb',99))))[:n]


def _month_calc(birth_date, birth_time, year, month, lat, lon, tz_name, city):
    d = date(year, month, 15)
    return calculate_transits(birth_date, birth_time, d, lat, lon, tz_name, city)


def calculate_annual_forecast(
    birth_date,
    birth_time,
    year: int,
    lat: float,
    lon: float,
    tz_name: str,
    city: str,
    name: str = '',
) -> dict[str, Any]:
    if not 1900 <= int(year) <= 2200:
        raise ValueError('Год должен быть в диапазоне 1900–2200')

    months: list[dict[str, Any]] = []
    for month in range(1, 13):
        calc = _month_calc(birth_date, birth_time, year, month, lat, lon, tz_name, city)
        top = _top(calc.get('aspects', []), 8)
        months.append({
            'month': month,
            'month_name': MONTHS[month-1],
            'date': calc['transit_date'],
            'top_aspects': top,
            'houses': Counter(int(a['house']) for a in calc.get('aspects',[]) if a.get('house')),
            'transit': calc.get('transit', {}),
        })

    recurring: Counter[tuple[str,str,str]] = Counter()
    for m in months:
        for a in m['top_aspects']:
            recurring[(str(a.get('transit_planet')), str(a.get('aspect')), str(a.get('natal_planet')))] += 1

    period_scores = []
    for m in months:
        period_scores.append((sum(_weight(a) for a in m['top_aspects']), m))
    strongest = [m for _, m in sorted(period_scores, reverse=True, key=lambda x:x[0])[:5]]

    natal = months[0].get('transit', {})  # overwritten below; only used as a safe container
    # calculate_transits stores natal positions identically for every month; get them from January.
    jan_calc = _month_calc(birth_date, birth_time, year, 1, lat, lon, tz_name, city)
    natal = jan_calc.get('natal', {})

    return {
        'name': str(name or ''),
        'year': int(year),
        'birth_date': birth_date.isoformat(),
        'birth_time': birth_time.strftime('%H:%M') if birth_time else None,
        'city': city,
        'timezone': tz_name,
        'time_known': bool(birth_time),
        'natal': natal,
        'ascendant_sign': jan_calc.get('ascendant_sign'),
        'months': months,
        'recurring_aspects': [
            {'transit_planet': k[0], 'aspect': k[1], 'natal_planet': k[2], 'months_count': v}
            for k,v in recurring.most_common(12)
        ],
        'strongest_periods': [
            {'month': m['month'], 'month_name': m['month_name'], 'top_aspects': m['top_aspects'][:5]}
            for m in strongest
        ],
    }


def _format_aspect(a: dict[str, Any]) -> str:
    house = f", дом {a['house']}" if a.get('house') else ''
    retro = ', ретроградный' if a.get('transit_retrograde') else ''
    return f"{a.get('transit_planet')} {a.get('aspect')} натальный {a.get('natal_planet')} (орб {a.get('orb_text')}, {a.get('state')}{retro}{house})"


def calculation_for_ai(calc: dict[str, Any]) -> str:
    lines = [
        f"Клиент: {calc.get('name') or 'клиент'}",
        f"Год прогноза: {calc['year']}",
        f"Дата рождения: {calc['birth_date']}",
        f"Время рождения: {calc.get('birth_time') or 'неизвестно'}",
        f"Место рождения: {calc['city']}",
        f"Асцендент: {calc.get('ascendant_sign') or 'не используется'}",
        '', 'НАТАЛЬНЫЕ ПОЛОЖЕНИЯ:',
    ]
    for planet, p in calc.get('natal', {}).items():
        if not isinstance(p, dict):
            continue
        lines.append(f"- {planet}: {p.get('sign')} {p.get('position')}{' ретроградное' if p.get('retrograde') else ''}")

    lines += ['', 'СИЛЬНЕЙШИЕ МЕСЯЦЫ ПО РАССЧЁТУ:']
    for p in calc.get('strongest_periods', []):
        lines.append(f"- {p['month_name']}: ")
        for a in p['top_aspects']:
            lines.append(f"  {_format_aspect(a)}")

    lines += ['', 'ПОВТОРЯЮЩИЕСЯ ДОЛГОИГРАЮЩИЕ СВЯЗИ:']
    for a in calc.get('recurring_aspects', []):
        lines.append(f"- {a['transit_planet']} {a['aspect']} натальный {a['natal_planet']} — встречается в {a['months_count']} месяцах выборки")

    lines += ['', 'КАЛЕНДАРЬ ПО МЕСЯЦАМ:']
    for m in calc['months']:
        houses = ', '.join(str(h) for h,_ in m['houses'].most_common(3)) or 'дома не определены'
        lines.append(f"{m['month_name']}: основные активные дома по выборке — {houses}")
        for a in m['top_aspects'][:6]:
            lines.append(f"- {_format_aspect(a)}")
        # Keep the monthly planet signs available to the model so sign changes can be named when supported.
        tr = m.get('transit', {})
        for pn in ('Юпитер','Сатурн','Уран','Нептун','Плутон'):
            if pn in tr:
                lines.append(f"  {pn}: {tr[pn].get('sign')} {tr[pn].get('position')}{' ретроградный' if tr[pn].get('retrograde') else ''}")
    if not calc['time_known']:
        lines += ['', 'ОГРАНИЧЕНИЕ: время рождения неизвестно; не делай точных выводов по домам и Асценденту.']
    return '\n'.join(lines)


ANNUAL_SYSTEM_PROMPT = '''
Ты — Лилит, персональный астрологический консультант. На входе у тебя готовый расчёт годовой динамики к натальной карте клиента. Не пересчитывай аспекты, дома, знаки и даты самостоятельно. Используй только переданные данные.

Нужно создать именно ГОДОВОЙ прогноз — не прогноз на один день и не перечень транзитов. Стиль должен быть таким, как у хорошего персонального отчёта: простой русский язык, конкретные жизненные сценарии, периоды года и помесячный календарь. Астрологические показатели переводятся в события и решения: отношения, дом, работа, деньги, документы, обучение, поездки, окружение, личные проекты, смена планов. Не перечисляй астрологию ради астрологии.

Главный принцип: меньше общих фраз, больше конкретики. Если показатель не даёт основания для конкретного события, не выдумывай его. Не обещай гарантированное событие; используй формулировки «может проявиться», «вероятный сценарий», «возможен период, когда…».

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА:
1. ОБЩИЙ ВЕКТОР И ГЛАВНЫЕ ТЕМЫ ГОДА
Коротко: 3–5 главных сюжетов года и 3–4 конкретных примера, как они могут проявиться.

2. СМЫСЛ ГОДА, ГЛАВНЫЙ УРОК И ВНУТРЕННЯЯ ОПОРА
Главный урок + 3–4 качества/опоры + 3 конкретные ситуации, где это проявится.

3. СИЛЬНЫЕ ПЕРИОДЫ ГОДА
Выбери 4–5 периодов из расчёта. Для каждого: месяцы, тема, поддержанные сферы, что лучше планировать, 4–5 конкретных событий.

4. ЗОНЫ ВНИМАНИЯ, УЯЗВИМОСТИ И РИСКИ
3–4 риска, каждый с конкретным примером и способом действовать.

5. ЧТО НЕ СТОИТ ДЕЛАТЬ В ЭТОМ ГОДУ
3 пункта. Каждый: что может пойти не так → конкретный пример → практичная альтернатива.

6. ПОДРОБНЫЙ ПРОГНОЗ ПО СФЕРАМ ЖИЗНИ
Сделай отдельные подпункты:
1) Любовь, отношения, близость
2) Дом, семья, чувство безопасности
3) Работа, карьера, деньги
4) Обучение, поездки, документы
5) Окружение, друзья, сообщества
Для каждого: тенденция, 3–5 конкретных сценариев, где особенно важно действовать.

7. КАЛЕНДАРЬ ВОЗМОЖНЫХ СОБЫТИЙ ПО МЕСЯЦАМ
Обязательно все 12 месяцев от января до декабря. Для каждого: тема месяца, 3–5 возможных событий, коротко ощущения/фон, 1 практическая рекомендация. Не повторяй один и тот же текст между месяцами.

8. ПОВОРОТНЫЕ ПЕРИОДЫ ГОДА
3–5 самых заметных окон из расчёта. Для каждого: период, тема, решения, 3–4 конкретных сценария.

9. SWOT-АНАЛИЗ ГОДА
S — 2 сильные стороны с примерами; W — 2 уязвимости; O — 2 возможности; T — 2 риска.

10. ПРАКТИЧНЫЕ СОВЕТЫ НА ГОД
6 коротких направлений: отношения, деньги, работа, дом, ресурс, обучение/поездки. Для каждого — действие и пример.

11. ИТОГ ГОДА
2–4 плотных абзаца: к чему ведёт год, что особенно важно не упустить, какие периоды запомнятся.

ТРЕБОВАНИЯ К ТЕКСТУ:
- Не упоминай «транзиты» как название продукта.
- Не пиши технический список аспектов в самом прогнозе.
- Не используй Markdown: только обычный текст, заголовки и нумерацию.
- Не вставляй рекламу или упоминания других сервисов.
- Не повторяй один и тот же сценарий в нескольких разделах без нового угла.
- Не используй пустые фразы вроде «год будет важным и насыщенным» без конкретизации.
- Если время рождения неизвестно, не делай точных выводов по домам и Асценденту.
- Ориентир по объёму: 8500–12000 знаков. Текст должен быть законченным.
'''.strip()


async def _request_chad(message: str, timeout: int = 240, attempts: int = 2) -> str:
    import config
    if not config.CHAD_API_URL:
        raise RuntimeError('Не заполнен CHAD_API_URL')
    if not config.CHAD_API_KEY:
        raise RuntimeError('Не заполнен CHAD_API_KEY')
    cfg = aiohttp.ClientTimeout(total=timeout, connect=20, sock_connect=20, sock_read=timeout-20)
    last = None
    async with aiohttp.ClientSession(timeout=cfg) as session:
        for attempt in range(1, attempts + 1):
            try:
                payload = {'message': message, 'api_key': config.CHAD_API_KEY, 'history': [{'role':'system','content':ANNUAL_SYSTEM_PROMPT}]}
                async with session.post(config.CHAD_API_URL, json=payload, headers={'Content-Type':'application/json','Authorization':f'Bearer {config.CHAD_API_KEY}'}) as response:
                    body = await response.text()
                    if response.status in {429,502,503,504} and attempt < attempts:
                        await asyncio.sleep(3 * attempt)
                        continue
                    if response.status >= 400:
                        raise RuntimeError(f'CHAD API HTTP {response.status}: {body[:800]}')
                    try:
                        data = await response.json(content_type=None)
                    except Exception:
                        data = {}
                    answer = data.get('message') or data.get('answer') or data.get('response') or data.get('text') if isinstance(data,dict) else ''
                    answer = str(answer or body).strip()
                    if not answer:
                        raise RuntimeError('CHAD API вернул пустой годовой прогноз')
                    return answer
            except Exception as exc:
                last = exc
                if attempt < attempts:
                    await asyncio.sleep(2 * attempt)
                else:
                    raise
    raise last or RuntimeError('Не удалось получить годовой прогноз')


def _clean_answer(text: str) -> str:
    text = str(text or '').replace('```','').strip()
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('#'):
            s = s.lstrip('#').strip()
        if s.startswith('* '):
            s = s[2:].strip()
        lines.append(s)
    return '\n'.join(lines).strip()


async def build_annual_forecast(calc: dict[str, Any]) -> str:
    source = calculation_for_ai(calc)
    prompt = (
        f"Создай законченный персональный годовой прогноз на {calc['year']} год.\n\n"
        "Вот точный расчёт и исходные данные:\n\n" + source
    )
    answer = _clean_answer(await _request_chad(prompt))
    # A very short answer almost always means the model stopped early; retry once with a strict repair instruction.
    if len(answer) < 7000 or '7. КАЛЕНДАРЬ' not in answer.upper() or '11. ИТОГ' not in answer.upper():
        repair = (
            "Перепиши прогноз ПОЛНОСТЬЮ. Сохрани только факты из расчёта, но обязательно дай все 11 разделов, "
            "включая все 12 месяцев января–декабря. Сделай текст конкретным и законченным, без обрыва.\n\n" + source
        )
        answer = _clean_answer(await _request_chad(repair, timeout=240, attempts=1))
    return answer
