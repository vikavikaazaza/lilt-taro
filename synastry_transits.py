from __future__ import annotations

from datetime import date
from typing import Any

from transits import PLANETS, calculate_transits
from synastry import calculate_synastry


def calculate_synastry_transits(
    person1: dict[str, Any],
    person2: dict[str, Any],
    transit_date: date,
    name1: str = '',
    name2: str = '',
) -> dict[str, Any]:
    pair = calculate_synastry(person1, person2, name1, name2)
    t1 = calculate_transits(
        person1['birth_date'], person1.get('birth_time'), transit_date,
        person1['lat'], person1['lon'], person1['timezone'], person1['city']
    )
    t2 = calculate_transits(
        person2['birth_date'], person2.get('birth_time'), transit_date,
        person2['lat'], person2['lon'], person2['timezone'], person2['city']
    )

    def relationship_aspects(calc: dict[str, Any]) -> list[dict[str, Any]]:
        important = {'Солнце', 'Луна', 'Меркурий', 'Венера', 'Марс', 'Юпитер', 'Сатурн'}
        return [a for a in calc['aspects'] if a['natal_planet'] in important or a['transit_planet'] in important]

    return {
        'name1': name1.strip(),
        'name2': name2.strip(),
        'transit_date': transit_date.isoformat(),
        'synastry': pair,
        'person1_transits': t1,
        'person2_transits': t2,
        'person1_relationship_transits': relationship_aspects(t1),
        'person2_relationship_transits': relationship_aspects(t2),
        'ephemeris_engine': 'Swiss Ephemeris / pysweph',
    }


def calculation_for_ai(calc: dict[str, Any]) -> str:
    lines = [
        f"Дата прогноза для пары: {calc['transit_date']}",
        f"Человек 1: {calc['name1'] or 'Человек 1'}",
        f"Человек 2: {calc['name2'] or 'Человек 2'}",
        '',
        'БАЗОВАЯ СИНАСТРИЯ:',
    ]
    pair = calc['synastry']
    for a in pair['aspects']:
        lines.append(
            f"- {a['person1_planet']} {a['aspect']} {a['person2_planet']} (орб {a['orb_text']}, {a['relationship_weight']})"
        )
    for a in pair['angle_aspects']:
        lines.append(f"- Углы: человек {a['from_person']} {a['planet']} {a['aspect']} углу {a['point']} человека {a['to_person']} (орб {a['orb_text']})")

    for idx, key in ((1, 'person1_transits'), (2, 'person2_transits')):
        tc = calc[key]
        lines += ['', f'ТРАНЗИТЫ К КАРТЕ ЧЕЛОВЕКА {idx}:']
        lines.append(f"Расчётный момент: {tc['transit_local_time']}; город: {tc['city']}; часовой пояс: {tc['timezone']}")
        for a in tc['aspects']:
            lines.append(
                f"- {a['transit_planet']} {a['aspect']} натальный {a['natal_planet']} "
                f"(орб {a['orb_text']}, {a['state']}, дом {a['house'] or 'не определён'} )"
            )

    lines += ['', 'ТЕКУЩИЕ ТРАНЗИТЫ, ОСОБЕННО ЗНАЧИМЫЕ ДЛЯ ОТНОШЕНИЙ:']
    for idx, key in ((1, 'person1_relationship_transits'), (2, 'person2_relationship_transits')):
        for a in calc[key]:
            lines.append(f"- Человек {idx}: {a['transit_planet']} {a['aspect']} натальный {a['natal_planet']} (орб {a['orb_text']}, {a['state']})")

    lines += [
        '',
        'Правило интерпретации: отделяй базовую природу связи от текущего периода. ' 
        'Сначала опиши устойчивую динамику пары, затем покажи, какие темы сейчас активируются транзитами у каждого человека и как это может проявляться именно в отношениях.'
    ]
    return '\n'.join(lines)
