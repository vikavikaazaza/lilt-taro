from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

try:
    import swisseph as swe
except Exception as exc:  # pragma: no cover
    swe = None
    _SWE_IMPORT_ERROR = exc
else:
    _SWE_IMPORT_ERROR = None

PLANETS = [
    ('Солнце', getattr(swe, 'SUN', 0)),
    ('Луна', getattr(swe, 'MOON', 1)),
    ('Меркурий', getattr(swe, 'MERCURY', 2)),
    ('Венера', getattr(swe, 'VENUS', 3)),
    ('Марс', getattr(swe, 'MARS', 4)),
    ('Юпитер', getattr(swe, 'JUPITER', 5)),
    ('Сатурн', getattr(swe, 'SATURN', 6)),
    ('Уран', getattr(swe, 'URANUS', 7)),
    ('Нептун', getattr(swe, 'NEPTUNE', 8)),
    ('Плутон', getattr(swe, 'PLUTO', 9)),
]

SIGNS = (
    'Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева',
    'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы',
)

ASPECTS = (
    ('Соединение', 0.0),
    ('Секстиль', 60.0),
    ('Квадрат', 90.0),
    ('Тригон', 120.0),
    ('Оппозиция', 180.0),
)

# A conservative orb for transit-to-natal aspects.
ORBS = {
    'Солнце': 4.0,
    'Луна': 5.0,
    'Меркурий': 3.0,
    'Венера': 3.0,
    'Марс': 3.0,
    'Юпитер': 3.0,
    'Сатурн': 3.0,
    'Уран': 3.0,
    'Нептун': 3.0,
    'Плутон': 3.0,
}


def _require_swe() -> None:
    if swe is None:
        raise RuntimeError(
            'Не установлен астрономический движок Swiss Ephemeris. '
            'Добавьте зависимость pysweph и перезапустите сервер.'
        )


def normalize_deg(value: float) -> float:
    return value % 360.0


def signed_deg(value: float) -> float:
    x = normalize_deg(value)
    if x > 180.0:
        x -= 360.0
    return x


def sign_info(longitude: float) -> tuple[str, int, float]:
    lon = normalize_deg(longitude)
    idx = int(lon // 30)
    deg = lon - idx * 30
    return SIGNS[idx], idx, deg


def format_degree(value: float) -> str:
    d = int(value)
    minutes = int(round((value - d) * 60.0))
    if minutes >= 60:
        d += 1
        minutes = 0
    return f'{d}° {minutes:02d}′'


def _julian_day(dt_utc: datetime) -> float:
    _require_swe()
    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0,
    )


def _planet_positions(jd_ut: float) -> dict[str, dict[str, Any]]:
    _require_swe()
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    out: dict[str, dict[str, Any]] = {}
    for name, body in PLANETS:
        calc_result = swe.calc_ut(jd_ut, body, flags)
        xx = calc_result[0]
        lon = normalize_deg(float(xx[0]))
        speed = float(xx[3])
        sign, _, sign_deg = sign_info(lon)
        out[name] = {
            'longitude': lon,
            'speed': speed,
            'sign': sign,
            'position': format_degree(sign_deg),
            'retrograde': speed < -0.0001,
        }
    return out


def _houses(jd_ut: float, lat: float, lon: float) -> tuple[list[float], float]:
    _require_swe()
    try:
        cusps, ascmc = swe.houses_ex(jd_ut, float(lat), float(lon), b'P')
    except Exception:
        return [], 0.0
    # pysweph 2.10.3.4+ can return a leading empty slot.
    if len(cusps) == 13 and abs(float(cusps[0])) < 1e-9:
        cusps = cusps[1:]
    cusps = [normalize_deg(float(x)) for x in cusps[:12]]
    asc = normalize_deg(float(ascmc[0])) if ascmc else 0.0
    return cusps, asc


def _house_for_longitude(lon: float, cusps: list[float]) -> int | None:
    if len(cusps) != 12:
        return None
    x = normalize_deg(lon)
    for i, start in enumerate(cusps):
        end = cusps[(i + 1) % 12]
        if start < end:
            inside = start <= x < end
        else:
            inside = x >= start or x < end
        if inside:
            return i + 1
    return 12


def _best_aspect(transit_lon: float, natal_lon: float) -> tuple[str, float, float] | None:
    best: tuple[str, float, float] | None = None
    raw_delta = signed_deg(transit_lon - natal_lon)
    for label, angle in ASPECTS:
        targets = [angle] if angle in (0.0, 180.0) else [angle, -angle]
        for target in targets:
            diff = signed_deg(raw_delta - target)
            orb = abs(diff)
            if best is None or orb < best[1]:
                best = (label, orb, diff)
    return best


def _aspect_state(diff: float, transit_speed: float) -> str:
    if abs(diff) < 0.05:
        return 'точный'
    # Positive absolute separation grows when diff and speed have the same sign,
    # and shrinks when signs oppose. With diff near +/-180, this remains stable enough
    # for our conservative 3–5° orb.
    moving_away = (diff > 0 and transit_speed > 0) or (diff < 0 and transit_speed < 0)
    return 'расходящийся' if moving_away else 'сходящийся'


def _local_noon(target_date: date, tz_name: str) -> datetime:
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Неизвестный часовой пояс: {tz_name}') from exc
    return datetime.combine(target_date, time(12, 0), tzinfo=zone)


def _birth_local_to_utc(birth_date: date, birth_time: time | None, tz_name: str) -> tuple[datetime, bool]:
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Неизвестный часовой пояс: {tz_name}') from exc
    known = birth_time is not None
    local = datetime.combine(birth_date, birth_time or time(12, 0), tzinfo=zone)
    return local.astimezone(timezone.utc), known


def calculate_transits(
    birth_date: date,
    birth_time: time | None,
    transit_date: date,
    lat: float,
    lon: float,
    tz_name: str,
    city: str,
) -> dict[str, Any]:
    """Calculate natal positions and the major transit aspects for one local day.

    Transit positions use 12:00 local time in the birth place so the result is a
    deterministic date-level reading. When birth time is unknown, houses and the
    Ascendant are intentionally omitted; natal Moon is marked approximate.
    """
    _require_swe()
    if not (-90 <= float(lat) <= 90):
        raise ValueError('Некорректная широта')
    if not (-180 <= float(lon) <= 180):
        raise ValueError('Некорректная долгота')

    birth_utc, time_known = _birth_local_to_utc(birth_date, birth_time, tz_name)
    target_local = _local_noon(transit_date, tz_name)
    target_utc = target_local.astimezone(timezone.utc)

    natal_jd = _julian_day(birth_utc)
    transit_jd = _julian_day(target_utc)

    natal = _planet_positions(natal_jd)
    transit = _planet_positions(transit_jd)
    cusps, asc = _houses(natal_jd, lat, lon) if time_known else ([], 0.0)

    aspects: list[dict[str, Any]] = []
    for transit_name, _ in PLANETS:
        tpos = transit[transit_name]
        max_orb = ORBS[transit_name]
        for natal_name, _ in PLANETS:
            best = _best_aspect(tpos['longitude'], natal[natal_name]['longitude'])
            if best is None:
                continue
            aspect_name, orb, diff = best
            if orb > max_orb:
                continue
            state = _aspect_state(diff, tpos['speed'])
            aspects.append({
                'transit_planet': transit_name,
                'natal_planet': natal_name,
                'aspect': aspect_name,
                'orb': round(orb, 2),
                'orb_text': format_degree(orb),
                'state': state,
                'transit_sign': tpos['sign'],
                'transit_position': tpos['position'],
                'transit_retrograde': bool(tpos['retrograde']),
                'house': _house_for_longitude(tpos['longitude'], cusps),
            })

    aspects.sort(key=lambda x: (x['orb'], x['transit_planet'], x['natal_planet']))
    seen_pairs: set[tuple[str, str, str]] = set()
    unique_aspects = []
    for a in aspects:
        key = (a['transit_planet'], a['natal_planet'], a['aspect'])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique_aspects.append(a)

    return {
        'city': city,
        'timezone': tz_name,
        'birth_date': birth_date.isoformat(),
        'birth_time': birth_time.strftime('%H:%M') if birth_time else None,
        'time_known': time_known,
        'transit_date': transit_date.isoformat(),
        'transit_local_time': target_local.strftime('%Y-%m-%d %H:%M'),
        'natal': natal,
        'transit': transit,
        'aspects': unique_aspects,
        'houses': cusps,
        'ascendant': asc if time_known else None,
        'ascendant_sign': sign_info(asc)[0] if time_known else None,
        'ephemeris_engine': 'Swiss Ephemeris / pysweph',
    }


def calculation_for_ai(calc: dict[str, Any]) -> str:
    lines = [
        f"Дата рождения: {calc['birth_date']}",
        f"Время рождения: {calc['birth_time'] or 'неизвестно'}",
        f"Место рождения: {calc['city']}",
        f"Часовой пояс: {calc['timezone']}",
        f"Дата транзита: {calc['transit_date']} (расчётный момент {calc['transit_local_time']})",
        '',
        'НАТАЛЬНЫЕ ПОЛОЖЕНИЯ:',
    ]
    for name, _ in PLANETS:
        p = calc['natal'][name]
        extra = ' ретроградное' if p['retrograde'] else ''
        if not calc['time_known'] and name == 'Луна':
            extra += ' (положение приблизительное, время рождения неизвестно)'
        lines.append(f"- {name}: {p['sign']} {p['position']}{extra}")

    lines.append('')
    lines.append('ТРАНЗИТНЫЕ ПОЛОЖЕНИЯ:')
    for name, _ in PLANETS:
        p = calc['transit'][name]
        extra = ' ретроградное' if p['retrograde'] else ''
        lines.append(f"- {name}: {p['sign']} {p['position']}{extra}")

    lines.append('')
    lines.append('ГЛАВНЫЕ АСПЕКТЫ:')
    if not calc['aspects']:
        lines.append('- Значимых аспектов в заданном орбисе не найдено.')
    else:
        for a in calc['aspects']:
            house = f", натальный дом {a['house']}" if a.get('house') else ''
            retro = ', ретроградная' if a.get('transit_retrograde') else ''
            lines.append(
                f"- {a['transit_planet']} {a['aspect']} натальный {a['natal_planet']} "
                f"(орб {a['orb_text']}, {a['state']}{retro}{house})"
            )

    if calc.get('ascendant_sign'):
        lines.append(f"Асцендент: {calc['ascendant_sign']}")
    if not calc['time_known']:
        lines.append('Время рождения неизвестно: дома и Асцендент не используются; положение натальной Луны приблизительное.')
    return '\n'.join(lines)
