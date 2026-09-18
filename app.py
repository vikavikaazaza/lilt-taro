import asyncio, hashlib, hmac, html, json, secrets, urllib.parse, re
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import config, db
from chad import ask

BASE=Path(__file__).resolve().parent
router=Router()
bot: Bot


def has_manual_subscription(uid):
    try:
        return bool(db.manual_subscription(uid))
    except Exception as e:
        print(f'[SUBSCRIPTION] read error uid={uid}: {e}', flush=True)
        return False

def premium_access(uid):
    u=db.get(uid)
    return bool(u and (int(u['paid_requests']) > 0 or has_manual_subscription(uid)))

def consume_request(uid, premium=False):
    # For a manually granted subscription, free/referral requests can also be
    # used for 9-card readings. Paid requests are still consumed first.
    if premium:
        return bool(db.consume(uid, premium=True))
    return bool(db.consume(uid, premium=False))

WAITE=[
'Шут','Маг','Верховная Жрица','Императрица','Император','Иерофант','Влюблённые','Колесница','Сила','Отшельник','Колесо Фортуны','Справедливость','Повешенный','Смерть','Умеренность','Дьявол','Башня','Звезда','Луна','Солнце','Суд','Мир',
'Туз Жезлов','Двойка Жезлов','Тройка Жезлов','Четвёрка Жезлов','Пятёрка Жезлов','Шестёрка Жезлов','Семёрка Жезлов','Восьмёрка Жезлов','Девятка Жезлов','Десятка Жезлов','Паж Жезлов','Рыцарь Жезлов','Королева Жезлов','Король Жезлов',
'Туз Кубков','Двойка Кубков','Тройка Кубков','Четвёрка Кубков','Пятёрка Кубков','Шестёрка Кубков','Семёрка Кубков','Восьмёрка Кубков','Девятка Кубков','Десятка Кубков','Паж Кубков','Рыцарь Кубков','Королева Кубков','Король Кубков',
'Туз Мечей','Двойка Мечей','Тройка Мечей','Четвёрка Мечей','Пятёрка Мечей','Шестёрка Мечей','Семёрка Мечей','Восьмёрка Мечей','Девятка Мечей','Десятка Мечей','Паж Мечей','Рыцарь Мечей','Королева Мечей','Король Мечей',
'Туз Пентаклей','Двойка Пентаклей','Тройка Пентаклей','Четвёрка Пентаклей','Пятёрка Пентаклей','Шестёрка Пентаклей','Семёрка Пентаклей','Восьмёрка Пентаклей','Девятка Пентаклей','Десятка Пентаклей','Паж Пентаклей','Рыцарь Пентаклей','Королева Пентаклей','Король Пентаклей']
MANARA=['Дурак','Маг','Верховная Жрица','Императрица','Император','Верховный Жрец','Возлюбленные','Колесница','Справедливость','Отшельник','Зеркало','Сила','Наказание','Смерть','Умеренность','Дьявол','Башня','Звезда','Луна','Солнце','Суд','Мир','Туз Огня','Двойка Огня','Тройка Огня','Четверка Огня','Пятерка Огня','Шестерка Огня','Семерка Огня','Восьмерка Огня','Девятка Огня','Десятка Огня','Слуга Огня','Всадница Огня','Королева Огня','Король Огня','Туз Воздуха','Двойка Воздуха','Тройка Воздуха','Четверка Воздуха','Пятерка Воздуха','Шестерка Воздуха','Семерка Воздуха','Восьмерка Воздуха','Девятка Воздуха','Десятка Воздуха','Слуга Воздуха','Всадница Воздуха','Королева Воздуха','Король Воздуха','Туз Земли','Двойка Земли','Тройка Земли','Четверка Земли','Пятерка Земли','Шестерка Земли','Семерка Земли','Восьмерка Земли','Девятка Земли','Десятка Земли','Слуга Земли','Всадница Земли','Королева Земли','Король Земли','Туз Воды','Двойка Воды','Тройка Воды','Четверка Воды','Пятерка Воды','Шестерка Воды','Семерка Воды','Восьмерка Воды','Девятка Воды','Десятка Воды','Слуга Воды','Всадница Воды','Королева Воды','Король Воды']
DECK_NAMES={'waite':'Таро Уэйта','manara':'Таро Манара','day':'Карта дня'}

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='Таро Уэйта',callback_data='deck:waite'),InlineKeyboardButton(text='Таро Манара 🍓',callback_data='deck:manara')],
      [InlineKeyboardButton(text='Карта дня',callback_data='day')],
      [InlineKeyboardButton(text='Реферальная программа',callback_data='friend')],
      [InlineKeyboardButton(text='Оформить подписку',callback_data='pay')]])

def pay_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='3 вопроса — 99 рублей',callback_data='pack:3')],[InlineKeyboardButton(text='5 вопросов — 159 рублей',callback_data='pack:5')],[InlineKeyboardButton(text='10 вопросов — 329 рублей',callback_data='pack:10')]])

def main_image(): return BASE/'Фото'/'Главное меню.jpg'
def sub_image(): return BASE/'Фото'/'Подписка.jpg'

def bot_url(): return config.PUBLIC_BASE_URL

def mini_url(deck,mode):
    if not bot_url().startswith('https://'): raise RuntimeError('PUBLIC_BASE_URL должен начинаться с https://')
    return f'{bot_url()}/miniapp?deck={urllib.parse.quote(deck)}&mode={urllib.parse.quote(mode)}'

def mini_button(deck,mode,text=None):
    button_text=text or ('Получить карту дня' if deck=='day' else 'Получить карты')
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text,web_app=WebAppInfo(url=mini_url(deck,mode)))]] )

async def main_menu(m):
    u=db.get(m.from_user.id); left=(int(u['requests']) if u else 0)+(int(u['paid_requests']) if u else 0)
    text='Добро пожаловать в пространство магии 🌙️\n\nЗдесь вы можете спросить о чём угодно — найдете ответ на любой вопрос 🕯️\n\nКарты ждут вас ☀️\n\nВаше количество запросов: '+str(left)
    p=main_image()
    if p.is_file(): await m.answer_photo(FSInputFile(p),caption=text,reply_markup=menu())
    else: await m.answer(text,reply_markup=menu())

async def subscription(m):
    text='🌟 Разгадай больше секретов с подпиской 🌟\n\nПреимущества:\n🔥 С подпиской ответы больше и детальнее\n🔥 Расклад не из трех, а из девяти карт\n🔥 Полное погружение в вашу ситуацию\n\nЖдем тебя в нашем эксклюзивном сообществе ❤️'
    p=sub_image()
    if p.is_file(): await m.answer_photo(FSInputFile(p),caption=text,reply_markup=pay_menu())
    else: await m.answer(text,reply_markup=pay_menu())

async def day_start(m):
    u=db.get(m.from_user.id)
    if not u or int(u['requests'])+int(u['paid_requests'])<=0:
        await m.answer('У вас осталось 0 запросов.')
        await subscription(m)
        return
    db.set_pending(m.from_user.id,'day','free','Карта дня')
    await m.answer('Сейчас карты покажут, на что стоит обратить внимание сегодня 🧘🏼',reply_markup=mini_button('day','free','Получить карту дня'))

async def deck_start(m,deck):
    mode='premium' if premium_access(m.from_user.id) else 'free'
    db.set_pending(m.from_user.id,deck,mode,'')
    await m.answer(f'Давай погадаем на {DECK_NAMES[deck]}\n\nСформулируй свой вопрос и напиши его полностью ❤️\n\nНапример: Что ждет меня в следующем месяце?')

@router.message(CommandStart())
async def start(m:types.Message):
    parts=(m.text or '').split(maxsplit=1); arg=parts[1].strip() if len(parts)>1 else ''
    existing=db.get(m.from_user.id)
    source='telegram'; referrer=None
    if not existing:
        if arg.startswith('ref'):
            referrer=db.use_ref(arg,m.from_user.id); source='referral' if referrer else 'telegram'
        elif arg.lower() in ('insta','instagram'):
            source='instagram'
        db.user(m.from_user,source,referrer)
        if referrer:
            db.add(referrer,1); db.event(referrer,'referral_success',str(m.from_user.id)); await bot.send_message(referrer,'Вам начислен 1 бесплатный запрос за нового друга!❤️')
    else:
        db.user(m.from_user,existing['source'] or 'telegram',existing['referrer_id'])
    db.event(m.from_user.id,'start',source if not existing else 'return')
    await main_menu(m)

@router.message(Command('friend'))
async def friend(m): await friend_show(m)
async def friend_show(m):
    await m.answer('Создавай ссылку для своих друзей и делись ею! За каждого приведенного друга дарим тебе 1 бесплатный запрос ❤️ Действуй 🔮',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Создать ссылку',callback_data='ref:create')]]))

@router.message(Command('pay'))
async def pay_cmd(m): await subscription(m)
@router.message(Command('magic'))
async def magic(m): await deck_start(m,'waite')
@router.message(Command('manara'))
async def manara(m): await deck_start(m,'manara')
@router.message(Command('day'))
async def day_cmd(m): await day_start(m)

@router.callback_query(F.data.startswith('deck:'))
async def deck_cb(c):
    await c.answer()
    uid=c.from_user.id
    deck=c.data.split(':',1)[1]
    mode='premium' if premium_access(uid) else 'free'
    db.set_pending(uid,deck,mode,'')
    await c.message.answer(
        f'Давай погадаем на {DECK_NAMES[deck]}\n\n'
        'Сформулируй свой вопрос и напиши его полностью ❤️\n\n'
        'Например: Что ждет меня в следующем месяце?'
    )

@router.callback_query(F.data=='day')
async def day_cb(c):
    await c.answer()
    uid=c.from_user.id
    u=db.get(uid)
    if not u or int(u['requests'])+int(u['paid_requests'])<=0:
        await c.message.answer('У вас осталось 0 запросов.')
        await subscription(c.message)
        return
    db.set_pending(uid,'day','free','Карта дня')
    await c.message.answer('Сейчас карты покажут, на что стоит обратить внимание сегодня 🧘🏼',reply_markup=mini_button('day','free','Получить карту дня'))

@router.callback_query(F.data=='friend')
async def friend_cb(c): await c.answer(); await friend_show(c.message)
@router.callback_query(F.data=='pay')
async def pay_cb(c): await c.answer(); await subscription(c.message)

@router.callback_query(F.data=='ref:create')
async def ref_create(c):
    code=db.create_ref(c.from_user.id)
    me=await bot.get_me(); link=f'https://t.me/{me.username}?start={code}'
    await c.answer(); await c.message.answer(f'Вот твоя ссылка, скопируй и отправь ее другу🕯️\n\n{link}')

@router.callback_query(F.data.startswith('pack:'))
async def pack(c):
    n=int(c.data.split(':')[1]); await c.answer()
    if n not in config.PACKAGES: return
    db.set_pending(c.from_user.id,'payment',str(n),'')
    await c.message.answer('Введи почту для отправки чека 📧')

@router.message(F.text)
async def text_message(m):
    p=db.get_pending(m.from_user.id)
    if not p: return
    if p['deck']=='payment':
        import re
        email=m.text.strip()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email): await m.answer('Пожалуйста, введи корректную почту.'); return
        await create_payment(m,int(p['mode']),email); db.clear_pending(m.from_user.id); return
    # question
    u=db.get(m.from_user.id); total=int(u['requests'])+int(u['paid_requests'])
    if total<=0:
        await m.answer('У вас осталось 0 запросов.')
        await subscription(m); return
    mode='premium' if premium_access(m.from_user.id) else 'free'
    deck=p['deck']; db.set_pending(m.from_user.id,deck,mode,m.text)
    db.event(m.from_user.id,'question',f'{deck}|{m.text[:500]}')
    await send_admin_question(m,deck,m.text)
    if deck=='day':
        db.set_pending(m.from_user.id,'day','free',m.text)
        await m.answer('Сейчас карты покажут, на что стоит обратить внимание сегодня 🧘🏼',reply_markup=mini_button('day','free','Получить карту дня'))
    else:
        await m.answer('Твой вопрос услышан. Сейчас карты покажут то, что важно увидеть именно тебе 🌙',reply_markup=mini_button(deck,mode,'Получить карты'))

def match_waite(q):
    norm=' '.join(q.lower().replace('ё','е').split())
    for n in WAITE:
        if ' '.join(n.lower().replace('ё','е').split())==norm: return n
    return None

async def send_admin_question(m,deck,q):
    if not config.ADMIN_CHAT_ID:
        return
    username=f'@{m.from_user.username}' if m.from_user.username else '—'
    text=(f'🔮 КЛИЕНТ ЗАДАЛ ВОПРОС 🔮\n\n'
          f'🕯️ Имя: {html.escape(m.from_user.full_name)}\n'
          f'🕯️ Ник: {html.escape(username)}\n'
          f'{html.escape(DECK_NAMES.get(deck,deck))}: {html.escape(q)}')
    try:
        await bot.send_message(config.ADMIN_CHAT_ID,text,parse_mode='HTML')
    except Exception as e:
        # Ошибка отправки в админскую группу не должна блокировать клиента.
        print(f'[ADMIN] Не удалось отправить вопрос в ADMIN_CHAT_ID: {e}')

# YooKassa
async def create_payment(m,n,email):
    if not config.YOOKASSA_SECRET_KEY or not config.PUBLIC_BASE_URL.startswith('https://'):
        await m.answer('Оплата пока не настроена: проверьте YOOKASSA_SECRET_KEY и PUBLIC_BASE_URL в .env.'); return
    from yookassa import Configuration, Payment
    Configuration.account_id=config.YOOKASSA_SHOP_ID; Configuration.secret_key=config.YOOKASSA_SECRET_KEY
    idem=secrets.token_hex(16); amount=config.PACKAGES[n]
    payment=Payment.create({
      'amount':{'value':f'{amount:.2f}','currency':'RUB'},
      'capture':True,
      'confirmation':{'type':'redirect','return_url':f'{config.PUBLIC_BASE_URL}/payment/success'},
      'description':'Оплата подписки Лилит',
      'receipt':{'customer':{'email':email},'items':[{'description':'Оплата подписки Лилит','quantity':'1.00','amount':{'value':f'{amount:.2f}','currency':'RUB'},'vat_code':1,'payment_mode':'full_payment','payment_subject':'service'}]},
      'metadata':{'user_id':str(m.from_user.id),'requests':str(n),'email':email}
    },idem)
    db.payment(m.from_user.id,payment.id,amount,n,'pending',email); db.event(m.from_user.id,'payment_created',str(payment.id))
    await m.answer(f'Перейдите к оплате: {payment.confirmation.confirmation_url}')

app=FastAPI(title='Lilit Taro')
app.mount('/cards',StaticFiles(directory=str(BASE)),name='cards')

@app.get('/health')
async def health(): return {'ok':True,'service':'lilit-taro'}

@app.get('/miniapp',response_class=HTMLResponse)
async def miniapp(): return FileResponse(BASE/'web'/'index.html')

@app.get('/api/miniapp/config')
async def mini_config(deck:str='waite'):
    if deck not in ('waite','manara','day'):
        raise HTTPException(400,'unknown deck')
    names = WAITE if deck in ('waite','day') else MANARA
    return {'deck':deck,'cards':[{'id':i,'name':n,'image':card_image(deck,i,n)} for i,n in enumerate(names)]}

def card_image(deck,i,name):
    if deck in ('waite','day'):
        # Карта дня использует отдельную папку, если она есть,
        # иначе надежно берет изображения из колоды Уэйта.
        day_folder=BASE/'Карта Дня'
        if deck=='day' and day_folder.is_dir():
            for filename in (f'{i:02d}.jpg',f'{i}.jpg'):
                if (day_folder/filename).is_file():
                    return '/cards/'+urllib.parse.quote(day_folder.name)+'/'+urllib.parse.quote(filename)
        folder=BASE/'Таро Уэйта'; filename=f'{i:02d}.jpg'
        if (folder/filename).is_file():
            return '/cards/'+urllib.parse.quote(folder.name)+'/'+urllib.parse.quote(filename)
        return ''
    if deck == 'manara':
        if i < 22:
            filename=f'{i}.jpg'
        else:
            prefix={22:'ж',36:'ч',50:'м',64:'п'}[22+14*((i-22)//14)]
            number=(i-22)%14+1
            filename=f'{prefix}{number}.jpg'
        folder=BASE/'Таро Манара'
        if (folder/filename).is_file():
            return '/cards/'+urllib.parse.quote(folder.name)+'/'+urllib.parse.quote(filename)
        return ''
    return ''

def validate_init_data(init_data):
    if not init_data: return None
    try:
        data=dict(urllib.parse.parse_qsl(init_data,keep_blank_values=True)); received=data.pop('hash',None)
        if not received: return None
        check='\n'.join(f'{k}={data[k]}' for k in sorted(data))
        secret=hmac.new(b'WebAppData',config.BOT_TOKEN.encode(),hashlib.sha256).digest()
        calc=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc,received): return None
        user_data=json.loads(data.get('user','{}')); return user_data
    except Exception: return None

async def process_reading(uid, deck, mode, cards, question, premium):
    names=[str(x.get('name','')) if isinstance(x,dict) else str(x) for x in cards]
    try:
        print(f'[READING] START uid={uid} deck={deck} mode={mode} question={question["question"]!r} cards={names!r}', flush=True)
        answer=await asyncio.wait_for(
            ask(deck, question['question'], [{'name': n} for n in names], paid=premium, day=(deck=='day')),
            timeout=130
        )
        if not answer or not str(answer).strip():
            raise RuntimeError('CHAD API вернул пустой ответ')
        answer=str(answer).strip()
        db.reading(uid,deck,mode,question['question'],json.dumps(names,ensure_ascii=False),answer)
        db.clear_pending(uid)
        user_now=db.get(uid)
        left=(db.balance(uid) + int(user_now['paid_requests'])) if user_now else 0
        # Keep the bot in question-entry mode so the very next text message
        # starts another reading without requiring the user to press a deck button again.
        next_mode='premium' if premium_access(uid) and deck!='day' else 'free'
        db.set_pending(uid,deck,next_mode,'')
        await bot.send_message(uid,answer)
        await bot.send_message(uid,f'Ваше количество запросов: {left}\n\nЗадайте свой вопрос ❤️')
        print(f'[READING] DONE uid={uid} left={left}', flush=True)
    except Exception as e:
        print(f'[READING] ERROR uid={uid}: {type(e).__name__}: {e}', flush=True)
        try:
            db.add(uid,1)
            db.clear_pending(uid)
            await bot.send_message(uid,'Не удалось получить расшифровку прямо сейчас. Запрос возвращён на баланс. Попробуйте ещё раз немного позже.')
        except Exception as inner:
            print(f'[READING] RECOVERY ERROR uid={uid}: {type(inner).__name__}: {inner}', flush=True)

@app.post('/api/miniapp/select')
async def mini_select(request:Request):
    try:
        body=await request.json()
        tg=validate_init_data(body.get('initData',''))
        if not tg: raise HTTPException(403,'Недействительный Telegram initData')
        uid=int(tg['id'])
        user=db.get(uid)
        if not user: raise HTTPException(404,'Пользователь не найден')
        deck=body.get('deck')
        cards=body.get('cards',[])
        question=db.get_pending(uid)
        if not question or question['deck']!=deck or not question['question']:
            raise HTTPException(409,'Вопрос не найден')
        mode='premium' if (premium_access(uid) and deck!='day') else 'free'
        # Never trust the Mini App's mode for access control; the server decides.
        expected=1 if deck=='day' else (9 if mode=='premium' else 3)
        if deck not in ('waite','manara','day') or len(cards)!=expected:
            raise HTTPException(400,'Неверное количество карт')
        names=[str(x.get('name','')) if isinstance(x,dict) else str(x) for x in cards]
        allowed=WAITE if deck in ('waite','day') else MANARA
        if any(n not in allowed for n in names):
            raise HTTPException(400,'Недопустимая карта')
        premium=(mode=='premium' and deck!='day')
        if not consume_request(uid,premium=premium):
            raise HTTPException(409,'Нет доступных запросов')
        print(f'[MINI] ACCEPT uid={uid} deck={deck} mode={mode} cards={names!r}', flush=True)
        await bot.send_message(uid,'Отправляем ваш запрос во Вселенную... Подождите...')
        await process_reading(uid,deck,mode,[{'name':n} for n in names],question,premium)
        return {'ok':True,'accepted':True}
    except HTTPException:
        raise
    except Exception as e:
        print(f'[MINI] ERROR: {type(e).__name__}: {e}', flush=True)
        raise HTTPException(500,'Ошибка обработки расклада')

@app.post('/yookassa/webhook')
async def yookassa_webhook(request:Request):
    body=await request.json(); obj=body.get('object',{}); event=body.get('event','')
    if event!='payment.succeeded': return {'ok':True}
    pid=obj.get('id'); existing=db.payment_status(pid)
    if existing and existing['status']=='succeeded': return {'ok':True}
    meta=obj.get('metadata',{}); uid=int(meta.get('user_id',0)); n=int(meta.get('requests',0)); amount=int(round(float(obj.get('amount',{}).get('value',0))))
    if not uid or n not in config.PACKAGES: return {'ok':False}
    db.payment(uid,pid,amount,n,'pending',meta.get('email','')); db.set_payment_status(pid,'succeeded'); db.add_paid(uid,n,amount); db.event(uid,'payment_succeeded',pid)
    if config.ADMIN_CHAT_ID:
        u=db.get(uid); username=f'@{u["username"]}' if u and u['username'] else '—'; await bot.send_message(config.ADMIN_CHAT_ID,f'🔥 КЛИЕНТ ОПЛАТИЛ 🔥\n\n🕯️ Имя: {u["name"] if u else uid}\n🕯️ Ник: {username}\n🕯️ Сумма: {amount} рублей')
    await bot.send_message(uid,f'Вам доступно {n} запросов 🌟')
    return {'ok':True}

@app.get('/payment/success',response_class=HTMLResponse)
async def payment_success(): return '<html><meta charset="utf-8"><body style="font-family:Arial;text-align:center;padding:40px"><h2>Оплата прошла успешно ❤️</h2><p>Вернитесь в Telegram — запросы уже начислены.</p></body></html>'

def auth_ok(request:Request):
    a=request.headers.get('authorization','')
    if not a.startswith('Basic '): return False
    import base64
    try: raw=base64.b64decode(a[6:]).decode(); u,p=raw.split(':',1); return secrets.compare_digest(u,config.ADMIN_USERNAME) and secrets.compare_digest(p,config.ADMIN_PASSWORD)
    except: return False

def admin_page():
    s=db.stats(); us=db.users(); tops=db.top_payers(); src=db.source_stats(); reads=db.recent_readings(); pays=db.recent_payments()
    rows=''.join(f'<tr><td>{u["id"]}</td><td>{html.escape(u["name"] or "")}</td><td>@{html.escape(u["username"] or "—")}</td><td>{int(u["requests"])+int(u["paid_requests"])}</td><td>{int(u["requests"])}</td><td>{int(u["paid_requests"])}</td><td>{"ВКЛ" if has_manual_subscription(u["id"]) else "—"}</td><td>{html.escape(u["source"] or "telegram")}</td><td>{html.escape(u["last_seen"] or "")}</td></tr>' for u in us)
    top=''.join(f'<tr><td>{html.escape(x["name"] or "")}</td><td>@{html.escape(x["username"] or "—")}</td><td>{x["total_spent"]} ₽</td></tr>' for x in tops)
    sources=''.join(f'<span class="pill">{html.escape(x["source"])}: {x["n"]}</span>' for x in src)
    rrows=''.join(f'<tr><td>{r["created_at"][:19].replace("T"," ")}</td><td>{html.escape(r["name"] or str(r["user_id"]))}</td><td>{html.escape(DECK_NAMES.get(r["deck"],r["deck"]))}</td><td>{html.escape(r["question"][:120])}</td></tr>' for r in reads)
    prows=''.join(f'<tr><td>{p["created_at"][:19].replace("T"," ")}</td><td>{html.escape(p["name"] or str(p["user_id"]))}</td><td>{p["amount"]} ₽</td><td>{p["requests"]}</td><td>{html.escape(p["status"] or "")}</td></tr>' for p in pays)
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Lilit Admin</title><style>
body{{margin:0;background:#090816;color:#f5e9c8;font:14px Arial,sans-serif}}.wrap{{max-width:1250px;margin:auto;padding:28px}}h1{{font-weight:500;letter-spacing:1px}}h2{{font-weight:500}}.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}.card,section{{background:#15132a;border:1px solid #302a52;border-radius:16px;padding:18px;box-shadow:0 10px 30px #0003}}.num{{font-size:28px;margin-top:8px}}table{{width:100%;border-collapse:collapse;min-width:760px}}.scroll{{overflow:auto}}td,th{{padding:10px;border-bottom:1px solid #292440;text-align:left;white-space:nowrap}}input,textarea,button{{padding:10px;border-radius:9px;border:1px solid #4b416e;background:#0d0c1c;color:#fff}}textarea{{width:100%;min-height:100px}}button{{cursor:pointer;background:#d7bb73;color:#171225;font-weight:bold}}.pill{{display:inline-block;padding:8px 12px;border:1px solid #4b416e;border-radius:999px;margin:4px}}form.row{{display:flex;gap:10px;flex-wrap:wrap}}.muted{{color:#aaa2bc}}</style></head><body><div class="wrap"><h1>Лилит · Панель управления</h1><p class="muted">Один сервер · одна база SQLite · бот + Mini App + платежи</p><div class="grid"><div class="card">Пользователи<div class="num">{s['users']}</div></div><div class="card">Активные 7 дней<div class="num">{s['active']}</div></div><div class="card">Расклады<div class="num">{s['questions']}</div></div><div class="card">Платежи<div class="num">{s['payments']}</div></div><div class="card">Выручка<div class="num">{s['revenue']} ₽</div></div></div><br>
<section><h2>Начислить запросы</h2><form class="row" method="post" action="/admin/add-requests"><input name="uid" placeholder="Telegram ID" required><input name="amount" type="number" min="1" placeholder="Количество" required><button>Начислить</button></form></section><br>
<section><h2>Ручная подписка</h2><p class="muted">Включает человеку режим расклада на 9 карт. Оплата не требуется. Запросы при этом расходуются как обычно.</p><form class="row" method="post" action="/admin/set-subscription"><input name="uid" placeholder="Telegram ID" required><button name="enabled" value="1">Включить подписку</button><button name="enabled" value="0">Отключить подписку</button></form></section><br>
<section><h2>Рассылка</h2><form method="post" action="/admin/broadcast"><textarea name="text" placeholder="Текст сообщения" required></textarea><br><br><button>Отправить всем пользователям</button></form></section><br>
<section><h2>Источники</h2>{sources}</section><br>
<section><h2>Последние вопросы</h2><div class="scroll"><table><tr><th>Дата</th><th>Клиент</th><th>Колода</th><th>Вопрос</th></tr>{rrows}</table></div></section><br>
<section><h2>Платежи</h2><div class="scroll"><table><tr><th>Дата</th><th>Клиент</th><th>Сумма</th><th>Запросы</th><th>Статус</th></tr>{prows}</table></div></section><br>
<section><h2>Клиенты с оплатами</h2><div class="scroll"><table><tr><th>Имя</th><th>Ник</th><th>Всего</th></tr>{top}</table></div></section><br>
<section><h2>Пользователи</h2><div class="scroll"><table><tr><th>ID</th><th>Имя</th><th>Ник</th><th>Всего</th><th>Бесплатные</th><th>Оплаченные</th><th>Ручная подписка</th><th>Источник</th><th>Последний вход</th></tr>{rows}</table></div></section></div></body></html>'''

@app.get('/admin',response_class=HTMLResponse)
async def admin(request:Request):
    if not auth_ok(request): return HTMLResponse('Авторизация требуется',401,headers={'WWW-Authenticate':'Basic realm="Lilit Admin"'})
    return admin_page()

@app.post('/admin/add-requests')
async def admin_add(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    form=await request.form(); uid=int(form['uid']); amount=int(form['amount']);
    if not db.get(uid): raise HTTPException(404,'Пользователь не найден')
    db.add(uid,amount); db.event(uid,'admin_add',str(amount)); return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin">')

@app.post('/admin/set-subscription')
async def admin_set_subscription(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    form=await request.form()
    raw_uid=str(form.get('uid','')).strip()
    raw_enabled=str(form.get('enabled','1')).strip()
    if not raw_uid.isdigit():
        raise HTTPException(400,'Telegram ID должен содержать только цифры')
    uid=int(raw_uid)
    if not db.get(uid):
        raise HTTPException(404,'Пользователь не найден')
    enabled=raw_enabled=='1'
    db.set_manual_subscription(uid,enabled)
    db.event(uid,'admin_subscription', 'enabled' if enabled else 'disabled')
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin">')

@app.post('/admin/broadcast')
async def broadcast(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    form=await request.form(); text=form.get('text','').strip(); count=0
    for u in db.users(10000):
        try: await bot.send_message(u['id'],text); count+=1; await asyncio.sleep(.05)
        except: pass
    return {'ok':True,'sent':count}

async def main():
    global bot
    db.init()
    if not config.BOT_TOKEN: raise RuntimeError('Заполните BOT_TOKEN в .env')
    bot=Bot(config.BOT_TOKEN)
    dp=Dispatcher(); dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    port=int(__import__('os').getenv('PORT','8000'))
    server=uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=port,log_level='info'))
    await asyncio.gather(dp.start_polling(bot), server.serve())

if __name__=='__main__': asyncio.run(main())
