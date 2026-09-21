import asyncio
import aiohttp
import config
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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



CHAD_WORDS_URL = 'https://ask.chadgpt.ru/api/public/words'
USAGE_LOG_DIR = Path(__file__).resolve().parent / 'logs'
USAGE_LOG_FILE = USAGE_LOG_DIR / 'chad_usage.log'


def _usage_log(line):
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    full=f'{stamp} {line}'
    print(full, flush=True)
    try:
        USAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG_FILE.open('a', encoding='utf-8') as f:
            f.write(full + '\n')
    except Exception as exc:
        print(f'[CHAD USAGE] file log error: {type(exc).__name__}: {exc}', flush=True)


async def _chad_words_balance(session):
    """Read current CHAD word/spark balance for fallback usage accounting."""
    try:
        async with session.post(
            CHAD_WORDS_URL,
            json={'api_key': CHAD_API_KEY},
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {CHAD_API_KEY}'},
        ) as response:
            body=await response.text()
            if response.status >= 400:
                _usage_log(f'[CHAD USAGE] balance status={response.status}')
                return None
            try:
                data=await response.json(content_type=None)
            except Exception:
                data={}
            if not isinstance(data, dict) or not data.get('is_success', True):
                return None
            return {
                'used_words': data.get('used_words'),
                'total_words': data.get('total_words'),
                'remaining_words': data.get('remaining_words'),
                'reserved_words': data.get('reserved_words'),
            }
    except Exception as exc:
        _usage_log(f'[CHAD USAGE] balance error={type(exc).__name__}: {exc}')
        return None


def _response_usage(data):
    if not isinstance(data, dict):
        return None, None, None
    used_words = data.get('used_words_count')
    if used_words is None:
        used_words = data.get('used_sparks_count')
    used_tokens = data.get('used_tokens_count')
    remaining = data.get('remaining_words')
    return used_words, used_tokens, remaining


def _usage_from_balance(before, after):
    if not before or not after:
        return None
    b=before.get('remaining_words')
    a=after.get('remaining_words')
    if isinstance(b, (int, float)) and isinstance(a, (int, float)):
        return max(0, int(b-a))
    return None


async def _log_chad_request_usage(session, request_id, kind, attempt, response_data, before_balance, http_status):
    after_balance=await _chad_words_balance(session)
    used_words, used_tokens, response_remaining=_response_usage(response_data)
    diff=_usage_from_balance(before_balance, after_balance)
    if used_words is None:
        used_words=diff
        source='balance_diff' if diff is not None else 'unavailable'
    else:
        source='api_response'

    if used_words is not None:
        used_label=f'{used_words} sparks/words'
    elif used_tokens is not None:
        used_label=f'{used_tokens} tokens'
    else:
        used_label='unknown'

    before_remaining=before_balance.get('remaining_words') if before_balance else None
    after_remaining=after_balance.get('remaining_words') if after_balance else response_remaining
    reserved=after_balance.get('reserved_words') if after_balance else None
    _usage_log(
        f'[CHAD USAGE] id={request_id} kind={kind} attempt={attempt} '
        f'http={http_status} used={used_label} source={source} '
        f'before_remaining={before_remaining} after_remaining={after_remaining} '
        f'reserved={reserved}'
    )


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

    request_id=uuid4().hex[:10]
    print(f'[CHAD] request id={request_id} deck={deck} key={key} cards={names!r}', flush=True)
    timeout=aiohttp.ClientTimeout(total=125, connect=20, sock_connect=20, sock_read=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, 3):
            before_balance=await _chad_words_balance(session)
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
                try:
                    usage_data=await response.json(content_type=None)
                except Exception:
                    usage_data={}
                await _log_chad_request_usage(
                    session, request_id, f'{deck}/{key}', attempt, usage_data, before_balance, response.status
                )
                if response.status>=400:
                    raise RuntimeError(f'CHAD API HTTP {response.status}: {text[:1000]}')
                data=usage_data
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
