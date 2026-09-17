import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def csv_ints(value):
    return {int(x.strip()) for x in value.split(',') if x.strip().lstrip('-').isdigit()}
BOT_TOKEN=os.getenv('BOT_TOKEN','').strip()
ADMIN_IDS=csv_ints(os.getenv('ADMIN_IDS',''))
ADMIN_CHAT_ID=int(os.getenv('ADMIN_CHAT_ID')) if os.getenv('ADMIN_CHAT_ID','').strip().lstrip('-').isdigit() else None
CHAD_API_URL=os.getenv('CHAD_API_URL','https://ask.chadgpt.ru/api/public/gpt-5.2-thinking').strip()
CHAD_API_KEY=os.getenv('CHAD_API_KEY','').strip()
YOOKASSA_SHOP_ID=os.getenv('YOOKASSA_SHOP_ID','1023526').strip()
YOOKASSA_SECRET_KEY=os.getenv('YOOKASSA_SECRET_KEY','').strip()
PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL','').strip().rstrip('/')
ADMIN_USERNAME=os.getenv('ADMIN_USERNAME','admin').strip()
ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD','change-me').strip()
PACKAGES={3:99,5:159,10:329}

def load_prompts():
    p=Path(__file__).resolve().parent/'prompts.txt'
    if not p.is_file(): return {}
    text=p.read_text(encoding='utf8'); out={}
    import re
    blocks=re.split(r'^===== (.+?) =====\s*$',text,flags=re.M)
    for i in range(1,len(blocks),2):
        title,body=blocks[i],blocks[i+1].strip()
        key={'Промпт Таро Уэйта Бесплатно':'waite_free','Промпт Манара Бесплатно':'manara_free','Промпт Руны Бесплатно':'runes_free','Промпт Карта Дня':'day_free','Промпт Таро Уэйта Платно':'waite_paid','Промпт Манара Платно':'manara_paid','Промпт Руны Платно':'runes_paid'}.get(title)
        if key: out[key]=body
    return out
PROMPTS=load_prompts()
