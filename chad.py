import aiohttp
from config import CHAD_API_URL, CHAD_API_KEY, PROMPTS

async def ask(deck, question, cards, paid=False, day=False):
    key = 'day_free' if day else f'{deck}_' + ('paid' if paid else 'free')
    prompt = PROMPTS.get(key, '').strip()
    if not CHAD_API_URL or not CHAD_API_KEY:
        raise RuntimeError('Не заполнены CHAD_API_URL или CHAD_API_KEY в .env')
    names=', '.join(c['name'] for c in cards)
    system = prompt or 'Дай ответ на русском языке, учитывая вопрос клиента и выбранные карты. Начни с перечисления карт.'
    payload={
      'message': question,
      'api_key': CHAD_API_KEY,
      'history': [
        {'role':'system','content':system},
        {'role':'user','content':question},
        {'role':'assistant','content':f'Ваши карты: {names}🌙️'}
      ]
    }
    headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'}
    timeout=aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.post(CHAD_API_URL,json=payload,headers=headers) as r:
            text=await r.text()
            if r.status>=400: raise RuntimeError(f'CHAD API {r.status}: {text[:500]}')
            try: data=await r.json(content_type=None)
            except Exception: return text
            return data.get('message') or data.get('answer') or data.get('response') or text
