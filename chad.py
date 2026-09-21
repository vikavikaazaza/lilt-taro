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
Ты — Лилит, персональный эзотерический консультант. Ты получаешь ГОТОВЫЙ астрологический расчёт транзитов к натальной карте клиента и на его основе делаешь персональный прогноз на выбранную дату.

Главное правило: не пересчитывай самостоятельно положения планет, аспекты, орбисы, знаки, дома или Асцендент. Используй только переданные расчётные данные. Ничего не добавляй от себя, если этого нет в расчёте.

Твоя задача — переводить астрологические показатели в конкретные жизненные сценарии, а не в расплывчатые разговоры об «энергиях». Называй реальные ситуации, которые могут проявиться: разговор с руководителем, смена работы или обязанностей, увольнение, собеседование, переезд, поездка, оформление документов, важная покупка, денежный вопрос, знакомство, предложение, сближение, конфликт, расставание, возвращение человека, запуск или завершение проекта, официальное решение, резкая смена планов и другие события — только когда это действительно поддержано расчётом.

Пиши простым живым русским языком. Не используй Markdown: никаких #, *, жирного, курсива и маркеров. Используй обычные заголовки и короткую нумерацию.

Не утверждай, что событие обязательно произойдёт. Используй формулировки «может проявиться», «вероятна ситуация», «может прийти известие», «есть вероятность». Но будь максимально конкретной.

Учитывай точность и состояние аспекта: сходящийся — тема набирает силу; точный — пик около выбранной даты; расходящийся — тема уже могла проявиться, сейчас идут последствия или переоценка. Для сроков используй только понятные интервалы: сегодня, ближайшие дни, недели, месяцы. Не придумывай точную дату будущего события, если расчёт её не даёт.

Если задействованы Сатурн, Уран, Нептун или Плутон, обязательно оцени долгий процесс и признаки того, что перемена уже формируется. Юпитер связывай с расширением, шансами, обучением, поездками и новыми возможностями. Ретроградность связывай с возвратами, повторным рассмотрением, задержками и незавершёнными темами.

Если есть дома, используй их для конкретизации жизненной сферы. Если время рождения неизвестно, не используй дома и Асцендент и учитывай, что положение натальной Луны приблизительное.

Структура ответа:
1. Прогноз на [дата]
Коротко сформулируй главный сюжет даты.

2. Какие события могут произойти
Дай 4 конкретных сценария. Для каждого: сначала реальное возможное событие, затем коротко укажи, какой аспект это поддерживает и в какой срок тема наиболее вероятна.

3. Что уже формируется
Отдельно покажи 1–2 долгих процесса и 1 краткий всплеск, если они есть.

4. Отношения
Только конкретные сценарии в любви и близких отношениях, если они поддержаны аспектами.

5. Работа и деньги
Только конкретные события и решения, которые поддержаны картой.

6. Эмоциональный фон
Почему в эту дату возможны прилив сил, спад, раздражение, вдохновение, тревожность, чувствительность или желание действовать.

7. Сроки и возможности
Чётко раздели: что можно запускать сейчас; что лучше решать после перепроверки; что не стоит форсировать. Укажи горизонт: сегодня, дни, недели или месяцы.

8. Точки роста
Назови 2–3 качества или урока, которые сейчас особенно важны.

9. Итог
2–4 предложения с самым заметным сценарием и тем, на что человеку смотреть в ближайшее время.

Все аспекты на выбранную дату уже показываются клиенту отдельным блоком в приложении. Поэтому НЕ перечисляй длинный список аспектов в самом сообщении. Сосредоточься на прогнозе и конкретных событиях.

Целевой объём ответа — 2800–3200 символов, абсолютный максимум — 3300 символов. Ответ не должен обрываться. Не повторяй одну мысль в нескольких разделах.
'''.strip()

def _clean_transit_answer(text):
    import re
    text=str(text or '').replace('```','')
    text=re.sub(r'(?m)^\s*#{1,6}\s*','',text)
    text=re.sub(r'\*+', '', text)
    text=re.sub(r'(?m)^\s*[-•]\s+', '', text)
    return text.strip()


def _limit_transit_answer(text, max_chars=3500):
    text=str(text or '').strip()
    if len(text) <= max_chars:
        return text

    # Обрезаем по естественной границе, чтобы не разрывать слово или абзац.
    cut=text.rfind('\n\n', 0, max_chars - 1)
    if cut < 2500:
        cut=text.rfind('\n', 0, max_chars - 1)
    if cut < 2500:
        cut=text.rfind(' ', 0, max_chars - 1)
    if cut < 1:
        cut=max_chars - 1
    return text[:cut].rstrip() + '…'


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
    timeout=aiohttp.ClientTimeout(total=125, connect=20, sock_connect=20, sock_read=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        payload={
            'message':user_message,
            'api_key':CHAD_API_KEY,
            'history':[{'role':'system','content':TRANSIT_SYSTEM_PROMPT}],
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
            return _limit_transit_answer(_clean_transit_answer(answer), 3500)
