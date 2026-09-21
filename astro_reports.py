from __future__ import annotations

from collections import defaultdict
from typing import Any


ASPECT_NATURE = {
    'Соединение': 'соединение усиливает и смешивает качества двух факторов',
    'Секстиль': 'секстиль даёт возможность использовать связь конструктивно и легче находить рабочий формат',
    'Квадрат': 'квадрат создаёт напряжение, которое требует согласования и осознанного действия',
    'Тригон': 'тригон облегчает взаимодействие и поддерживает естественное взаимопонимание',
    'Оппозиция': 'оппозиция создаёт сильное притяжение вместе с полярностью и разницей реакций',
}

PLANET_ROLE = {
    'Солнце': 'воли, самовыражения и направления жизни',
    'Луна': 'эмоциональных реакций, чувства безопасности и бытового комфорта',
    'Меркурий': 'общения, мышления, договорённостей и обмена информацией',
    'Венера': 'симпатии, любви, удовольствия, ценностей и проявления нежности',
    'Марс': 'инициативы, действия, сексуальной энергии и защиты своих границ',
    'Юпитер': 'роста, возможностей, убеждений и расширения планов',
    'Сатурн': 'ответственности, границ, обязательств и долгосрочных решений',
    'Уран': 'свободы, перемен и неожиданных поворотов',
    'Нептун': 'идеализации, интуиции, мечтаний и тонкого эмоционального восприятия',
    'Плутон': 'интенсивности, глубинных изменений и темы контроля/силы',
}

HOUSE_THEME = {
    1: 'личность, внешний образ и способ проявляться',
    2: 'деньги, личные ресурсы и материальные ценности',
    3: 'разговоры, документы, поездки и повседневные контакты',
    4: 'дом, семья, быт и личное пространство',
    5: 'романтика, влюблённость, удовольствие, творчество и совместные увлечения',
    6: 'ежедневная рутина, работа и распределение практических обязанностей',
    7: 'партнёрство, договорённости и официальные отношения',
    8: 'общие деньги, интимность, доверие и глубокая близость',
    9: 'поездки, обучение, мировоззрение и расширение горизонтов',
    10: 'карьера, статус, цели и публичная реализация',
    11: 'друзья, сообщества, планы на будущее и совместные проекты',
    12: 'скрытые процессы, завершение старых сюжетов и необходимость паузы',
}

TRANSIT_THEME = {
    'Солнце': 'активирует тему проявленности, решений и личной инициативы',
    'Луна': 'быстро усиливает эмоциональную реакцию и потребность в комфорте',
    'Меркурий': 'активирует разговоры, документы, решения, поездки и обмен информацией',
    'Венера': 'усиливает тему отношений, симпатии, денег и удовольствия',
    'Марс': 'добавляет скорость, напор, конкуренцию и необходимость действовать',
    'Юпитер': 'расширяет возможности, контакты, обучение и планы',
    'Сатурн': 'проверяет обязательства, границы, устойчивость и реальные сроки',
    'Уран': 'может приносить резкую смену планов и потребность в свободе',
    'Нептун': 'усиливает интуитивность, мечты и одновременно риск неясности',
    'Плутон': 'обостряет глубокую перестройку, тему власти и отказа от старого сценария',
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


def _aspect_descriptor(aspect: str) -> str:
    return ASPECT_NATURE.get(aspect, 'связь показывает заметное взаимодействие двух факторов')


def _syn_pair_sentence(a: dict[str, Any], n1: str, n2: str) -> str:
    p1, p2 = str(a['person1_planet']), str(a['person2_planet'])
    aspect = str(a['aspect'])
    orb = str(a.get('orb_text', ''))
    sentence = f'{n1}: {p1} {aspect} {n2}: {p2} (орб {orb}) - {_aspect_descriptor(aspect)}.'

    special = {
        frozenset(('Луна', 'Венера')): 'Это сочетание особенно связано с симпатией, заботой и тем, насколько комфортно партнёры чувствуют себя рядом.',
        frozenset(('Марс', 'Солнце')): 'Такой контакт показывает, как воля и инициатива одного человека включают активность другого, поэтому тема притяжения и соперничества здесь особенно заметна.',
        frozenset(('Венера', 'Марс')): 'Контакт усиливает романтическую и физическую вовлечённость, а при напряжённом аспекте может одновременно повышать раздражительность.',
        frozenset(('Солнце', 'Луна')): 'Контакт связывает самовыражение одного человека с эмоциональными потребностями другого и влияет на ощущение «мы».',
        frozenset(('Меркурий', 'Нептун')): 'Здесь возможны образное мышление, интуитивное считывание и совместные фантазии; при напряжении особенно важна проверка фактов.',
        frozenset(('Плутон', 'Венера')): 'Контакт усиливает эмоциональную и чувственную вовлечённость и может делать тему внимания, ревности или влияния особенно чувствительной при напряжённом аспекте.',
        frozenset(('Луна', 'Марс')): 'Эмоциональная реакция одного человека может быстро включаться на способ действовать другого, поэтому бытовые ситуации могут становиться более горячими.',
        frozenset(('Сатурн', 'Луна')): 'Контакт связывает эмоциональные потребности с ответственностью и правилами; при напряжении один человек может ощущать нехватку мягкости или пространства.',
        frozenset(('Сатурн', 'Венера')): 'Связь проверяет чувства временем, правилами и реальностью; она может поддерживать устойчивость, но при напряжении ощущаться как сдерживание.',
        frozenset(('Сатурн', 'Марс')): 'Контакт учит соотносить действие и ограничения: совместная работа может стать эффективной, но разный темп иногда вызывает сопротивление.',
        frozenset(('Юпитер', 'Сатурн')): 'Связь помогает соединять расширение планов с реалистичными рамками и сроками.',
    }
    if frozenset((p1, p2)) in special:
        sentence += ' ' + special[frozenset((p1, p2))]
    return sentence


def _angle_sentence(a: dict[str, Any], calc: dict[str, Any]) -> str:
    p = str(a.get('planet', ''))
    point = str(a.get('point', ''))
    aspect = str(a.get('aspect', ''))
    orb = str(a.get('orb_text', ''))
    source_name = _name(calc, int(a.get('from_person', 1)))
    target_name = _name(calc, int(a.get('to_person', 2)))
    point_meaning = {
        'ASC': 'личный образ и непосредственная реакция',
        'DSC': 'сценарий партнёрства и ожидания от союза',
        'MC': 'цели, статус и публичная реализация',
        'IC': 'дом, семья и внутреннее чувство опоры',
    }.get(point, 'угол карты')
    return f'{source_name}: {p} {aspect} {target_name}: {point} (орб {orb}) - связь с темой {point_meaning}.'


def _top_lines(items: list[dict[str, Any]], calc: dict[str, Any], limit: int = 3) -> list[str]:
    n1, n2 = _name(calc, 1), _name(calc, 2)
    return [_syn_pair_sentence(a, n1, n2) for a in sorted(items, key=_aspect_sort_key)[:limit]]


def _house_lines(calc: dict[str, Any], limit: int = 8) -> list[str]:
    out: list[str] = []
    n1, n2 = _name(calc, 1), _name(calc, 2)
    for x in calc.get('overlays_1_in_2', []):
        h = int(x.get('house', 0) or 0)
        if h in HOUSE_THEME:
            out.append(f'{n1}: {x.get("planet")} попадает в {h} дом {n2} - акцент на теме {HOUSE_THEME[h]}.')
    for x in calc.get('overlays_2_in_1', []):
        h = int(x.get('house', 0) or 0)
        if h in HOUSE_THEME:
            out.append(f'{n2}: {x.get("planet")} попадает в {h} дом {n1} - акцент на теме {HOUSE_THEME[h]}.')
    return out[:limit]


def build_synastry_interpretation(calc: dict[str, Any]) -> str:
    aspects = sorted(list(calc.get('aspects', [])), key=_aspect_sort_key)
    hard = [a for a in aspects if a.get('aspect') in {'Квадрат', 'Оппозиция'}]
    emotional = [a for a in aspects if _is_pair(a, 'Луна', 'Венера') or _is_pair(a, 'Луна', 'Луна') or _is_pair(a, 'Солнце', 'Луна')]
    attraction = [a for a in aspects if _is_pair(a, 'Марс', 'Солнце') or _is_pair(a, 'Венера', 'Марс') or _is_pair(a, 'Венера', 'Солнце')]
    compatibility = [a for a in aspects if _contains(a, 'Солнце') or _contains(a, 'Луна') or _contains(a, 'Меркурий') or _contains(a, 'Юпитер')]
    durable = [a for a in aspects if _contains(a, 'Юпитер') or _contains(a, 'Сатурн')]
    conflict = [a for a in hard if _contains(a, 'Марс') or _contains(a, 'Сатурн') or _contains(a, 'Плутон') or _contains(a, 'Меркурий') or _contains(a, 'Луна')]

    n1, n2 = _name(calc, 1), _name(calc, 2)
    sections: list[str] = []

    # 1. Main dynamics
    main_lines = _top_lines(compatibility or aspects, calc, 3)
    if calc.get('angle_aspects'):
        main_lines.append(_angle_sentence(sorted(calc['angle_aspects'], key=lambda x: float(x.get('orb', 99)))[0], calc))
    body1 = ' '.join(main_lines) if main_lines else 'В расчёте нет выраженных межпланетных аспектов в заданных орбисах, поэтому основной сюжет лучше оценивать по домам и углам.'
    sections.append(f'1. Уровень совместимости и главная динамика\n{body1}')

    # 2. Emotional contact
    emotional_lines = _top_lines(emotional, calc, 3)
    if emotional_lines:
        body2 = ' '.join(emotional_lines)
    else:
        body2 = 'Прямых связей Луна-Венера, Луна-Луна или Солнце-Луна в заданных орбисах нет. Эмоциональную совместимость тогда лучше читать через остальные аспекты и попадания планет в дома.'
    sections.append(f'2. Эмоциональный контакт\n{body2}')

    # 3. Attraction
    attraction_lines = _top_lines(attraction, calc, 3)
    if attraction_lines:
        body3 = ' '.join(attraction_lines)
    else:
        body3 = 'Значимых связей Марс-Солнце, Венера-Марс или Венера-Солнце в заданном орбисе не найдено. Это означает только отсутствие выраженного технического акцента именно в этом блоке.'
    sections.append(f'3. Притяжение и страсть\n{body3}')

    # 4. Conflicts
    conflict_lines = _top_lines(conflict or hard, calc, 4)
    if conflict_lines:
        body4 = ' '.join(conflict_lines)
    else:
        body4 = 'Квадратов и оппозиций в расчёте не найдено. Это означает, что в выбранной системе аспектов нет выраженного набора жёстких межпланетных связей.'
    sections.append(f'4. Сферы конфликтов\n{body4}')

    # 5. Love / closeness / daily life
    love_lines = []
    for a in sorted(aspects, key=_aspect_sort_key):
        if _is_pair(a, 'Венера', 'Плутон') or _is_pair(a, 'Луна', 'Марс') or _is_pair(a, 'Венера', 'Луна'):
            love_lines.append(_syn_pair_sentence(a, n1, n2))
    if not love_lines:
        love_lines = _top_lines(hard, calc, 2)
    house_lines = _house_lines(calc, 4)
    body5 = ' '.join(love_lines[:3] + house_lines[:4]) if (love_lines or house_lines) else 'По домам не удалось получить дополнительный бытовой акцент, а ключевые аспекты близости не попали в заданные орбисы.'
    sections.append(f'5. Любовь, близость и совместная жизнь\n{body5}')

    # 6. Long-term potential
    durable_lines = _top_lines(durable, calc, 3)
    angle_lines = [_angle_sentence(a, calc) for a in sorted(calc.get('angle_aspects', []), key=lambda x: float(x.get('orb', 99)))[:3]]
    partner_house = [x for x in _house_lines(calc, 12) if '7 дом' in x]
    body6_parts = durable_lines + angle_lines + partner_house[:2]
    body6 = ' '.join(body6_parts) if body6_parts else 'Юпитер-Сатурн и угловые связи в заданном орбисе не дают отдельного сильного акцента. Перспективу лучше оценивать по совокупности остальных аспектов, а не по одному показателю.'
    sections.append(f'6. Перспективы союза\n{body6}')

    # 7. Growth
    growth: list[str] = []
    for a in sorted(hard, key=_aspect_sort_key):
        p1 = str(a.get('person1_planet'))
        p2 = str(a.get('person2_planet'))
        if 'Луна' in (p1, p2):
            growth.append('бережно проговаривать эмоциональные потребности и не переводить бытовое напряжение в личную претензию')
        if 'Меркурий' in (p1, p2):
            growth.append('проверять формулировки и не спорить с предположением, что партнёр уже понял сказанное')
        if 'Марс' in (p1, p2):
            growth.append('разделять инициативу и контроль, заранее договариваясь о темпе и порядке действий')
        if 'Венера' in (p1, p2):
            growth.append('не проверять чувства через ревность, давление или молчание')
        if 'Сатурн' in (p1, p2):
            growth.append('фиксировать границы, обязательства и сроки словами, а не ожиданиями')
        if 'Плутон' in (p1, p2):
            growth.append('не превращать сильную вовлечённость в борьбу за влияние')
    growth = list(dict.fromkeys(growth))[:3]
    if not growth:
        growth = [
            'говорить о потребностях прямо',
            'договариваться о бытовых и финансовых правилах заранее',
            'оставлять друг другу пространство для самостоятельности',
        ]
    body7 = ' '.join(f'{i+1}) {x}.' for i, x in enumerate(growth))
    sections.append(f'7. Точки роста\n{body7}')

    # 8. Summary
    top = aspects[:2]
    top_names = ', '.join(f"{a['person1_planet']} {a['aspect']} {a['person2_planet']}" for a in top)
    if hard:
        hard_names = ', '.join(f"{a['person1_planet']} {a['aspect']} {a['person2_planet']}" for a in hard[:2])
        body8 = f'В расчёте наиболее заметны связи {top_names or "между личными планетами"}. Наиболее чувствительная зона - {hard_names}; она требует осознанных договорённостей и не означает автоматического конфликта. Сильные стороны союза лучше раскрываются там, где партнёры прямо проговаривают ожидания и не подменяют факты догадками.'
    else:
        body8 = f'В расчёте наиболее заметны связи {top_names or "между планетами пары"}. Выраженного набора квадратов и оппозиций не найдено, поэтому основной акцент приходится на способ общения, эмоциональный обмен и практические договорённости. Реальную динамику отношений стоит наблюдать по тому, как эти темы проявляются в конкретных ситуациях.'
    sections.append(f'8. Итог\n{body8}')
    return '\n\n'.join(sections)


def _transit_planet_name(name: str) -> str:
    feminine = {'Луна': 'Транзитная', 'Венера': 'Транзитная'}
    neuter = {'Солнце': 'Транзитное'}
    return f"{feminine.get(name, neuter.get(name, 'Транзитный'))} {name}"


NATAL_CASE = {
    'Солнце': 'Солнцу', 'Луна': 'Луне', 'Меркурий': 'Меркурию', 'Венера': 'Венере', 'Марс': 'Марсу',
    'Юпитер': 'Юпитеру', 'Сатурн': 'Сатурну', 'Уран': 'Урану', 'Нептун': 'Нептуну', 'Плутон': 'Плутону',
}
NATAL_INSTRUMENTAL = {
    'Солнце': 'Солнцем', 'Луна': 'Луной', 'Меркурий': 'Меркурием', 'Венера': 'Венерой', 'Марс': 'Марсом',
    'Юпитер': 'Юпитером', 'Сатурн': 'Сатурном', 'Уран': 'Ураном', 'Нептун': 'Нептуном', 'Плутон': 'Плутоном',
}
ASPECT_CASE = {
    'Соединение': 'соединение с', 'Секстиль': 'секстиль к', 'Квадрат': 'квадрат к', 'Тригон': 'тригон к', 'Оппозиция': 'оппозиция к',
}


def _transit_label(a: dict[str, Any]) -> str:
    tp = str(a.get('transit_planet', ''))
    np = str(a.get('natal_planet', ''))
    aspect = str(a.get('aspect', ''))
    connector = ASPECT_CASE.get(aspect, aspect.lower())
    target = NATAL_INSTRUMENTAL.get(np, np) if aspect == 'Соединение' else NATAL_CASE.get(np, np)
    return f"{_transit_planet_name(tp)} {connector} натальному {target}" if aspect != 'Соединение' else f"{_transit_planet_name(tp)} {connector} {target}"


def _transit_aspect_sentence(a: dict[str, Any], calc: dict[str, Any]) -> str:
    tp = str(a.get('transit_planet', ''))
    np = str(a.get('natal_planet', ''))
    aspect = str(a.get('aspect', ''))
    orb = str(a.get('orb_text', ''))
    state = str(a.get('state', ''))
    house = a.get('house')
    retro = bool(a.get('transit_retrograde'))
    house_text = f' Акцент затрагивает {int(house)} дом: {HOUSE_THEME[int(house)]}.' if house else ''
    retro_text = ' Ретроградность усиливает тему пересмотра, возврата к старому вопросу или повторного обсуждения.' if retro else ''
    theme = TRANSIT_THEME.get(tp, 'это активирует заметную тему периода').strip().rstrip('.')
    theme = theme[:1].upper() + theme[1:] + '.'
    return f'{_transit_label(a)} (орб {orb}, {state}). {theme} Задействована тема {PLANET_ROLE.get(np, "натального показателя")}.{house_text}{retro_text}'


def _transit_sort_key(a: dict[str, Any]) -> tuple[float, int, str, str]:
    # Prefer exact/tighter aspects, with outer planets treated as slower background.
    rank = {'точный': 0, 'сходящийся': 1, 'расходящийся': 2}.get(str(a.get('state')), 3)
    return (float(a.get('orb', 99)), rank, str(a.get('transit_planet', '')), str(a.get('natal_planet', '')))


def _event_for_transit(a: dict[str, Any]) -> str:
    tp = str(a.get('transit_planet', ''))
    np = str(a.get('natal_planet', ''))
    aspect = str(a.get('aspect', ''))
    house = a.get('house')
    state = str(a.get('state', ''))
    event = ''
    if tp == 'Меркурий':
        event = 'важный разговор, оформление документа, поездка, решение по работе или возврат к уже обсуждавшемуся вопросу'
    elif tp == 'Венера':
        event = 'встреча, примирение, усиление симпатии, обсуждение денег или покупка того, что связано с комфортом'
    elif tp == 'Марс':
        event = 'быстрое решение, активное действие, запуск дела, спор или необходимость отстоять границы'
    elif tp == 'Юпитер':
        event = 'расширение возможностей, полезный контакт, обучение, поездка или предложение, увеличивающее выбор'
    elif tp == 'Сатурн':
        event = 'закрепление обязательства, проверка результата, оформление статуса или необходимость принять ограничение'
    elif tp == 'Уран':
        event = 'резкая смена плана, неожиданный контакт или решение освободиться от привычного сценария'
    elif tp == 'Нептун':
        event = 'период сильной интуиции или идеализации; важные решения требуют перепроверки фактов'
    elif tp == 'Плутон':
        event = 'глубокая перестройка, отказ от старого формата или разговор о контроле и ресурсах'
    elif tp == 'Солнце':
        event = 'ситуация, где нужно проявиться, принять решение или взять инициативу'
    elif tp == 'Луна':
        event = 'эмоционально заметный день, семейный или бытовой разговор, быстрая смена настроения'
    if aspect in {'Квадрат', 'Оппозиция'}:
        event += ', причём напряжение может сделать событие более резким'
    elif aspect in {'Тригон', 'Секстиль'}:
        event += ', при этом обстоятельства проще использовать конструктивно'
    if state == 'точный':
        event += '; пик темы приходится на выбранную дату'
    elif state == 'сходящийся':
        event += '; тема набирает силу'
    elif state == 'расходящийся':
        event += '; сейчас идёт развязка или осмысление последствий'
    if house:
        event += f'. Основная сфера - {HOUSE_THEME.get(int(house), "соответствующая сфера карты")}'
    return event


def _timing_for_transit(a: dict[str, Any]) -> str:
    tp = str(a.get('transit_planet', ''))
    state = str(a.get('state', ''))
    if tp == 'Луна': horizon = 'часы - 1 день'
    elif tp in {'Меркурий', 'Венера', 'Марс', 'Солнце'}: horizon = 'дни - несколько недель'
    elif tp in {'Юпитер', 'Сатурн'}: horizon = 'недели - месяцы'
    else: horizon = 'месяцы'
    if state == 'точный':
        return f'Точка максимальной заметности - выбранная дата; общий горизонт влияния ориентировочно {horizon}.'
    if state == 'сходящийся':
        return f'Тема нарастает к выбранной дате; ориентировочный горизонт {horizon}.'
    return f'Основная точка уже проходит; ориентировочный горизонт развязки - {horizon}.'


def build_transit_interpretation(calc: dict[str, Any]) -> str:
    aspects = sorted(list(calc.get('aspects', [])), key=_transit_sort_key)
    date = str(calc.get('transit_date', ''))
    city = str(calc.get('city', ''))
    if not aspects:
        return (
            f'1. Прогноз на {date}\nДля {city} в заданном орбисе на выбранный момент не найдено значимых транзитных аспектов к натальным планетам. Это не означает отсутствия событий: просто расчёт не показывает выраженных основных аспектов, на которых можно уверенно строить отдельный сценарий.\n\n'
            '2. Какие события могут произойти\nКонкретных транзитных сценариев по основным аспектам в расчёте нет.\n\n'
            '3. Что уже формируется\nПо текущему расчёту нет аспекта, который можно отдельно выделить как долгий процесс.\n\n'
            '4. Эмоциональный фон\nЭмоциональный фон на выбранную дату не получает выраженного акцента через основные транзитные аспекты.\n\n'
            '5. Любовь, близость и конфликт\nОтдельного усиления любовной или конфликтной тематики по транзитам не выделяется.\n\n'
            '6. Сроки и возможности\nЛучше опираться на обычный план дня и не приписывать событиям астрологическую неизбежность.\n\n'
            '7. Точки роста\nНаблюдать за фактами, не ускорять решения без необходимости и использовать дату для спокойной проверки приоритетов.\n\n'
            '8. Итог\nНа выбранную дату расчёт не даёт выраженного набора мажорных транзитов. Поэтому наиболее корректно смотреть на реальные обстоятельства дня и не делать сильных выводов из отсутствующих аспектов.'
        )

    top = aspects[:5]
    long_aspects = [a for a in aspects if str(a.get('transit_planet')) in {'Юпитер', 'Сатурн', 'Уран', 'Нептун', 'Плутон'}]
    moon = [a for a in aspects if str(a.get('transit_planet')) == 'Луна']
    love = [a for a in aspects if str(a.get('transit_planet')) in {'Венера', 'Марс'} or str(a.get('natal_planet')) in {'Венера', 'Марс'}]
    hard = [a for a in aspects if a.get('aspect') in {'Квадрат', 'Оппозиция'}]
    helpful = [a for a in aspects if a.get('aspect') in {'Тригон', 'Секстиль'}]

    sections: list[str] = []
    main = ' '.join(_transit_aspect_sentence(a, calc) for a in top[:3])
    sections.append(f'1. Прогноз на {date}\n{main}')

    events = []
    for a in top[:4]:
        events.append(f'• {_event_for_transit(a)} ({_transit_label(a)}.) {_timing_for_transit(a)}')
    sections.append('2. Какие события могут произойти\n' + '\n'.join(events))

    if long_aspects:
        body3 = ' '.join(_transit_aspect_sentence(a, calc) for a in long_aspects[:3])
    else:
        body3 = 'В текущем расчёте нет выраженного акцента внешних планет. Поэтому период читается скорее через краткосрочные и среднесрочные темы.'
    sections.append('3. Что уже формируется\n' + body3)

    if moon:
        body4 = ' '.join(_transit_aspect_sentence(a, calc) for a in moon[:2])
    elif any(str(a.get('transit_planet')) in {'Венера', 'Марс'} for a in aspects):
        body4 = 'Эмоциональный фон может быть заметнее обычного из-за активных быстрых планет, особенно когда они затрагивают Луну, Венеру или Марс.'
    else:
        body4 = 'Эмоциональный фон определяется прежде всего общим набором аспектов, без отдельного яркого акцента Луны на выбранную дату.'
    sections.append('4. Эмоциональный фон\n' + body4)

    if love:
        body5 = ' '.join(_transit_aspect_sentence(a, calc) for a in love[:3])
    else:
        body5 = 'Прямого акцента на Венеру и Марс в основных транзитах нет. Конфликтная тема в большей степени зависит от тех напряжённых аспектов, которые затрагивают Меркурий, Луну или Сатурн.'
    if hard:
        body5 += ' ' + ' '.join(f'Напряжение усиливает {a["transit_planet"]} {a["aspect"]} натальному {a["natal_planet"]}.' for a in hard[:2])
    sections.append('5. Любовь, близость и конфликт\n' + body5)

    if helpful:
        now = 'Для конструктивного использования периода подходят мягкие связи: ' + ', '.join([str(a.get('transit_planet','')) + ' ' + str(a.get('aspect','')) + ' ' + str(a.get('natal_planet','')) for a in helpful[:3]]) + '.'
    else:
        now = 'Возможности лучше искать через самые точные аспекты, а напряжённые сюжеты не форсировать без необходимости.'
    timing = _timing_for_transit(top[0])
    sections.append('6. Сроки и возможности\n' + now + ' ' + timing)

    growth = []
    if hard:
        growth.append('не принимать напряжение за необходимость немедленно действовать')
    if any(str(a.get('transit_planet')) == 'Сатурн' for a in aspects):
        growth.append('фиксировать обязательства и сроки письменно')
    if any(str(a.get('transit_planet')) == 'Меркурий' for a in aspects):
        growth.append('перепроверять формулировки, документы и договорённости')
    if any(bool(a.get('transit_retrograde')) for a in aspects):
        growth.append('возвращаться к незавершённым вопросам до окончательного решения')
    if not growth:
        growth = ['наблюдать за фактами', 'не ускорять то, что развивается естественно', 'использовать сильные стороны дня конструктивно']
    sections.append('7. Точки роста\n' + ' '.join(f'{i+1}) {x}.' for i, x in enumerate(dict.fromkeys(growth))))

    strongest = _transit_label(top[0])
    if hard:
        closing = f'Главный акцент даты - {strongest}. Он задаёт наиболее заметную тему периода, а напряжённые аспекты показывают, где потребуется больше осознанности и терпения. Остальные события лучше оценивать по фактическим обстоятельствам и степени точности каждого аспекта.'
    else:
        closing = f'Главный акцент даты - {strongest}. В расчёте нет выраженного набора жёстких аспектов, поэтому период больше подходит для использования возможностей, чем для ожидания неизбежных событий. Ориентироваться стоит на наиболее точные связи и их реальные проявления.'
    sections.append('8. Итог\n' + closing)
    return '\n\n'.join(sections)
