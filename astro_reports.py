from __future__ import annotations

from collections import Counter
from typing import Any

ASPECT_NATURE = {
    'Соединение': 'соединение усиливает и смешивает качества двух факторов',
    'Секстиль': 'секстиль даёт рабочую возможность использовать связь конструктивно',
    'Квадрат': 'квадрат создаёт напряжение и требует согласования',
    'Тригон': 'тригон облегчает взаимодействие и поддерживает естественное согласование',
    'Оппозиция': 'оппозиция усиливает притяжение и одновременно показывает полярность',
}

PLANET_ROLE = {
    'Солнце': 'воля, самовыражение, цели и жизненное направление',
    'Луна': 'эмоции, чувство безопасности, привычки и бытовая реакция',
    'Меркурий': 'общение, мышление, договорённости и решения',
    'Венера': 'симпатия, любовь, ценности, удовольствие и нежность',
    'Марс': 'инициатива, действие, сексуальная энергия и границы',
    'Юпитер': 'рост, возможности, убеждения и расширение планов',
    'Сатурн': 'ответственность, ограничения, обязательства и долгосрочность',
    'Уран': 'свобода, резкие перемены и нестандартные решения',
    'Нептун': 'идеализация, интуиция, мечты и неясность',
    'Плутон': 'интенсивность, глубокая перестройка и тема контроля',
}

HOUSE_THEME = {
    1: 'личность, внешний образ и способ проявляться',
    2: 'деньги, личные ресурсы и материальные ценности',
    3: 'разговоры, документы, поездки и повседневные контакты',
    4: 'дом, семья, быт и личное пространство',
    5: 'романтика, влюблённость, удовольствие, творчество и увлечения',
    6: 'ежедневная рутина, работа и распределение обязанностей',
    7: 'партнёрство, договорённости и официальные отношения',
    8: 'общие деньги, интимность, доверие и глубокая близость',
    9: 'поездки, обучение, мировоззрение и расширение горизонтов',
    10: 'карьера, статус, цели и публичная реализация',
    11: 'друзья, сообщества, планы и совместные проекты',
    12: 'скрытые процессы, завершение и необходимость паузы',
}

TRANSIT_THEME = {
    'Солнце': 'проявленность, решения и личная инициатива',
    'Луна': 'эмоциональная реакция, комфорт и бытовая чувствительность',
    'Меркурий': 'разговоры, документы, решения, поездки и переговоры',
    'Венера': 'отношения, симпатия, деньги, покупки и удовольствие',
    'Марс': 'действие, скорость, конкуренция, конфликты и границы',
    'Юпитер': 'рост, полезные контакты, обучение, поездки и новые возможности',
    'Сатурн': 'обязательства, сроки, границы, оформление и проверка устойчивости',
    'Уран': 'смена планов, неожиданные решения и освобождение от старого',
    'Нептун': 'интуиция, вдохновение, идеализация и риск неясности',
    'Плутон': 'глубокая перестройка, ресурсы, власть и отказ от старого формата',
}

PAIR_MEANINGS = {
    frozenset(('Луна', 'Венера')): 'Эмоциональная совместимость: симпатия, забота и ощущение комфорта могут включаться легче.',
    frozenset(('Луна', 'Марс')): 'Эмоции сталкиваются со способом действовать: бытовые мелочи могут быстро становиться причиной спора.',
    frozenset(('Солнце', 'Луна')): 'Связь самовыражения и эмоциональных потребностей влияет на ощущение близости и совместного ритма.',
    frozenset(('Солнце', 'Марс')): 'Воля и действие напрямую включают друг друга; это один из главных индикаторов энергии, притяжения и соперничества.',
    frozenset(('Венера', 'Марс')): 'Романтическая и физическая вовлечённость выражена сильнее; при напряжённом аспекте добавляется раздражительность.',
    frozenset(('Венера', 'Солнце')): 'Симпатия и самоощущение легко включают друг друга; контакт заметен в любовной динамике.',
    frozenset(('Меркурий', 'Меркурий')): 'Схожий или различающийся стиль мышления напрямую влияет на лёгкость разговоров и договорённостей.',
    frozenset(('Меркурий', 'Нептун')): 'Образное и интуитивное общение; при напряжении особенно важна проверка фактов и договорённостей.',
    frozenset(('Плутон', 'Венера')): 'Чувства и внимание становятся интенсивнее; при напряжении чувствительнее темы ревности, влияния и контроля.',
    frozenset(('Сатурн', 'Луна')): 'Ответственность и правила напрямую связаны с эмоциональным комфортом; при напряжении может ощущаться нехватка мягкости.',
    frozenset(('Сатурн', 'Венера')): 'Чувства проверяются временем и реальностью; связь может поддерживать устойчивость, но при напряжении давать ощущение сдерживания.',
    frozenset(('Сатурн', 'Марс')): 'Действие сталкивается с ограничениями; при хорошем аспекте это помогает дисциплине, при напряжении - создаёт сопротивление.',
    frozenset(('Юпитер', 'Сатурн')): 'Рост и расширение легче соединяются с правилами, реалистичными сроками и ответственностью.',
}


def _name(calc: dict[str, Any], idx: int) -> str:
    return str(calc.get(f'name{idx}') or f'Человек {idx}')


def _aspect_sort_key(a: dict[str, Any]) -> tuple[float, str, str]:
    return (float(a.get('orb', 99)), str(a.get('person1_planet', '')), str(a.get('person2_planet', '')))


def _pair_key(a: dict[str, Any]) -> frozenset[str]:
    return frozenset((str(a.get('person1_planet', '')), str(a.get('person2_planet', ''))))


def _is_pair(a: dict[str, Any], left: str, right: str) -> bool:
    return _pair_key(a) == frozenset((left, right))


def _contains(a: dict[str, Any], planet: str) -> bool:
    return planet in {str(a.get('person1_planet', '')), str(a.get('person2_planet', ''))}


def _aspect_weight(orb: float) -> str:
    if orb <= 2:
        return 'сильный'
    if orb <= 4:
        return 'значимый'
    return 'рабочий'


def _pair_text(a: dict[str, Any], n1: str, n2: str) -> str:
    p1, p2 = str(a['person1_planet']), str(a['person2_planet'])
    aspect = str(a['aspect'])
    orb = str(a.get('orb_text', ''))
    s1 = str(a.get('person1_sign', ''))
    s2 = str(a.get('person2_sign', ''))
    pos1 = str(a.get('person1_position', ''))
    pos2 = str(a.get('person2_position', ''))
    meaning = PAIR_MEANINGS.get(frozenset((p1, p2)), f'{p1} и {p2} связывают {PLANET_ROLE.get(p1, "одну сферу")} и {PLANET_ROLE.get(p2, "другую сферу")}.')
    return (
        f'{n1}: {p1} ({s1} {pos1}) {aspect} {n2}: {p2} ({s2} {pos2}); '
        f'орб {orb}, {_aspect_weight(float(a.get("orb", 99)))}. {ASPECT_NATURE.get(aspect, "Связь заметно активирует обе сферы").capitalize()}. {meaning}'
    )


def _angle_text(a: dict[str, Any], calc: dict[str, Any]) -> str:
    source = _name(calc, int(a.get('from_person', 1)))
    target = _name(calc, int(a.get('to_person', 2)))
    point = str(a.get('point', ''))
    planet = str(a.get('planet', ''))
    aspect = str(a.get('aspect', ''))
    orb = str(a.get('orb_text', ''))
    point_meaning = {
        'ASC': 'личный образ и непосредственная реакция',
        'DSC': 'партнёрство и ожидания от союза',
        'MC': 'карьера, статус и публичная реализация',
        'IC': 'дом, семья и внутренняя опора',
    }.get(point, 'угол карты')
    return f'{source}: {planet} {aspect} {target}: {point}; орб {orb}. Задействована тема {point_meaning}.'


def _house_overlay_text(x: dict[str, Any], source_name: str, target_name: str) -> str:
    h = int(x.get('house', 0) or 0)
    return f'{source_name}: {x.get("planet")} -> {h} дом {target_name}; сфера: {HOUSE_THEME.get(h, "не определена")}'


def _syn_key_aspects(calc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    aspects = list(calc.get('aspects', []))
    return {
        'compatibility': [a for a in aspects if _contains(a, 'Солнце') or _contains(a, 'Меркурий') or _contains(a, 'Юпитер')],
        'emotional': [a for a in aspects if _is_pair(a, 'Луна', 'Венера') or _is_pair(a, 'Луна', 'Луна') or _is_pair(a, 'Солнце', 'Луна')],
        'attraction': [a for a in aspects if _is_pair(a, 'Солнце', 'Марс') or _is_pair(a, 'Венера', 'Марс') or _is_pair(a, 'Венера', 'Солнце')],
        'conflict': [a for a in aspects if a.get('aspect') in {'Квадрат', 'Оппозиция'}],
        'perspective': [a for a in aspects if _contains(a, 'Юпитер') or _contains(a, 'Сатурн')],
    }


def build_synastry_interpretation(calc: dict[str, Any]) -> str:
    n1, n2 = _name(calc, 1), _name(calc, 2)
    aspects = sorted(list(calc.get('aspects', [])), key=_aspect_sort_key)
    groups = _syn_key_aspects(calc)
    sections: list[str] = []

    strongest = aspects[:4]
    sections.append('1. Главная динамика\n' + (' '.join(_pair_text(a, n1, n2) for a in strongest) if strongest else 'В заданных орбисах значимых межпланетных аспектов не найдено.'))

    emotional = sorted(groups['emotional'], key=_aspect_sort_key)
    if emotional:
        sections.append('2. Эмоциональный контакт\n' + ' '.join(_pair_text(a, n1, n2) for a in emotional[:4]))
    else:
        sections.append('2. Эмоциональный контакт\nПрямых связей Луна-Венера, Луна-Луна или Солнце-Луна в заданных орбисах нет.')

    attraction = sorted(groups['attraction'], key=_aspect_sort_key)
    if attraction:
        sections.append('3. Притяжение и страсть\n' + ' '.join(_pair_text(a, n1, n2) for a in attraction[:4]))
    else:
        sections.append('3. Притяжение и страсть\nВыраженных связей Солнце-Марс, Венера-Марс или Венера-Солнце в заданных орбисах нет. Это только отсутствие технического акцента по этим парам.')

    conflicts = sorted(groups['conflict'], key=_aspect_sort_key)
    if conflicts:
        sections.append('4. Зоны напряжения\n' + ' '.join(_pair_text(a, n1, n2) for a in conflicts[:5]))
    else:
        sections.append('4. Зоны напряжения\nКвадратов и оппозиций в выбранных орбисах не найдено.')

    house_lines = []
    house_lines.extend(_house_overlay_text(x, n1, n2) for x in calc.get('overlays_1_in_2', []))
    house_lines.extend(_house_overlay_text(x, n2, n1) for x in calc.get('overlays_2_in_1', []))
    sections.append('5. Совместная жизнь и практические сферы\n' + (' '.join(house_lines[:8]) if house_lines else 'Дома не рассчитаны: для соответствующего человека не указано точное время рождения.'))

    durable = sorted(groups['perspective'], key=_aspect_sort_key)
    sections.append('6. Долгосрочная динамика\n' + (' '.join(_pair_text(a, n1, n2) for a in durable[:4]) if durable else 'Связей Юпитера/Сатурна в заданных орбисах нет.'))

    growth = []
    for a in conflicts:
        pair = {str(a.get('person1_planet')), str(a.get('person2_planet'))}
        if 'Луна' in pair:
            growth.append('говорить о чувствах и бытовых потребностях прямо, не переводя реакцию в обвинение')
        if 'Меркурий' in pair:
            growth.append('фиксировать важные договорённости словами и проверять, одинаково ли вы поняли сказанное')
        if 'Марс' in pair:
            growth.append('заранее договариваться о темпе действий и границах ответственности')
        if 'Венера' in pair:
            growth.append('не проверять чувства ревностью, давлением или молчанием')
        if 'Сатурн' in pair:
            growth.append('прояснять сроки, обязательства и финансовые правила заранее')
        if 'Плутон' in pair:
            growth.append('не превращать сильную вовлечённость в борьбу за влияние')
    growth = list(dict.fromkeys(growth))[:4]
    if not growth:
        growth = ['прямо проговаривать ожидания', 'разделять чувства и факты', 'заранее обсуждать бытовые правила']
    sections.append('7. Практические точки роста\n' + ' '.join(f'{i+1}) {x}.' for i, x in enumerate(growth)))

    if calc.get('angle_aspects'):
        sections.append('8. Угловые связи\n' + ' '.join(_angle_text(a, calc) for a in sorted(calc['angle_aspects'], key=lambda x: float(x.get('orb', 99)))[:4]))

    counts = Counter(str(a.get('aspect')) for a in aspects)
    stats = ', '.join(f'{k}: {counts.get(k, 0)}' for k in ('Соединение', 'Секстиль', 'Квадрат', 'Тригон', 'Оппозиция'))
    tight = sum(1 for a in aspects if float(a.get('orb', 99)) <= 2)
    sections.append(f'9. Итог и статистика\nВсего межпланетных аспектов: {len(aspects)}. Плотность по типам: {stats}. Точных/очень тесных связей с орбом до 2°: {tight}. Основные выводы следует делать по совокупности аспектов, а не по одному контакту.')
    return '\n\n'.join(sections)


def synastry_pdf_sections(calc: dict[str, Any]) -> list[tuple[str, list[str]]]:
    n1, n2 = _name(calc, 1), _name(calc, 2)
    p1, p2 = calc.get('person1', {}), calc.get('person2', {})
    aspects = sorted(list(calc.get('aspects', [])), key=_aspect_sort_key)
    sections: list[tuple[str, list[str]]] = []

    basic = [
        f'{n1}: {p1.get("birth_date", "")} | {p1.get("birth_time") or "время неизвестно"} | {p1.get("city", "")} | {p1.get("timezone", "")}',
        f'{n2}: {p2.get("birth_date", "")} | {p2.get("birth_time") or "время неизвестно"} | {p2.get("city", "")} | {p2.get("timezone", "")}',
        f'Межпланетных аспектов: {len(aspects)}; аспектов к углам: {len(calc.get("angle_aspects", []))}',
        'Дома и углы рассчитываются только для человека с известным временем рождения.',
    ]
    sections.append(('Исходные данные', basic))

    def planet_lines(person: dict[str, Any]) -> list[str]:
        lines = []
        for planet, data in person.get('planets', {}).items():
            retro = ' | ретроградное' if data.get('retrograde') else ''
            lines.append(f'{planet}: {data.get("sign", "")} {data.get("position", "")}{retro}')
        if person.get('time_known'):
            lines.append(f'ASC: {person.get("ascendant_sign", "")}')
            lines.append(f'MC: {person.get("mc_sign", "")}')
        return lines
    sections.append((f'Натальные положения - {n1}', planet_lines(p1)))
    sections.append((f'Натальные положения - {n2}', planet_lines(p2)))

    groups = _syn_key_aspects(calc)
    labels = [
        ('compatibility', '1. Главная динамика и совместимость'),
        ('emotional', '2. Эмоциональный контакт'),
        ('attraction', '3. Притяжение и страсть'),
        ('conflict', '4. Конфликты и точки трения'),
        ('perspective', '5. Долгосрочная динамика'),
    ]
    for key, title in labels:
        items = sorted(groups[key], key=_aspect_sort_key)
        if items:
            sections.append((title, [_pair_text(a, n1, n2) for a in items]))
        else:
            sections.append((title, ['В заданных орбисах отдельные аспекты этой группы не найдены.']))

    other = [a for a in aspects if all(a not in groups[k] for k in groups)]
    if other:
        sections.append(('6. Остальные межпланетные аспекты', [_pair_text(a, n1, n2) for a in other]))

    angle_items = sorted(calc.get('angle_aspects', []), key=lambda x: float(x.get('orb', 99)))
    sections.append(('7. Аспекты к ASC / DSC / MC / IC', [_angle_text(a, calc) for a in angle_items] or ['Аспекты к углам не рассчитаны или не найдены.']))

    overlays = []
    overlays.extend(_house_overlay_text(x, n1, n2) for x in calc.get('overlays_1_in_2', []))
    overlays.extend(_house_overlay_text(x, n2, n1) for x in calc.get('overlays_2_in_1', []))
    sections.append(('8. Планеты в домах партнёра', overlays or ['Дома недоступны: не указано точное время рождения.']))

    # House focus counts are useful and deterministic.
    house_counts_1 = Counter(int(x.get('house')) for x in calc.get('overlays_1_in_2', []) if x.get('house'))
    house_counts_2 = Counter(int(x.get('house')) for x in calc.get('overlays_2_in_1', []) if x.get('house'))
    stat_lines = []
    if house_counts_1:
        stat_lines.append(f'{n1} в домах {n2}: ' + ', '.join(f'{h} дом - {house_counts_1[h]} планет' for h in sorted(house_counts_1)))
    if house_counts_2:
        stat_lines.append(f'{n2} в домах {n1}: ' + ', '.join(f'{h} дом - {house_counts_2[h]} планет' for h in sorted(house_counts_2)))
    counts = Counter(str(a.get('aspect')) for a in aspects)
    stat_lines.append('Аспекты: ' + ', '.join(f'{k} - {counts.get(k, 0)}' for k in ('Соединение','Секстиль','Квадрат','Тригон','Оппозиция')))
    stat_lines.append(f'Орб до 2°: {sum(1 for a in aspects if float(a.get("orb", 99)) <= 2)}; 2-4°: {sum(1 for a in aspects if 2 < float(a.get("orb", 99)) <= 4)}; более 4°: {sum(1 for a in aspects if float(a.get("orb", 99)) > 4)}')
    sections.append(('9. Статистика расчёта', stat_lines))

    sections.append(('10. Краткий вывод', build_synastry_interpretation(calc).split('\n\n')[:9]))
    return sections


def _transit_planet_phrase(name: str) -> str:
    return f'Транзитное {name}' if name not in {'Луна', 'Венера'} else f'Транзитная {name}'


def _transit_aspect_text(a: dict[str, Any]) -> str:
    tp = str(a.get('transit_planet', ''))
    np = str(a.get('natal_planet', ''))
    aspect = str(a.get('aspect', ''))
    orb = str(a.get('orb_text', ''))
    state = str(a.get('state', ''))
    house = a.get('house')
    retro = ' | ретроградный транзит' if a.get('transit_retrograde') else ''
    theme = TRANSIT_THEME.get(tp, 'заметная тема периода')
    target = PLANET_ROLE.get(np, 'натальный фактор')
    sphere = f' | дом {int(house)}: {HOUSE_THEME.get(int(house), "")}' if house else ''
    return f'{_transit_planet_phrase(tp)} {aspect} к натальному {np}; орб {orb}; состояние: {state}{retro}{sphere}. Активная тема: {theme}. Натальная точка: {target}.'


def _event_for_transit(a: dict[str, Any]) -> str:
    tp, np = str(a.get('transit_planet','')), str(a.get('natal_planet',''))
    aspect, state = str(a.get('aspect','')), str(a.get('state',''))
    house = a.get('house')
    event_map = {
        'Меркурий': 'разговор, документ, поездка, переговоры или пересмотр решения',
        'Венера': 'встреча, сближение, примирение, покупка или финансовое решение',
        'Марс': 'быстрое действие, запуск, спор или необходимость отстоять позицию',
        'Юпитер': 'предложение, обучение, поездка, рост контактов или расширение возможностей',
        'Сатурн': 'оформление, обязательство, проверка результата или необходимость принять ограничение',
        'Уран': 'резкая смена плана, неожиданный контакт или освобождение от старого формата',
        'Нептун': 'период вдохновения/идеализации; важные детали требуют перепроверки',
        'Плутон': 'глубокая перестройка, решение о ресурсах, влиянии или завершении старого формата',
        'Солнце': 'ситуация, где нужно проявиться, выбрать направление или взять инициативу',
        'Луна': 'эмоционально заметный день, семейный вопрос или быстрая смена настроения',
    }
    verb = event_map.get(tp, 'заметное событие в активной сфере')
    modifier = 'напряжённый' if aspect in {'Квадрат','Оппозиция'} else 'поддерживающий'
    state_text = {'точный':'пик акцента приходится на выбранную дату','сходящийся':'тема нарастает','расходящийся':'тема проходит стадию развязки'}.get(state, 'фаза зависит от положения на орбисе')
    sphere = f' Сфера: {HOUSE_THEME[int(house)]}.' if house else ''
    return f'{modifier.capitalize()} сценарий: {verb}; транзитный {tp} затрагивает натальный {np}. {state_text}.{sphere}'


def _timing_line(a: dict[str, Any]) -> str:
    tp, state = str(a.get('transit_planet','')), str(a.get('state',''))
    if tp == 'Луна': horizon = 'часы - 1 день'
    elif tp in {'Солнце','Меркурий','Венера','Марс'}: horizon = 'дни - несколько недель'
    elif tp in {'Юпитер','Сатурн'}: horizon = 'недели - месяцы'
    else: horizon = 'месяцы и дольше'
    if state == 'точный': return f'Пик на выбранную дату; ориентировочный рабочий горизонт: {horizon}.'
    if state == 'сходящийся': return f'Аспект набирает силу; ориентировочный горизонт: {horizon}.'
    return f'Аспект уже расходится; ориентировочный горизонт развязки: {horizon}.'


def build_transit_interpretation(calc: dict[str, Any]) -> str:
    date = str(calc.get('transit_date', ''))
    city = str(calc.get('city', ''))
    aspects = sorted(list(calc.get('aspects', [])), key=lambda a: (float(a.get('orb', 99)), str(a.get('transit_planet','')), str(a.get('natal_planet',''))))
    if not aspects:
        return f'1. Дата\n{date}, {city}. В заданных орбисах основных транзитных аспектов к натальным планетам не найдено.\n\n2. Что важно\nСильных транзитных акцентов по выбранной системе нет; события лучше не связывать с отсутствующими аспектами.'
    top = aspects[:5]
    hard = [a for a in aspects if a.get('aspect') in {'Квадрат','Оппозиция'}]
    long = [a for a in aspects if str(a.get('transit_planet')) in {'Юпитер','Сатурн','Уран','Нептун','Плутон'}]
    fast = [a for a in aspects if str(a.get('transit_planet')) in {'Солнце','Луна','Меркурий','Венера','Марс'}]
    sections = [
        f'1. Главные акценты {date}\n' + ' '.join(_transit_aspect_text(a) for a in top[:3]),
        '2. Возможные конкретные сценарии\n' + ' '.join(_event_for_transit(a) for a in top[:4]),
        '3. Долгосрочные процессы\n' + (' '.join(_transit_aspect_text(a) for a in long[:4]) if long else 'Юпитер, Сатурн, Уран, Нептун и Плутон не дают отдельного выраженного акцента в заданных орбисах.'),
        '4. Быстрые триггеры\n' + (' '.join(_transit_aspect_text(a) for a in fast[:5]) if fast else 'Быстрых транзитов в заданном орбисе нет.'),
        '5. Напряжённые зоны\n' + (' '.join(_event_for_transit(a) for a in hard[:5]) if hard else 'Квадратов и оппозиций на выбранную дату не найдено.'),
        '6. Сроки\n' + ' '.join(_timing_line(a) for a in top[:4]),
        '7. Итог\n' + _event_for_transit(top[0]),
    ]
    return '\n\n'.join(sections)


def transit_pdf_sections(calc: dict[str, Any]) -> list[tuple[str, list[str]]]:
    aspects = sorted(list(calc.get('aspects', [])), key=lambda a: (float(a.get('orb', 99)), str(a.get('transit_planet','')), str(a.get('natal_planet',''))))
    date = str(calc.get('transit_date', ''))
    city = str(calc.get('city', ''))
    sections: list[tuple[str, list[str]]] = []
    sections.append(('Исходные данные', [
        f'Дата транзита: {date}',
        f'Место рождения: {city}',
        f'Дата рождения: {calc.get("birth_date", "")}',
        f'Время рождения: {calc.get("birth_time") or "неизвестно"}',
        f'Расчётный момент: {calc.get("transit_local_time", "")}',
        f'Часовой пояс: {calc.get("timezone", "")}',
        f'Время рождения известно: {"да" if calc.get("time_known") else "нет"}',
        'При неизвестном времени рождения дома и ASC не используются, положение натальной Луны отмечается как приблизительное.',
    ]))

    def positions(title: str, data: dict[str, Any]) -> list[str]:
        out = []
        for planet, p in data.items():
            retro = ' | ретроградное' if p.get('retrograde') else ''
            approx = ' | приблизительно' if title.startswith('Натальные') and planet == 'Луна' and not calc.get('time_known') else ''
            out.append(f'{planet}: {p.get("sign", "")} {p.get("position", "")}{retro}{approx}')
        return out
    sections.append(('Натальные положения', positions('Натальные', calc.get('natal', {}))))
    sections.append(('Транзитные положения', positions('Транзитные', calc.get('transit', {}))))

    if aspects:
        sections.append(('1. Все активные аспекты на выбранную дату', [_transit_aspect_text(a) for a in aspects]))
        sections.append(('2. Конкретные событийные сценарии', [_event_for_transit(a) + ' ' + _timing_line(a) for a in aspects]))
    else:
        sections.append(('1. Все активные аспекты на выбранную дату', ['Значимых аспектов в заданных орбисах не найдено.']))

    long = [a for a in aspects if str(a.get('transit_planet')) in {'Юпитер','Сатурн','Уран','Нептун','Плутон'}]
    hard = [a for a in aspects if a.get('aspect') in {'Квадрат','Оппозиция'}]
    supportive = [a for a in aspects if a.get('aspect') in {'Тригон','Секстиль'}]
    fast = [a for a in aspects if str(a.get('transit_planet')) in {'Солнце','Луна','Меркурий','Венера','Марс'}]
    sections.append(('3. Долгосрочные процессы', [_transit_aspect_text(a) + ' ' + _timing_line(a) for a in long] or ['Нет выраженного акцента внешних планет.']))
    sections.append(('4. Любовь, отношения и социальные события', [_event_for_transit(a) for a in aspects if str(a.get('transit_planet')) in {'Венера','Марс','Юпитер'} or str(a.get('natal_planet')) in {'Венера','Марс','Солнце','Луна'}] or ['Отдельного набора таких аспектов в заданном орбисе нет.']))
    sections.append(('5. Работа, деньги, документы и решения', [_event_for_transit(a) for a in aspects if str(a.get('transit_planet')) in {'Меркурий','Венера','Марс','Юпитер','Сатурн'} or str(a.get('natal_planet')) in {'Меркурий','Юпитер','Сатурн'}] or ['В заданном наборе нет отдельного выраженного акцента этих сфер.']))
    sections.append(('6. Эмоциональный фон', [_transit_aspect_text(a) for a in aspects if str(a.get('transit_planet')) == 'Луна'] or ['Отдельного точного лунного аспекта к натальным планетам не найдено.']))
    sections.append(('7. Напряжение и точки риска', [_event_for_transit(a) for a in hard] or ['Квадратов и оппозиций нет.']))
    sections.append(('8. Возможности и поддерживающие связи', [_event_for_transit(a) for a in supportive] or ['Тригонов и секстилей нет.']))
    sections.append(('9. Быстрые триггеры', [_transit_aspect_text(a) + ' ' + _timing_line(a) for a in fast] or ['Выраженных быстрых триггеров в заданных орбисах нет.']))

    if calc.get('houses'):
        house_lines = [f'{i+1} дом: {((calc["houses"][i]) % 360):.2f}°' for i in range(min(12, len(calc['houses'])))]
        if calc.get('ascendant_sign'):
            house_lines.append(f'ASC: {calc.get("ascendant_sign")}')
        sections.append(('10. Дома и ASC', house_lines))

    counts = Counter(str(a.get('aspect')) for a in aspects)
    stat_lines = [
        f'Всего активных аспектов: {len(aspects)}',
        'По типам: ' + ', '.join(f'{k} - {counts.get(k, 0)}' for k in ('Соединение','Секстиль','Квадрат','Тригон','Оппозиция')),
        f'Орб до 1°: {sum(1 for a in aspects if float(a.get("orb",99)) <= 1)}',
        f'Орб до 2°: {sum(1 for a in aspects if float(a.get("orb",99)) <= 2)}',
        f'Напряжённых аспектов: {len(hard)}; поддерживающих: {len(supportive)}',
    ]
    sections.append(('11. Статистика расчёта', stat_lines))
    sections.append(('12. Итог', build_transit_interpretation(calc).split('\n\n')))
    return sections
