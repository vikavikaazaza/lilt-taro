import aiohttp
import config

CHAD_API_URL=getattr(config,'CHAD_API_URL','').strip()
CHAD_API_KEY=getattr(config,'CHAD_API_KEY','').strip()
PROMPTS=getattr(config,'PROMPTS',None)
if PROMPTS is None:
    PROMPTS=getattr(config,'prompts',{})
if not isinstance(PROMPTS,dict):
    PROMPTS={}

async def ask(deck,q,cards,paid=False,day=False):
    key='day_free' if day else f'{deck}_{"paid" if paid else "free"}'
    names=', '.join(x.get('name','') if isinstance(x,dict) else str(x) for x in cards)
    if not CHAD_API_URL:
        raise RuntimeError('Не заполнен CHAD_API_URL')
    if not CHAD_API_KEY:
        raise RuntimeError('Не заполнен CHAD_API_KEY')

    # Карты передаются отдельным сообщением history, чтобы модель точно видела
    # именно выбранные карты и их порядок.
    user_text=q.strip()
    cards_text=f'Ваши карты: {names}. ВАЖНО: используй ТОЛЬКО эти карты и именно в указанном порядке. Не выбирай, не генерируй и не заменяй карты самостоятельно.'
    payload={
        'message': user_text,
        'api_key': CHAD_API_KEY,
        'history': [
            {'role':'system','content':PROMPTS.get(key,'')},
            {'role':'user','content':user_text},
            {'role':'assistant','content':cards_text},
        ],
    }
    print(f'[CHAD] request deck={deck} key={key} cards={names!r}', flush=True)
    timeout=aiohttp.ClientTimeout(total=125, connect=20, sock_connect=20, sock_read=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            CHAD_API_URL,
            json=payload,
            headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'},
        ) as response:
            text=await response.text()
            print(f'[CHAD] response status={response.status} body_len={len(text)}', flush=True)
            if response.status>=400:
                raise RuntimeError(f'CHAD API HTTP {response.status}: {text[:1000]}')
            try:
                data=await response.json(content_type=None)
            except Exception:
                data={}
            if isinstance(data,dict):
                answer=data.get('message') or data.get('answer') or data.get('response') or data.get('text')
                if answer:
                    return str(answer)
            if text.strip():
                return text.strip()
            raise RuntimeError('CHAD API вернул пустой ответ')
