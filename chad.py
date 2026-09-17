import aiohttp
import config
CHAD_API_URL=getattr(config,'CHAD_API_URL','')
CHAD_API_KEY=getattr(config,'CHAD_API_KEY','')
PROMPTS=getattr(config,'PROMPTS',None)
if PROMPTS is None: PROMPTS=getattr(config,'prompts',{})
if not isinstance(PROMPTS,dict): PROMPTS={}
async def ask(deck,q,cards,paid=False,day=False):
    key='day_free' if day else f'{deck}_{"paid" if paid else "free"}'
    names=', '.join(x.get('name','') if isinstance(x,dict) else str(x) for x in cards)
    exact=f'Ваши карты: {names}. ВАЖНО: используй ТОЛЬКО эти карты и именно в указанном порядке. Не выбирай, не генерируй и не заменяй карты самостоятельно.'
    msg=f'Вопрос клиента: {q}\n\n{exact}'
    payload={'message':msg,'api_key':CHAD_API_KEY,'history':[{'role':'system','content':PROMPTS.get(key,'')},{'role':'user','content':msg}]}
    if not CHAD_API_URL: raise RuntimeError('Не заполнен CHAD_API_URL')
    async with aiohttp.ClientSession() as s:
        async with s.post(CHAD_API_URL,json=payload,headers={'Content-Type':'application/json','Authorization':f'Bearer {CHAD_API_KEY}'},timeout=120) as r:
            t=await r.text()
            if r.status>=400: raise RuntimeError(f'CHAD API HTTP {r.status}: {t[:1000]}')
            try:d=await r.json()
            except Exception:return t
            return d.get('message') or d.get('answer') or d.get('response') or t
