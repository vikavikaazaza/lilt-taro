import aiohttp
from config import CHAD_API_URL, CHAD_API_KEY, prompts

async def ask(deck, q, cards, paid=False, day=False):
    key = 'day_free' if day else f'{deck}_{"paid" if paid else "free"}'
    names = ', '.join(
        x.get('name', '') if isinstance(x, dict) else str(x)
        for x in cards
    )

    exact_cards = (
        f'Ваши карты: {names}. '
        'ВАЖНО: используй ТОЛЬКО эти карты и именно в указанном порядке. '
        'Не выбирай, не генерируй и не заменяй карты самостоятельно.'
    )

    payload = {
        'message': f'Вопрос клиента: {q}\n\n{exact_cards}',
        'api_key': CHAD_API_KEY,
        'history': [
            {'role': 'system', 'content': prompts.get(key, '')},
            {'role': 'user', 'content': f'Вопрос клиента: {q}\n\n{exact_cards}'},
            {'role': 'assistant', 'content': exact_cards},
        ],
    }

    if not CHAD_API_URL:
        raise RuntimeError('Не заполнен CHAD_API_URL')

    async with aiohttp.ClientSession() as s:
        async with s.post(
            CHAD_API_URL,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {CHAD_API_KEY}',
            },
            timeout=120,
        ) as r:
            t = await r.text()
            if r.status >= 400:
                raise RuntimeError(t[:500])
            try:
                d = await r.json()
                return d.get('message') or d.get('answer') or d.get('response') or t
            except Exception:
                return t
