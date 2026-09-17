import aiohttp
from config import CHAD_API_URL, CHAD_API_KEY, PROMPTS

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

    user_message = f'Вопрос клиента: {q}\n\n{exact_cards}'

    payload = {
        'message': user_message,
        'api_key': CHAD_API_KEY,
        'history': [
            {'role': 'system', 'content': PROMPTS.get(key, '')},
            {'role': 'user', 'content': user_message},
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
            text = await r.text()

            if r.status >= 400:
                raise RuntimeError(f'CHAD API HTTP {r.status}: {text[:1000]}')

            try:
                data = await r.json()
            except Exception:
                return text

            return (
                data.get('message')
                or data.get('answer')
                or data.get('response')
                or text
            )
