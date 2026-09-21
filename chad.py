import asyncio
import aiohttp
import config

MANARA_NAMES=[
'Дурак','Маг','Верховная Жрица','Императрица','Император','Верховный Жрец','Возлюбленные','Колесница','Справедливость','Отшельник','Зеркало','Сила','Наказание','Смерть','Умеренность','Дьявол','Башня','Звезда','Луна','Солнце','Суд','Мир',
'Туз Огня','Двойка Огня','Тройка Огня','Четверка Огня','Пятерка Огня','Шестерка Огня','Семерка Огня','Восьмерка Огня','Девятка Огня','Десятка Огня','Слуга Огня','Всадница Огня','Королева Огня','Король Огня',
'Туз Воздуха','Двойка Воздуха','Тройка Воздуха','Четверка Воздуха','Пятерка Воздуха','Шестерка Воздуха','Семерка Воздуха','Восьмерка Воздуха','Девятка Воздуха','Десятка Воздуха','Слуга Воздуха','Всадница Воздуха','Королева Воздуха','Король Воздуха',
'Туз Земли','Двойка Земли','Тройка Земли','Четверка Земли','Пятерка Земли','Шестерка Земли','Семерка Земли','Восьмерка Земли','Девятка Земли','Десятка Земли','Слуга Земли','Всадница Земли','Королева Земли','Король Земли',
'Туз Воды','Двойка Воды','Тройка Воды','Четверка Воды','Пятерка Воды','Шестерка Воды','Семерка Воды','Восьмерка Воды','Девятка Воды','Десятка Воды','Слуга Воды','Всадница Воды','Королева Воды','Король Воды']

WAITE_NAMES=[
'Шут','Маг','Верховная Жрица','Императрица','Император','Иерофант','Влюблённые','Колесница','Сила','Отшельник','Колесо Фортуны','Справедливость','Повешенный','Смерть','Умеренность','Дьявол','Башня','Звезда','Луна','Солнце','Суд','Мир',
'Туз Жезлов','Двойка Жезлов','Тройка Жезлов','Четвёрка Жезлов','Пятёрка Жезлов','Шестёрка Жезлов','Семёрка Жезлов','Восьмёрка Жезлов','Девятка Жезлов','Десятка Жезлов','Паж Жезлов','Рыцарь Жезлов','Королева Жезлов','Король Жезлов',
'Туз Кубков','Двойка Кубков','Тройка Кубков','Четвёрка Кубков','Пятёрка Кубков','Шестёрка Кубков','Семёрка Кубков','Восьмёрка Кубков','Девятка Кубков','Десятка Кубков','Паж Кубков','Рыцарь Кубков','Королева Кубков','Король Кубков',
'Туз Мечей','Двойка Мечей','Тройка Мечей','Четвёрка Мечей','Пятёрка Мечей','Шестёрка Мечей','Семёрка Мечей','Восьмёрка Мечей','Девятка Мечей','Десятка Мечей','Паж Мечей','Рыцарь Мечей','Королева Мечей','Король Мечей',
'Туз Пентаклей','Двойка Пентаклей','Тройка Пентаклей','Четвёрка Пентаклей','Пятёрка Пентаклей','Шестёрка Пентаклей','Семёрка Пентаклей','Восьмёрка Пентаклей','Девятка Пентаклей','Десятка Пентаклей','Паж Пентаклей','Рыцарь Пентаклей','Королева Пентаклей','Король Пентаклей']

CHAD_API_URL=getattr(config, 'CHAD_API_URL', '').strip()
CHAD_API_KEY=getattr(config, 'CHAD_API_KEY', '').strip()
PROMPTS=getattr(config, 'PROMPTS', None)
if PROMPTS is None:
    PROMPTS=getattr(config, 'prompts', {})
if not isinstance(PROMPTS, dict):
    PROMPTS={}


def _card_lines(cards):
    lines=[]
    for pos, card in enumerate(cards, 1):
        if isinstance(card, dict):
            cid=card.get('id')
            name=str(card.get('name',''))
            if cid is not None:
                lines.append(f'{pos}. ID={cid} — {name}')
            else:
                lines.append(f'{pos}. {name}')
        else:
            lines.append(f'{pos}. {str(card)}')
    return lines

def _expected_header(cards):
    names=', '.join(x.get('name','') if isinstance(x,dict) else str(x) for x in cards)
    return f'Ваши карты: {names}'


def _answer_matches_cards(answer, cards, deck):
    """Require the exact card header and reject mentions of another full card name."""
    if not answer or not cards:
        return False
    expected=_expected_header(cards).strip().replace('\r\n','\n')
    first=answer.strip().split('\n', 1)[0].strip()
    if first != expected:
        return False
    expected_names={str(x.get('name','')) if isinstance(x,dict) else str(x) for x in cards}
    known=MANARA_NAMES if deck=='manara' else WAITE_NAMES
    for card_name in known:
        if card_name in expected_names:
            continue
        if card_name and card_name in answer:
            return False
    return True


async def ask(deck, q, cards, paid=False, day=False):
    key='day_free' if day else f'{deck}_{"paid" if paid else "free"}'
    names=', '.join(x.get('name','') if isinstance(x,dict) else str(x) for x in cards)
    if not CHAD_API_URL:
        raise RuntimeError('Не заполнен CHAD_API_URL')
    if not CHAD_API_KEY:
        raise RuntimeError('Не заполнен CHAD_API_KEY')

    # Передаём карты в ОСНОВНОМ сообщении пользователя, а не только в history.
    # Так список карт является частью текущего запроса и не может трактоваться
    # как старый ответ ассистента. Это особенно важно для Манары и Карты дня.
    card_rule=(
        'ВНИМАНИЕ. КАРТЫ УЖЕ ВЫБРАНЫ СЕРВЕРОМ И ЯВЛЯЮТСЯ ФИКСИРОВАННЫМИ ДАННЫМИ РАСКЛАДА. '
        'НЕЛЬЗЯ ВЫБИРАТЬ, ВЫТЯГИВАТЬ, ЗАМЕНЯТЬ, ПЕРЕИМЕНОВЫВАТЬ ИЛИ ПОДМЕНЯТЬ КАРТЫ. '
        f'КАНОНИЧЕСКИЕ КАРТЫ РАСКЛАДА: {"; ".join(_card_lines(cards))}. '
        f'Используй ТОЛЬКО эти карты и только в этом порядке: {names}. '
        'Для каждой карты трактуй именно указанное название и ID, а не другую карту с похожим значением. '
        'Не ориентируйся на любые другие названия карт, которые можешь вспомнить самостоятельно. '
        f'Первая строка твоего ответа ДОЛЖНА быть строго: «{_expected_header(cards)}». '
    )
    user_message=(
        f'{card_rule}\n\n'
        f'Вопрос клиента:\n{q.strip()}\n\n'
        'Ответь строго в соответствии с системным промптом, но не выбирай карты самостоятельно.'
    )

    print(f'[CHAD] request deck={deck} key={key} cards={names!r}', flush=True)
    timeout=aiohttp.ClientTimeout(total=125, connect=20, sock_connect=20, sock_read=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, 3):
            payload={
                'message': user_message if attempt == 1 else (
                    user_message + '\n\nКРИТИЧЕСКАЯ ПРОВЕРКА: в прошлой попытке карты были указаны неверно. '
                    'Сейчас перед ответом сверь первую строку посимвольно с обязательной строкой выше и трактуй только фиксированные карты.'
                ),
                'api_key': CHAD_API_KEY,
                'history': [
                    {'role':'system','content':PROMPTS.get(key,'')},
                ],
            }

            async with session.post(
                CHAD_API_URL,
                json=payload,
                headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'},
            ) as response:
                text=await response.text()
                print(f'[CHAD] response status={response.status} body_len={len(text)} attempt={attempt}', flush=True)
                if response.status>=400:
                    raise RuntimeError(f'CHAD API HTTP {response.status}: {text[:1000]}')
                try:
                    data=await response.json(content_type=None)
                except Exception:
                    data={}
                if isinstance(data,dict):
                    answer=data.get('message') or data.get('answer') or data.get('response') or data.get('text')
                    if answer:
                        answer=str(answer).strip()
                    else:
                        answer=''
                else:
                    answer=''
                if not answer and text.strip():
                    answer=text.strip()
                if not answer:
                    raise RuntimeError('CHAD API вернул пустой ответ')

                if _answer_matches_cards(answer, cards, deck):
                    return answer

                print(
                    f'[CHAD] card mismatch attempt={attempt}: expected={_expected_header(cards)!r} '
                    f'got={answer.split(chr(10),1)[0].strip()!r}',
                    flush=True,
                )

    raise RuntimeError('CHAD API вернул трактовку с другими картами. Запрос безопасно отменён.')


TRANSIT_SYSTEM_PROMPT = '''
Ты — Лилит, персональный эзотерический консультант. Ты получаешь ГОТОВЫЙ астрологический расчёт транзитов к натальной карте клиента и делаешь персональный прогноз на выбранную дату.

Используй ТОЛЬКО переданные расчётные данные. Не пересчитывай положения планет, аспекты, орбисы, знаки, дома или Асцендент и не добавляй показатели, которых нет в расчёте.

Переводи расчёт в конкретные возможные жизненные сценарии. Не ограничивайся описанием «энергий». Когда показатели действительно поддерживают сценарий, называй конкретное проявление: разговор с руководителем, изменение обязанностей, собеседование, новая работа, завершение работы, увольнение, переезд, поездка, документы, покупка или продажа, денежный вопрос, знакомство, предложение, сближение, конфликт, расставание, возвращение человека, запуск или завершение проекта, официальное решение, смена планов и другие события. Не выбирай событие только потому, что оно есть в примерах.

Учитывай фазу аспекта: сходящийся — тема набирает силу; точный — пик около выбранной даты; расходящийся — тема уже могла проявиться, сейчас идут последствия или переоценка. Ретроградность учитывай как возврат, пересмотр, повторное рассмотрение или задержку. Сроки выражай только как сегодня, ближайшие дни, недели или месяцы. Точную будущую дату не придумывай.

Если есть дома, используй их для конкретизации сферы жизни. Если время рождения неизвестно, не используй дома и Асцендент и учитывай приблизительность натальной Луны.

Не утверждай неизбежность событий. Формулируй как возможные сценарии, но максимально конкретно.

Не используй Markdown. Никаких #, *, жирного, курсива, маркеров или многоточий для обозначения пропущенного текста. Используй обычные заголовки и нумерацию.

ОБЯЗАТЕЛЬНО напиши ВСЕ 9 разделов в указанном порядке. Каждый раздел должен иметь содержательный текст и заканчиваться полноценным предложением. Не используй «…» и «...». Нельзя заканчивать раздел оборванной фразой.

1. Прогноз на [дата]
1–2 коротких законченных предложения о главном сюжете даты.

2. Какие события могут произойти
Дай 3 конкретных сценария, максимум 4. Для каждого: сначала реальное возможное событие, затем кратко какой аспект или сочетание аспектов его поддерживает и какой срок наиболее вероятен.

3. Что уже формируется
Покажи 1–2 долгих процесса и один краткий всплеск, если он есть. Обязательно укажи, что уже формируется и на каком горизонте.

4. Отношения
Опиши только конкретные возможные проявления в любви и близких отношениях, если они подтверждены расчётом.

5. Работа и деньги
Опиши только конкретные события, решения, возможности и риски, подтверждённые аспектами и домами.

6. Эмоциональный фон
Объясни, почему в выбранную дату возможны прилив сил, спад, раздражение, вдохновение, тревожность, чувствительность или желание действовать.

7. Сроки и возможности
Обязательно раздели на три части: что можно запускать сейчас; что решать после перепроверки; что не стоит форсировать. Для каждого укажи горизонт времени.

8. Точки роста
Назови 2–3 качества или урока, особенно важные сейчас, и свяжи их с текущими аспектами.

9. Итог
Дай 2–3 законченных предложения о наиболее заметном сценарии и о том, за какими признаками следить дальше.

Полный список аспектов показывается клиенту отдельно в приложении. В сообщении указывай только аспекты, которые действительно объясняют конкретный прогноз.

ОБЪЁМ: стремись к 2800–3100 символам. АБСОЛЮТНЫЙ МАКСИМУМ — 3300 символов. Все 9 разделов обязательны. Если места мало, сокращай формулировки внутри разделов, но НЕ удаляй разделы и НЕ обрывай предложения. Не ставь многоточия. Ответ должен заканчиваться полноценным предложением.
'''.strip()

import re

EXPECTED_HEADINGS={
    '1':'прогноз на',
    '2':'какие события могут произойти',
    '3':'что уже формируется',
    '4':'отношения',
    '5':'работа и деньги',
    '6':'эмоциональный фон',
    '7':'сроки и возможности',
    '8':'точки роста',
    '9':'итог',
}
HEADING_RE=re.compile(r'(?m)^(?P<num>[1-9])\.\s*(?P<title>[^\n]+?)\s*$')


def _clean_transit_answer(text):
    text=str(text or '').replace('```','')
    text=re.sub(r'(?m)^\s*#{1,6}\s*','',text)
    text=re.sub(r'\*+','',text)
    text=re.sub(r'(?m)^\s*[-•]\s+','',text)
    text=text.replace('…','')
    text=re.sub(r'\.{3,}','.',text)
    return text.strip()


def _extract_sections(text):
    cleaned=str(text or '').strip()
    found=[]
    for m in HEADING_RE.finditer(cleaned):
        num=m.group('num')
        title=m.group('title').strip().lower()
        expected=EXPECTED_HEADINGS[num]
        if not title.startswith(expected):
            continue
        found.append((num,m.start(),m.end(),m.group('title').strip()))
    if len(found)!=9 or [x[0] for x in found]!=list('123456789'):
        return {}
    result={}
    for i,(num,start,end,title) in enumerate(found):
        body_start=end
        body_end=found[i+1][1] if i<8 else len(cleaned)
        result[num]=(title,cleaned[body_start:body_end].strip())
    return result


def _section_body_complete(body):
    body=str(body or '').strip()
    if not body or '…' in body or '...' in body:
        return False
    tail=body
    while tail and tail[-1] in '»”"\'’)]}':
        tail=tail[:-1].rstrip()
    return bool(tail) and tail[-1] in '.!?'


def _transit_answer_valid(text, max_chars=3300):
    cleaned=_clean_transit_answer(text)
    if not cleaned or len(cleaned)>max_chars:
        return False
    sections=_extract_sections(cleaned)
    if set(sections)!=set('123456789'):
        return False
    if any(not _section_body_complete(sections[n][1]) for n in '123456789'):
        return False
    return True


async def _chad_transit_request(message, system_prompt, timeout=180, attempts=2):
    last_exc=None
    for attempt in range(1, attempts+1):
        try:
            timeout_cfg=aiohttp.ClientTimeout(total=timeout,connect=20,sock_connect=20,sock_read=timeout-10)
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                payload={'message':message,'api_key':CHAD_API_KEY,'history':[{'role':'system','content':system_prompt}]}
                async with session.post(
                    CHAD_API_URL,
                    json=payload,
                    headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'},
                ) as response:
                    body=await response.text()
                    print(f'[CHAD TRANSIT] response status={response.status} body_len={len(body)} attempt={attempt}',flush=True)
                    if response.status in {502,503,504} and attempt<attempts:
                        await asyncio.sleep(2*attempt)
                        continue
                    if response.status>=400:
                        raise RuntimeError(f'CHAD API HTTP {response.status}: {body[:1000]}')
                    try:
                        data=await response.json(content_type=None)
                    except Exception:
                        data={}
                    answer=''
                    if isinstance(data,dict):
                        answer=data.get('message') or data.get('answer') or data.get('response') or data.get('text') or ''
                    if not answer and body.strip():
                        answer=body.strip()
                    if not str(answer).strip():
                        raise RuntimeError('CHAD API вернул пустую интерпретацию транзитов')
                    return str(answer).strip()
        except (aiohttp.ClientError,asyncio.TimeoutError,TimeoutError) as exc:
            last_exc=exc
            print(f'[CHAD TRANSIT] network error attempt={attempt}: {type(exc).__name__}: {exc}',flush=True)
            if attempt<attempts:
                await asyncio.sleep(2*attempt)
                continue
            raise
    if last_exc: raise last_exc
    raise RuntimeError('CHAD API: неизвестная ошибка запроса')


async def ask_transit(calculation_text):
    if not CHAD_API_URL: raise RuntimeError('Не заполнен CHAD_API_URL')
    if not CHAD_API_KEY: raise RuntimeError('Не заполнен CHAD_API_KEY')
    user_message=(
        'Ниже приведён точный расчёт транзитов к натальной карте клиента. '
        'Сразу создай один законченный прогноз со всеми 9 разделами. '
        'Сначала проверь, что каждый раздел закончен и общий текст не превышает 3300 символов. '
        'Не пересчитывай данные, не используй Markdown, не ставь многоточия и не обрывай предложения.\n\n'+calculation_text
    )
    answer=_clean_transit_answer(await _chad_transit_request(user_message,TRANSIT_SYSTEM_PROMPT,timeout=180,attempts=2))
    if _transit_answer_valid(answer,3300):
        return answer

    repair_prompt='''
Перепиши предыдущий прогноз ПОЛНОСТЬЮ, сохранив исходные астрологические факты. Это не сокращение кусками: создай цельный новый текст.

Обязательные разделы строго в таком порядке:
1. Прогноз на [дата]
2. Какие события могут произойти
3. Что уже формируется
4. Отношения
5. Работа и деньги
6. Эмоциональный фон
7. Сроки и возможности
8. Точки роста
9. Итог

В разделе 2 дай 3 конкретных события (максимум 4), и у каждого укажи поддерживающий аспект и срок. В разделах 3–9 дай законченный, содержательный текст.

НЕ используй Markdown, #, *, многоточия или обрывки фраз. Каждый раздел и весь ответ должны заканчиваться полноценными предложениями.
Объём 2800–3100 символов, абсолютный максимум 3300. Ничего не удаляй из структуры ради длины: сокращай формулировки внутри разделов.
'''.strip()
    repaired=_clean_transit_answer(await _chad_transit_request(
        'Перепиши прогноз целиком по правилам редактора ниже. Не добавляй новых астрологических фактов.\n\n'+answer,
        repair_prompt,
        timeout=180,
        attempts=2,
    ))
    if not _transit_answer_valid(repaired,3300):
        sections=_extract_sections(repaired)
        raise RuntimeError(
            f'CHAD вернул неполный прогноз: длина={len(repaired)}, '
            f'разделы={sorted(sections)}, завершённость=' +
            str(all(_section_body_complete(sections.get(n,('', ''))[1]) for n in '123456789'))
        )
    return repaired
