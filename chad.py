import asyncio
import re
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

Главное правило: не пересчитывай самостоятельно положения планет, аспекты, орбисы, знаки, дома или Асцендент. Используй только переданные расчётные данные. Не добавляй показатели, которых нет в расчёте.

Главная задача — переводить астрологические показатели в конкретные жизненные сценарии, а не в расплывчатое описание «энергий». Ищи реальные проявления: разговор или решение на работе, смена обязанностей, собеседование, предложение, увольнение, переезд, поездка, документы, покупка, денежный вопрос, знакомство, сближение, конфликт, расставание, возвращение человека, запуск или завершение проекта, официальное решение и другие события — только если это поддержано сочетанием аспектов, домов, точности и состояния. Не используй список примеров механически.

Сходящийся аспект — тема набирает силу; точный — пик около выбранной даты; расходящийся — тема уже могла проявиться, сейчас идут последствия или переоценка. Ретроградность может указывать на возврат, пересмотр, задержку или повторное прохождение темы. Для сроков используй только: сегодня, ближайшие дни, недели, месяцы. Не придумывай точную дату будущего события.

Если есть дома, используй их для конкретизации жизненной сферы. Если время рождения неизвестно, не используй дома и Асцендент и учитывай приблизительность натальной Луны.

Не обещай неизбежное событие. Используй «может произойти», «вероятна ситуация», «может прийти известие», но будь максимально конкретной.

Не используй Markdown вообще: никаких #, *, жирного, курсива и маркеров списков. Только обычные заголовки и нумерация.

ОБЯЗАТЕЛЬНО используй ровно эти 9 разделов, в этом порядке. Нельзя пропускать разделы, объединять их или завершать ответ раньше раздела 9:

1. Прогноз на [дата]
1–2 коротких предложения о главном сюжете даты.

2. Какие события могут произойти
Дай 3–4 конкретных сценария. Формат каждого: событие → поддерживающий аспект или сочетание аспектов → срок. Не расписывай длинные объяснения.

3. Что уже формируется
1–2 долгих процесса и при наличии 1 краткий всплеск. Покажи, что уже начинает складываться и в какой срок.

4. Отношения
Только конкретные проявления в любви и близких отношениях, если они поддержаны расчётом.

5. Работа и деньги
Только конкретные события, решения и риски, подтверждённые картой.

6. Эмоциональный фон
Почему в эту дату возможны прилив сил, спад, раздражение, вдохновение, тревожность или чувствительность.

7. Сроки и возможности
Коротко раздели: что делать сейчас; что решать после проверки; что не форсировать. Для каждого укажи горизонт: сегодня, дни, недели или месяцы.

8. Точки роста
2–3 качества или урока, которые особенно важны сейчас.

9. Итог
2–3 конкретных предложения о наиболее заметном сценарии и о том, на что смотреть дальше.

Полный список аспектов уже показывается клиенту отдельным блоком в приложении. Не трать место на их длинное повторение в прогнозе.

ОБЪЁМ: стремись к 2700–3000 символам. Абсолютный максимум — 3200 символов. Ответ ОБЯЗАТЕЛЬНО должен закончиться разделом 9 и не должен обрываться.
'''.strip()

TRANSIT_SECTION_HEADERS = (
    '1. Прогноз на',
    '2. Какие события могут произойти',
    '3. Что уже формируется',
    '4. Отношения',
    '5. Работа и деньги',
    '6. Эмоциональный фон',
    '7. Сроки и возможности',
    '8. Точки роста',
    '9. Итог',
)


def _clean_transit_answer(text):
    text=str(text or '').replace('```','')
    text=re.sub(r'(?m)^\s*#{1,6}\s*','',text)
    text=re.sub(r'\*+', '', text)
    text=re.sub(r'(?m)^\s*[-•]\s+', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _has_all_transit_sections(text):
    t=_clean_transit_answer(text)
    return all(re.search(rf'(?m)^\s*{re.escape(h)}(?:.*)?$', t) for h in TRANSIT_SECTION_HEADERS)


def _natural_trim(text, limit):
    text=str(text or '').strip()
    if len(text)<=limit:
        return text
    cut=text.rfind('\n\n', 0, limit)
    if cut < int(limit*0.55):
        cut=text.rfind('. ', 0, limit)
        if cut>0:
            cut+=1
    if cut < int(limit*0.55):
        cut=text.rfind(' ', 0, limit)
    if cut<1:
        cut=limit
    return text[:cut].rstrip(' .,:;—-')+'…'


def _hard_cap_transit_answer(text, max_chars=3300):
    t=_clean_transit_answer(text)
    if len(t)<=max_chars and _has_all_transit_sections(t):
        return t
    matches=list(re.finditer(r'(?m)^\s*(\d)\.\s+', t))
    by_num={}
    for i,m in enumerate(matches):
        start=m.start()
        end=matches[i+1].start() if i+1<len(matches) else len(t)
        n=int(m.group(1))
        if 1<=n<=9:
            by_num[n]=t[start:end].strip()
    budgets={1:280,2:760,3:400,4:320,5:320,6:260,7:300,8:240,9:250}
    pieces=[]
    for n in range(1,10):
        block=by_num.get(n)
        if not block:
            raise ValueError(f'Не найден раздел прогноза {n}')
        pieces.append(_natural_trim(block,budgets[n]))
    result='\n\n'.join(pieces).strip()
    if len(result)>max_chars:
        for n in (9,8,7,6,5,4,3,1,2):
            if len(result)<=max_chars:
                break
            extra=len(result)-max_chars
            old=pieces[n-1]
            pieces[n-1]=_natural_trim(old,max(120,len(old)-extra))
            result='\n\n'.join(pieces).strip()
    if len(result)>max_chars or not _has_all_transit_sections(result):
        raise ValueError('Не удалось безопасно уложить прогноз в 3300 символов с сохранением 9 разделов')
    return result


async def _chad_transit_request(message, system_prompt, timeout=180, attempts=2):
    timeout_cfg=aiohttp.ClientTimeout(total=timeout, connect=20, sock_connect=20, sock_read=max(30, timeout-10))
    last_error=None
    async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
        for attempt in range(1, attempts+1):
            try:
                payload={
                    'message':message,
                    'api_key':CHAD_API_KEY,
                    'history':[{'role':'system','content':system_prompt}],
                }
                async with session.post(
                    CHAD_API_URL,
                    json=payload,
                    headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'},
                ) as response:
                    body=await response.text()
                    print(f'[CHAD TRANSIT] response status={response.status} body_len={len(body)} attempt={attempt}',flush=True)
                    if response.status in (429,502,503,504):
                        last_error=RuntimeError(f'CHAD API HTTP {response.status}: {body[:1000]}')
                        if attempt<attempts:
                            delay=8 if response.status==429 else 3
                            print(f'[CHAD TRANSIT] retrying after HTTP {response.status} in {delay}s',flush=True)
                            await asyncio.sleep(delay)
                            continue
                        raise last_error
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
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error=exc
                print(f'[CHAD TRANSIT] transport error attempt={attempt}: {type(exc).__name__}: {exc}',flush=True)
                if attempt<attempts:
                    await asyncio.sleep(3)
                    continue
                raise
    if last_error:
        raise last_error
    raise RuntimeError('Не удалось получить ответ CHAD')


async def ask_transit(calculation_text):
    if not CHAD_API_URL:
        raise RuntimeError('Не заполнен CHAD_API_URL')
    if not CHAD_API_KEY:
        raise RuntimeError('Не заполнен CHAD_API_KEY')
    user_message=(
        'Ниже приведён точный расчёт транзитов к натальной карте клиента. '
        'Интерпретируй только эти данные и ничего не пересчитывай. '
        'Сформируй прогноз строго по всем 9 разделам системного промпта.\n\n'+calculation_text
    )
    answer=await _chad_transit_request(user_message, TRANSIT_SYSTEM_PROMPT, timeout=180, attempts=2)
    answer=_clean_transit_answer(answer)
    if len(answer)<=3300 and _has_all_transit_sections(answer):
        return answer

    compact_prompt='''Ты — редактор уже готового астрологического прогноза. Не меняй его смысл и не добавляй новых астрологических фактов. Сохрани РОВНО все 9 пронумерованных разделов в исходном порядке. Сохрани ключевые конкретные события, поддерживающие аспекты и сроки. Удали повторы и второстепенные пояснения. Никакого Markdown. Итог — 2700–3150 символов, максимум 3200. Ответ обязательно должен закончиться разделом 9 и не обрываться.'''.strip()
    compact=await _chad_transit_request(
        'Сожми этот готовый прогноз до безопасного объёма, сохранив все 9 разделов:\n\n'+answer,
        compact_prompt,
        timeout=180,
        attempts=2,
    )
    compact=_clean_transit_answer(compact)
    if len(compact)<=3300 and _has_all_transit_sections(compact):
        return compact
    return _hard_cap_transit_answer(compact,3300)
