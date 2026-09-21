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

ОБЯЗАТЕЛЬНО напиши все 9 разделов. Нельзя пропускать раздел, заканчивать его обрывком или многоточием. Каждый раздел должен содержать законченные предложения.

1. Прогноз на [дата]
1–2 коротких предложения о главном сюжете даты.

2. Какие события могут произойти
Дай 3 конкретных сценария, максимум 4. Для каждого: событие → аспект или сочетание аспектов → срок. Выбирай самые заметные сценарии.

3. Что уже формируется
1–2 долгих процесса и один краткий всплеск, если он есть. Покажи, что уже формируется и на каком горизонте.

4. Отношения
Только конкретные возможные проявления в любви и близких отношениях, если они подтверждены расчётом.

5. Работа и деньги
Только конкретные события, решения, возможности и риски, подтверждённые аспектами и домами.

6. Эмоциональный фон
Почему в выбранную дату возможны прилив сил, спад, раздражение, вдохновение, тревожность, чувствительность или желание действовать.

7. Сроки и возможности
Раздели на: что можно запускать сейчас; что решать после проверки; что не стоит форсировать. Для каждого дай горизонт времени.

8. Точки роста
Назови 2–3 качества или урока, особенно важные сейчас, и свяжи их с текущими аспектами.

9. Итог
2–3 законченных предложения о наиболее заметном сценарии и о том, за какими признаками следить дальше.

Полный список аспектов показывается клиенту отдельно в приложении. В сообщении указывай только аспекты, которые действительно объясняют конкретный прогноз.

ОБЪЁМ: целевой 2700–3000 символов, абсолютный максимум 3300. Сохрани все 9 разделов. Если приходится сокращать, сокращай формулировки внутри разделов, но никогда не удаляй раздел и никогда не обрывай предложение.
'''.strip()

import re

SECTION_RE = re.compile(r'(?ms)^(?P<num>[1-9])\.\s*(?P<title>[^\n]+)\n(?P<body>.*?)(?=^\d+\.\s|\Z)')


def _clean_transit_answer(text):
    text=str(text or '').replace('```','')
    text=re.sub(r'(?m)^\s*#{1,6}\s*','',text)
    text=re.sub(r'\*+','',text)
    text=re.sub(r'(?m)^\s*[-•]\s+','',text)
    text=text.replace('…','.')
    text=re.sub(r'\.{4,}','... ',text)
    return text.strip()


def _extract_sections(text):
    result={}
    for m in SECTION_RE.finditer(text):
        result[m.group('num')]=(m.group('title').strip(),m.group('body').strip())
    return result


def _sentence_chunks(text):
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+',str(text).strip()) if x.strip()]


def _compact_body(body,budget):
    body=re.sub(r'\s+',' ',str(body).strip())
    if len(body)<=budget:
        return body
    out=[]; used=0
    for sent in _sentence_chunks(body):
        extra=len(sent)+(1 if out else 0)
        if used+extra<=budget:
            out.append(sent); used+=extra
        else:
            break
    if out:
        return ' '.join(out).strip()
    cut=body.rfind(' ',0,max(1,budget-1))
    if cut<80: cut=min(len(body),budget-1)
    return body[:cut].rstrip(' ,;:-')+'.'


def _fit_transit_answer(text,max_chars=3300):
    text=_clean_transit_answer(text)
    sections=_extract_sections(text)
    if len(sections)!=9 or any(not sections.get(n,('', ''))[1] for n in '123456789'):
        return text
    if len(text)<=max_chars:
        return text
    budgets={'1':240,'2':850,'3':380,'4':300,'5':300,'6':230,'7':300,'8':250,'9':250}
    pieces=[]
    for n in '123456789':
        title,body=sections[n]
        pieces.append(f'{n}. {title if n=="1" else {"2":"Какие события могут произойти","3":"Что уже формируется","4":"Отношения","5":"Работа и деньги","6":"Эмоциональный фон","7":"Сроки и возможности","8":"Точки роста","9":"Итог"}[n]}')
        pieces.append(_compact_body(body,budgets[n]))
    result='\n\n'.join(pieces).strip()
    if len(result)<=max_chars:
        return result
    # Second deterministic pass with balanced budgets, still preserving all 9 headings.
    per=185
    pieces=[]
    for n in '123456789':
        title,body=sections[n]
        canonical=title if n=='1' else {"2":"Какие события могут произойти","3":"Что уже формируется","4":"Отношения","5":"Работа и деньги","6":"Эмоциональный фон","7":"Сроки и возможности","8":"Точки роста","9":"Итог"}[n]
        pieces += [f'{n}. {canonical}', _compact_body(body, per)]
    result='\n\n'.join(pieces).strip()
    if len(result)<=max_chars:
        return result
    # Last safety: remove complete sentences from the longest section bodies first.
    blocks=result.split('\n\n')
    while len('\n\n'.join(blocks))>max_chars:
        body_indexes=list(range(1,len(blocks),2))
        idx=max(body_indexes,key=lambda i:len(blocks[i]))
        sentences=_sentence_chunks(blocks[idx])
        if len(sentences)>1:
            blocks[idx]=' '.join(sentences[:-1])
        else:
            blocks[idx]=_compact_body(blocks[idx],max(100,len(blocks[idx])-20))
    return '\n\n'.join(blocks).strip()


async def _chad_transit_request(message, system_prompt, timeout=180, attempts=2):
    last_exc=None
    for attempt in range(1, attempts+1):
        try:
            timeout_cfg=aiohttp.ClientTimeout(total=timeout,connect=20,sock_connect=20,sock_read=timeout-10)
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                payload={'message':message,'api_key':CHAD_API_KEY,'history':[{'role':'system','content':system_prompt}]}
                async with session.post(CHAD_API_URL,json=payload,headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'}) as response:
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
        'Сразу создай один законченный прогноз из всех 9 разделов. '
        'Соблюдай абсолютный максимум 3300 символов. Не пересчитывай данные.\n\n'+calculation_text
    )
    answer=await _chad_transit_request(user_message,TRANSIT_SYSTEM_PROMPT,timeout=180,attempts=2)
    answer=_clean_transit_answer(answer)
    sections=_extract_sections(answer)
    if len(sections)!=9 or any(not sections.get(n,('', ''))[1] for n in '123456789'):
        repair_prompt='''Верни законченный прогноз по переданному тексту. Сохрани все 9 разделов в точности в формате 1–9, конкретные события, аспекты и сроки. Не используй Markdown. Не ставь многоточия. Каждый раздел должен заканчиваться полноценными предложениями. Максимум 3000 символов.'''.strip()
        repaired=await _chad_transit_request('Исправь только структуру и завершённость этого прогноза, не добавляя новых фактов:\n\n'+answer,repair_prompt,timeout=120,attempts=1)
        answer=_clean_transit_answer(repaired)
    answer=_fit_transit_answer(answer,3300)
    sections=_extract_sections(answer)
    if len(answer)>3300:
        raise RuntimeError(f'Прогноз после сжатия превышает 3300 символов: {len(answer)}')
    if len(sections)!=9 or any(not sections.get(n,('', ''))[1] for n in '123456789'):
        raise RuntimeError('CHAD вернул неполный прогноз: необходимы все 9 разделов')
    return answer

SYNASTRY_SYSTEM_PROMPT = '''
Ты — Лилит, персональный эзотерический консультант. Ты получаешь ГОТОВЫЙ расчёт синастрии двух натальных карт и делаешь персональный разбор их отношений.

Используй ТОЛЬКО переданные расчётные данные. Не пересчитывай планеты, аспекты, орбисы, дома или углы и не добавляй показатели, которых нет в расчёте.

Не делай расплывчатый текст о «совместимости вообще». Переводи показатели в конкретную динамику пары и возможные жизненные проявления: сильное притяжение, ревность, различие потребностей, повторяющиеся конфликты, совместные планы, финансовые споры, желание жить вместе, поддержка карьеры, расставание или возвращение к отношениям, официальный статус, трудности с доверием, сексуальная динамика, бытовые разногласия и другие сценарии — только если они действительно поддержаны расчётом.

Не утверждай неизбежность событий. Используй формулировки «может проявляться», «вероятна динамика», «может приводить», «есть вероятность».

Особое внимание уделяй Солнцу, Луне, Венере, Марсу, Меркурию, Юпитеру и Сатурну. Сильные и точные аспекты описывай подробнее. Длительные планеты показывай как более глубокие процессы. Учитывай дома, если они рассчитаны; не используй дома и углы человека, если время его рождения неизвестно.

Не используй Markdown. Никаких #, *, жирного, курсива, маркеров и многоточий для обрыва текста. Используй обычные заголовки и нумерацию.

ОБЯЗАТЕЛЬНО напиши все 8 разделов. Каждый раздел должен быть законченным.

1. Главная динамика пары
2–3 предложения о том, что прежде всего связывает и одновременно напрягает этих людей.

2. Что притягивает
Конкретно объясни, за счёт каких аспектов возникает эмоциональное, интеллектуальное, романтическое или сексуальное притяжение.

3. Где возникают конфликты
Назови 2–3 наиболее вероятные повторяющиеся проблемы и свяжи каждую с конкретными аспектами.

4. Любовь и близость
Опиши вероятную модель проявления чувств, ревности, доверия, сексуальности и потребности в близости.

5. Быт, деньги и совместная жизнь
Покажи, как пара может взаимодействовать в бытовых вопросах, общих расходах, ответственности, переезде или совместных планах, если это поддержано домами и аспектами.

6. Потенциал отношений
Опиши, что помогает сохранять связь и что может разрушать её. Отдельно укажи признаки серьёзного долгосрочного сценария, если они есть в расчёте.

7. Точки роста
Назови 3 конкретных урока или качества, которые каждому человеку важно развивать в этой связи.

8. Итог
Дай ясный вывод о характере связи и о том, на какие реальные проявления в отношениях стоит смотреть.

Полный список синастрических аспектов показывается клиенту отдельно в приложении. Не трать сообщение на механическое перечисление всех аспектов.

ОБЪЁМ: целевой 2600–3000 символов, абсолютный максимум 3300. Все 8 разделов обязательны. Если нужно сокращать, сокращай формулировки внутри разделов, но не удаляй разделы и не обрывай предложения.
'''.strip()

SYNASTRY_TRANSIT_SYSTEM_PROMPT = '''
Ты — Лилит, персональный эзотерический консультант. Ты получаешь ГОТОВУЮ синастрию двух людей и ГОТОВЫЙ расчёт транзитов на выбранную дату к картам обоих людей. Сделай персональный прогноз именно для отношений этой пары на выбранную дату.

Используй ТОЛЬКО переданные расчётные данные. Не пересчитывай планеты, аспекты, орбисы, дома или углы.

Сначала отдели устойчивую природу связи от временного периода. Затем объясни, какие темы отношений активируются транзитами сейчас.

Будь конкретной. Называй возможные события и реальные проявления: важный разговор, примирение, ссора, предложение, решение съехаться или разъехаться, поездка, оформление отношений, знакомство с семьёй, совместная покупка, финансовый спор, изменение планов, возвращение к незавершённой теме, усиление притяжения, охлаждение, пауза, решение о будущем отношений и другие сценарии — только если они действительно поддержаны расчётом.

Учитывай состояние аспекта: сходящийся — тема набирает силу; точный — пик около выбранной даты; расходящийся — последствия или развязка. Ретроградность — возврат, повторное обсуждение, пересмотр, задержка или возвращение человека/темы. Сроки выражай только как сегодня, ближайшие дни, недели или месяцы.

Не утверждай неизбежность событий. Не используй Markdown: никаких #, *, жирного, курсива, маркеров и многоточий для обрыва текста.

ОБЯЗАТЕЛЬНО все 8 разделов:

1. Прогноз отношений на [дата]
Главный сюжет периода в 2–3 предложениях.

2. Какие события могут произойти
Дай 3–4 конкретных сценария. Для каждого: событие → какие транзиты его поддерживают → срок.

3. Что уже формируется
Покажи 1–2 долгих процесса и их связь с базовой синастрией.

4. Эмоциональный фон пары
Почему отношения могут ощущаться более тёплыми, напряжёнными, нестабильными или притягательными.

5. Любовь, близость и конфликт
Что вероятнее усиливается в чувствах и где возможна точка напряжения.

6. Сроки и возможности
Что можно обсуждать или начинать сейчас; что лучше перепроверить; что не стоит форсировать. Для каждого — горизонт времени.

7. Точки роста
3 качества или урока, которые особенно важны паре сейчас.

8. Итог
2–4 законченных предложения о главном сценарии периода.

Полные списки базовых синастрических аспектов и текущих транзитных аспектов показываются отдельно в приложении. Не перечисляй их механически в сообщении.

ОБЪЁМ: целевой 2600–3000 символов, абсолютный максимум 3300. Все 8 разделов обязательны. Никогда не обрывай раздел или предложение ради объёма.
'''.strip()

RELATION_SECTION_RE = re.compile(r'(?ms)^(?P<num>[1-8])\.\s*(?P<title>[^\n]+)\n(?P<body>.*?)(?=^\d+\.\s|\Z)')


def _clean_relation_answer(text):
    text=str(text or '').replace('```','')
    text=re.sub(r'(?m)^\s*#{1,6}\s*','',text)
    text=re.sub(r'\*+','',text)
    text=re.sub(r'(?m)^\s*[-•]\s+','',text)
    text=text.replace('…','.')
    return text.strip()


def _extract_relation_sections(text):
    return {m.group('num'):(m.group('title').strip(),m.group('body').strip()) for m in RELATION_SECTION_RE.finditer(text)}


def _relation_sentences(text):
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+',str(text).strip()) if x.strip()]


def _fit_relation_answer(text, max_chars=3300):
    text=_clean_relation_answer(text)
    sections=_extract_relation_sections(text)
    if len(sections)!=8 or any(not sections.get(n,('', ''))[1] for n in '12345678'):
        return text
    if len(text)<=max_chars:
        return text
    budgets={'1':330,'2':480,'3':480,'4':430,'5':420,'6':470,'7':350,'8':330}
    out=[]
    canonical={'1':'Главная динамика пары','2':'Что притягивает','3':'Где возникают конфликты','4':'Любовь и близость','5':'Быт, деньги и совместная жизнь','6':'Потенциал отношений','7':'Точки роста','8':'Итог'}
    for n in '12345678':
        body=re.sub(r'\s+',' ',sections[n][1])
        out.append(f'{n}. {canonical[n]}')
        if len(body)<=budgets[n]:
            out.append(body)
        else:
            sents=_relation_sentences(body)
            acc=[]; used=0
            for sent in sents:
                extra=len(sent)+(1 if acc else 0)
                if used+extra<=budgets[n]:
                    acc.append(sent); used+=extra
                else:
                    break
            out.append(' '.join(acc) if acc else body[:max(80,budgets[n]-1)].rsplit(' ',1)[0]+'.')
    result='\n\n'.join(out).strip()
    if len(result)<=max_chars:
        return result
    # Remove whole sentences from the longest body while keeping all 8 sections.
    blocks=result.split('\n\n')
    while len('\n\n'.join(blocks))>max_chars:
        body_indexes=list(range(1,len(blocks),2))
        idx=max(body_indexes,key=lambda i:len(blocks[i]))
        sents=_relation_sentences(blocks[idx])
        if len(sents)>1:
            blocks[idx]=' '.join(sents[:-1]).strip()
        else:
            blocks[idx]=blocks[idx][:max(60,len(blocks[idx])-20)].rsplit(' ',1)[0]+'.'
    return '\n\n'.join(blocks).strip()


async def _chad_relation_request(message, system_prompt, timeout=180, attempts=2):
    last_exc=None
    for attempt in range(1, attempts+1):
        try:
            timeout_cfg=aiohttp.ClientTimeout(total=timeout,connect=20,sock_connect=20,sock_read=timeout-10)
            async with aiohttp.ClientSession(timeout=timeout_cfg) as session:
                payload={'message':message,'api_key':CHAD_API_KEY,'history':[{'role':'system','content':system_prompt}]}
                async with session.post(CHAD_API_URL,json=payload,headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'}) as response:
                    body=await response.text()
                    print(f'[CHAD RELATION] response status={response.status} body_len={len(body)} attempt={attempt}',flush=True)
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
                    if not answer and body.strip(): answer=body.strip()
                    if not str(answer).strip(): raise RuntimeError('CHAD API вернул пустой ответ')
                    return str(answer).strip()
        except (aiohttp.ClientError,asyncio.TimeoutError,TimeoutError) as exc:
            last_exc=exc
            print(f'[CHAD RELATION] network error attempt={attempt}: {type(exc).__name__}: {exc}',flush=True)
            if attempt<attempts:
                await asyncio.sleep(2*attempt)
                continue
            raise
    if last_exc: raise last_exc
    raise RuntimeError('CHAD API: неизвестная ошибка запроса')


async def _ask_relation(calculation_text, prompt, label):
    if not CHAD_API_URL: raise RuntimeError('Не заполнен CHAD_API_URL')
    if not CHAD_API_KEY: raise RuntimeError('Не заполнен CHAD_API_KEY')
    user_message=(
        f'Ниже приведён точный расчёт для задачи «{label}». '
        'Сразу создай один законченный ответ в требуемой структуре. '
        'Сохрани все обязательные разделы и абсолютный максимум 3300 символов.\n\n'+calculation_text
    )
    answer=await _chad_relation_request(user_message,prompt,timeout=180,attempts=2)
    answer=_clean_relation_answer(answer)
    sections=_extract_relation_sections(answer)
    if len(sections)!=8 or any(not sections.get(n,('', ''))[1] for n in '12345678'):
        repair_prompt='''Верни только исправленный, законченный ответ по исходному тексту. Сохрани все 8 нумерованных разделов, конкретные выводы и факты. Никакого Markdown и никаких многоточий. Не добавляй новых астрологических данных. Максимум 3000 символов.'''.strip()
        repaired=await _chad_relation_request('Исправь только структуру и завершённость этого ответа:\n\n'+answer,repair_prompt,timeout=120,attempts=1)
        answer=_clean_relation_answer(repaired)
    answer=_fit_relation_answer(answer,3300)
    if len(answer)>3300:
        raise RuntimeError(f'Ответ после обработки превышает 3300 символов: {len(answer)}')
    sections=_extract_relation_sections(answer)
    if len(sections)!=8 or any(not sections.get(n,('', ''))[1] for n in '12345678'):
        raise RuntimeError('CHAD вернул неполный ответ: необходимы все 8 разделов')
    return answer


async def ask_synastry(calculation_text):
    return await _ask_relation(calculation_text, SYNASTRY_SYSTEM_PROMPT, 'синастрия')


async def ask_synastry_transits(calculation_text):
    return await _ask_relation(calculation_text, SYNASTRY_TRANSIT_SYSTEM_PROMPT, 'транзиты синастрии')
