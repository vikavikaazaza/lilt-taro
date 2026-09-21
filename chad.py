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

Главная задача — переводить астрологические показатели в конкретные жизненные сценарии, а не в расплывчатое описание «энергий». Ищи реальные проявления: разговор или решение на работе, смена обязанностей, собеседование, предложение, увольнение, переезд, поездка, документы, покупка, денежный вопрос, знакомство, сближение, конфликт, расставание, возвращение человека, запуск или завершение проекта, публичное решение и другие события — только если это действительно поддержано сочетанием аспектов, домов, точности и состояния. Не используй список примеров механически.

Сходящийся аспект — тема набирает силу; точный — пик около выбранной даты; расходящийся — тема могла уже проявиться, сейчас идут последствия или переоценка. Ретроградность может указывать на возвращение, пересмотр и задержки. Для сроков используй только: сегодня, ближайшие дни, недели, месяцы. Точную дату будущего события не придумывай.

Если есть дома, используй их для конкретизации сферы жизни. Если время рождения неизвестно, не используй дома и Асцендент и учитывай приблизительность натальной Луны.

Не обещай неизбежное событие. Используй «может произойти», «вероятна ситуация», «может прийти известие», но формулируй максимально конкретно.

Не используй Markdown вообще: никаких #, *, жирного, курсива и маркеров списков. Только обычные заголовки и нумерация.

Структура ответа ОБЯЗАТЕЛЬНО должна содержать ВСЕ 9 разделов и НЕ должна обрываться:
1. Прогноз на [дата]
1–2 коротких предложения о главном сюжете даты.

2. Какие события могут произойти
Дай 3–4 самых конкретных сценария. Каждый: событие → аспект/аспекты → срок. Не расписывай длинно.

3. Что уже формируется
1–2 долгих процесса и, если есть, 1 краткий всплеск. Покажи, что уже начинает складываться и в какой срок.

4. Отношения
Только конкретные проявления в любви и близких отношениях, если они поддержаны расчётом.

5. Работа и деньги
Только конкретные события, решения и риски, подтверждённые картой.

6. Эмоциональный фон
Почему в эту дату возможны прилив сил, спад, раздражение, вдохновение, тревожность или чувствительность.

7. Сроки и возможности
Коротко раздели: что делать сейчас; что делать после проверки; что не форсировать. Для каждого — горизонт времени.

8. Точки роста
2–3 качества или урока, которые особенно важны сейчас.

9. Итог
2–3 конкретных предложения о наиболее заметном сценарии и о том, на что смотреть дальше.

Не перечисляй длинный список аспектов в самом сообщении: полный список аспектов показывается клиенту отдельно в приложении.

Целевой объём — 2700–3000 символов. Абсолютный максимум — 3300 символов. Все 9 разделов обязательны. Каждый раздел должен быть коротким и содержательным. Не повторяй одну мысль в нескольких разделах.
'''.strip()

async def _chad_transit_request(message, system_prompt, timeout):
    timeout_cfg=aiohttp.ClientTimeout(total=timeout, connect=20, sock_connect=20, sock_read=timeout-5)
    async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
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
            print(f'[CHAD TRANSIT] response status={response.status} body_len={len(body)}',flush=True)
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


def _clean_transit_answer(text):
    import re
    text=str(text or '').replace('```','')
    text=re.sub(r'(?m)^\s*#{1,6}\s*','',text)
    text=re.sub(r'\*+', '', text)
    text=re.sub(r'(?m)^\s*[-•]\s+', '', text)
    return text.strip()


async def ask_transit(calculation_text):
    if not CHAD_API_URL:
        raise RuntimeError('Не заполнен CHAD_API_URL')
    if not CHAD_API_KEY:
        raise RuntimeError('Не заполнен CHAD_API_KEY')
    user_message=(
        'Ниже приведён точный расчёт транзитов к натальной карте клиента. '
        'Интерпретируй только эти данные и ничего не пересчитывай.\n\n'
        + calculation_text
    )
    answer=await _chad_transit_request(user_message, TRANSIT_SYSTEM_PROMPT, 300)
    answer=_clean_transit_answer(answer)
    if len(answer) <= 3300:
        return answer

    compact_prompt="""Ты редактируешь уже готовый прогноз транзитов. Сожми его, не меняя астрологический смысл и не добавляя новых фактов. ОБЯЗАТЕЛЬНО сохрани все 9 разделов, каждый заголовок и ключевые конкретные события, аспекты и сроки. Удали повторы, длинные пояснения и второстепенные фразы. Не используй Markdown. Итог должен быть от 2500 до 3200 символов и не должен обрываться.""".strip()
    compact_message='Сожми этот готовый прогноз до лимита, сохранив ВСЕ 9 разделов:\n\n'+answer
    compact=await _chad_transit_request(compact_message, compact_prompt, 300)
    compact=_clean_transit_answer(compact)
    if len(compact) <= 3300:
        return compact

    compact_prompt2="""Сожми этот прогноз ещё раз. Сохрани ВСЕ 9 пронумерованных разделов, конкретные события, аспекты и сроки. Никакого Markdown. Максимум 3200 символов. Не обрывай текст.""".strip()
    compact2=await _chad_transit_request('Сожми прогноз ещё раз:\n\n'+compact, compact_prompt2, 300)
    compact2=_clean_transit_answer(compact2)
    if len(compact2) <= 3300:
        return compact2

    text=compact2[:3300]
    cut=text.rfind('\n\n')
    if cut < 2500:
        cut=text.rfind('\n')
    if cut < 2500:
        cut=text.rfind(' ')
    if cut > 0:
        text=text[:cut].rstrip()+'.'
    else:
        text=text[:3299].rstrip()+'.'
    return text

