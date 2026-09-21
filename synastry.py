from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe

from transits import (
    PLANETS,
    SIGNS,
    ASPECTS,
    ORBS as TRANSIT_ORBS,
    format_degree,
    normalize_deg,
    sign_info,
    _julian_day,
    _planet_positions,
    _houses,
    _house_for_longitude,
    _best_aspect,
)

SYNASTRY_ORBS = {
    'Солнце': 8.0,
    'Луна': 8.0,
    'Меркурий': 6.0,
    'Венера': 6.0,
    'Марс': 6.0,
    'Юпитер': 5.0,
    'Сатурн': 5.0,
    'Уран': 4.0,
    'Нептун': 4.0,
    'Плутон': 4.0,
}
ANGLE_ORB = 5.0
ANGLES = ('ASC', 'MC', 'DSC', 'IC')


def _local_birth_to_utc(birth_date: date, birth_time: time | None, tz_name: str) -> tuple[datetime, bool]:
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Неизвестный часовой пояс: {tz_name}') from exc
    known = birth_time is not None
    local = datetime.combine(birth_date, birth_time or time(12, 0), tzinfo=zone)
    return local.astimezone(timezone.utc), known


def _natal_chart(birth_date: date, birth_time: time | None, lat: float, lon: float, tz_name: str, city: str) -> dict[str, Any]:
    birth_utc, time_known = _local_birth_to_utc(birth_date, birth_time, tz_name)
    jd = _julian_day(birth_utc)
    planets = _planet_positions(jd)
    cusps, asc = _houses(jd, lat, lon) if time_known else ([], 0.0)
    angles = {}
    if time_known:
        try:
            _, ascmc = swe.houses_ex(jd, float(lat), float(lon), b'P')
            mc = normalize_deg(float(ascmc[1])) if len(ascmc) > 1 else 0.0
        except Exception:
            mc = 0.0
        angles = {
            'ASC': asc,
            'MC': mc,
            'DSC': normalize_deg(asc + 180.0),
            'IC': normalize_deg(mc + 180.0),
        }
    return {
        'birth_date': birth_date.isoformat(),
        'birth_time': birth_time.strftime('%H:%M') if birth_time else None,
        'time_known': time_known,
        'city': city,
        'timezone': tz_name,
        'latitude': float(lat),
        'longitude': float(lon),
        'jd': jd,
        'planets': planets,
        'houses': cusps,
        'angles': angles,
        'ascendant_sign': sign_info(asc)[0] if time_known else None,
        'mc_sign': sign_info(angles.get('MC', 0.0))[0] if time_known else None,
    }


def _aspect_for_pair(lon_a: float, name_a: str, lon_b: float, name_b: str) -> tuple[str, float, float] | None:
    best = _best_aspect(lon_a, lon_b)
    if not best:
        return None
    aspect, orb, diff = best
    allowed = max(SYNASTRY_ORBS.get(name_a, 5.0), SYNASTRY_ORBS.get(name_b, 5.0))
    if orb > allowed:
        return None
    return aspect, orb, diff


def calculate_synastry(
    person1: dict[str, Any],
    person2: dict[str, Any],
    name1: str = '',
    name2: str = '',
) -> dict[str, Any]:
    p1 = _natal_chart(
        person1['birth_date'], person1.get('birth_time'), person1['lat'], person1['lon'], person1['timezone'], person1['city']
    )
    p2 = _natal_chart(
        person2['birth_date'], person2.get('birth_time'), person2['lat'], person2['lon'], person2['timezone'], person2['city']
    )

    aspects: list[dict[str, Any]] = []
    for n1, _ in PLANETS:
        for n2, _ in PLANETS:
            found = _aspect_for_pair(p1['planets'][n1]['longitude'], n1, p2['planets'][n2]['longitude'], n2)
            if not found:
                continue
            aspect, orb, diff = found
            aspects.append({
                'person1_planet': n1,
                'person2_planet': n2,
                'aspect': aspect,
                'orb': round(orb, 2),
                'orb_text': format_degree(orb),
                'person1_sign': p1['planets'][n1]['sign'],
                'person1_position': p1['planets'][n1]['position'],
                'person2_sign': p2['planets'][n2]['sign'],
                'person2_position': p2['planets'][n2]['position'],
                'relationship_weight': 'сильный' if orb <= 2.0 else ('значимый' if orb <= 4.0 else 'рабочий'),
            })

    angle_aspects: list[dict[str, Any]] = []
    if p2['time_known']:
        for n1, _ in PLANETS:
            for angle in ANGLES:
                lon2 = p2['angles'].get(angle)
                if lon2 is None:
                    continue
                best = _best_aspect(p1['planets'][n1]['longitude'], lon2)
                if best and best[1] <= ANGLE_ORB:
                    aspect, orb, _ = best
                    angle_aspects.append({
                        'from_person': 1,
                        'planet': n1,
                        'to_person': 2,
                        'point': angle,
                        'aspect': aspect,
                        'orb': round(orb, 2),
                        'orb_text': format_degree(orb),
                    })
    if p1['time_known']:
        for n2, _ in PLANETS:
            for angle in ANGLES:
                lon1 = p1['angles'].get(angle)
                if lon1 is None:
                    continue
                best = _best_aspect(p2['planets'][n2]['longitude'], lon1)
                if best and best[1] <= ANGLE_ORB:
                    aspect, orb, _ = best
                    angle_aspects.append({
                        'from_person': 2,
                        'planet': n2,
                        'to_person': 1,
                        'point': angle,
                        'aspect': aspect,
                        'orb': round(orb, 2),
                        'orb_text': format_degree(orb),
                    })

    aspects.sort(key=lambda x: (x['orb'], x['person1_planet'], x['person2_planet']))
    angle_aspects.sort(key=lambda x: (x['orb'], x['planet'], x['point']))

    overlays_1_in_2 = []
    if p2['time_known']:
        for n1, _ in PLANETS:
            house = _house_for_longitude(p1['planets'][n1]['longitude'], p2['houses'])
            if house:
                overlays_1_in_2.append({'planet': n1, 'house': house})

    overlays_2_in_1 = []
    if p1['time_known']:
        for n2, _ in PLANETS:
            house = _house_for_longitude(p2['planets'][n2]['longitude'], p1['houses'])
            if house:
                overlays_2_in_1.append({'planet': n2, 'house': house})

    return {
        'name1': name1.strip(),
        'name2': name2.strip(),
        'person1': p1,
        'person2': p2,
        'aspects': aspects,
        'angle_aspects': angle_aspects,
        'overlays_1_in_2': overlays_1_in_2,
        'overlays_2_in_1': overlays_2_in_1,
        'aspect_count': len(aspects),
        'angle_aspect_count': len(angle_aspects),
        'ephemeris_engine': 'Swiss Ephemeris / pysweph',
    }


def _planet_line(name: str, p: dict[str, Any]) -> str:
    retro = ' ретроградное' if p.get('retrograde') else ''
    return f'- {name}: {p["sign"]} {p["position"]}{retro}'


def calculation_for_ai(calc: dict[str, Any]) -> str:
    lines = [
        f"Имя человека 1: {calc['name1'] or 'Человек 1'}",
        f"Имя человека 2: {calc['name2'] or 'Человек 2'}",
        '',
        'ЧЕЛОВЕК 1:',
        f"Дата рождения: {calc['person1']['birth_date']}",
        f"Время рождения: {calc['person1']['birth_time'] or 'неизвестно'}",
        f"Место рождения: {calc['person1']['city']}",
        f"Часовой пояс: {calc['person1']['timezone']}",
        'Планеты:',
    ]
    for name, _ in PLANETS:
        lines.append(_planet_line(name, calc['person1']['planets'][name]))
    if calc['person1']['time_known']:
        lines.append(f"Асцендент: {calc['person1']['ascendant_sign']}")
        lines.append(f"MC: {calc['person1']['mc_sign']}")
    else:
        lines.append('Время рождения неизвестно: дома и углы не используются.')

    lines += [
        '',
        'ЧЕЛОВЕК 2:',
        f"Дата рождения: {calc['person2']['birth_date']}",
        f"Время рождения: {calc['person2']['birth_time'] or 'неизвестно'}",
        f"Место рождения: {calc['person2']['city']}",
        f"Часовой пояс: {calc['person2']['timezone']}",
        'Планеты:',
    ]
    for name, _ in PLANETS:
        lines.append(_planet_line(name, calc['person2']['planets'][name]))
    if calc['person2']['time_known']:
        lines.append(f"Асцендент: {calc['person2']['ascendant_sign']}")
        lines.append(f"MC: {calc['person2']['mc_sign']}")
    else:
        lines.append('Время рождения неизвестно: дома и углы не используются.')

    lines += ['', 'СИНАСТРИЧЕСКИЕ АСПЕКТЫ ВСЕ:']
    if calc['aspects']:
        for a in calc['aspects']:
            lines.append(
                f"- {a['person1_planet']} ({a['person1_sign']} {a['person1_position']}) "
                f"{a['aspect']} {a['person2_planet']} ({a['person2_sign']} {a['person2_position']}) "
                f"(орб {a['orb_text']}, {a['relationship_weight']})"
            )
    else:
        lines.append('- Значимых межпланетных аспектов в заданных орбисах не найдено.')

    if calc['angle_aspects']:
        lines.append('АСПЕКТЫ К УГЛАМ:')
        for a in calc['angle_aspects']:
            from_name = calc['name1'] or 'Человека 1' if a['from_person'] == 1 else calc['name2'] or 'Человека 2'
            to_name = calc['name2'] or 'Человека 2' if a['to_person'] == 2 else calc['name1'] or 'Человека 1'
            lines.append(f"- {from_name}: {a['planet']} {a['aspect']} {to_name} {a['point']} (орб {a['orb_text']})")

    if calc['overlays_1_in_2']:
        lines.append('ПЛАНЕТЫ ЧЕЛОВЕКА 1 В ДОМАХ ЧЕЛОВЕКА 2:')
        lines.extend(f"- {x['planet']}: дом {x['house']}" for x in calc['overlays_1_in_2'])
    if calc['overlays_2_in_1']:
        lines.append('ПЛАНЕТЫ ЧЕЛОВЕКА 2 В ДОМАХ ЧЕЛОВЕКА 1:')
        lines.extend(f"- {x['planet']}: дом {x['house']}" for x in calc['overlays_2_in_1'])

    return '\n'.join(lines)
