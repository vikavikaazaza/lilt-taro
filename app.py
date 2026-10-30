import asyncio, hashlib, hmac, html, json, secrets, urllib.parse, re, aiohttp
from pathlib import Path
from datetime import date as dt_date, datetime as dt_datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router, types, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import config, db
from chad import ask
from transits import calculate_transits, daily_sky_signature
from pdf_reports import build_transit_pdf
from astro_reports import build_transit_interpretation

BASE=Path(__file__).resolve().parent
router=Router()
bot: Bot
BROADCAST_TASKS=set()
READING_TASKS=set()
TRANSIT_TASKS=set()
TRANSIT_MINIAPP_VERSION='1'
NOMINATIM_LOCK=asyncio.Lock()
NOMINATIM_LAST=0.0

class DialogueMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.CallbackQuery) and event.from_user:
            try:
                db.touch(event.from_user.id)
                db.log_message(event.from_user.id,'user','[button] '+str(event.data or ''),'callback')
            except Exception as e:
                print(f'[DIALOGUE] callback log error: {type(e).__name__}: {e}',flush=True)
        if isinstance(event, types.Message) and event.from_user:
            text=event.text or event.caption
            if not text:
                text=f'[{getattr(event, "content_type", "message")}]'
            try:
                db.touch(event.from_user.id)
                db.log_message(event.from_user.id,'user',text,getattr(event,'content_type','text'))
            except Exception as e:
                print(f'[DIALOGUE] incoming log error: {type(e).__name__}: {e}',flush=True)
        return await handler(event,data)

router.message.middleware(DialogueMiddleware())
router.callback_query.middleware(DialogueMiddleware())

async def answer_user(m,text,**kwargs):
    db.log_message(int(m.chat.id),'bot',text,'text')
    return await m.answer(text,**kwargs)

async def answer_user_photo(m,photo,caption=None,**kwargs):
    if caption:
        db.log_message(int(m.chat.id),'bot',caption,'photo')
    return await m.answer_photo(photo,caption=caption,**kwargs)

async def send_user_message(uid,text,**kwargs):
    db.log_message(int(uid),'bot',text,'text')
    return await bot.send_message(uid,text,**kwargs)


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
      [InlineKeyboardButton(text='Таро Уэйта',callback_data='deck:waite'),InlineKeyboardButton(text='Таро Манара',callback_data='deck:manara')],
      [InlineKeyboardButton(text='Карта дня',callback_data='day')],
      [InlineKeyboardButton(text='Реферальная программа ',callback_data='friend')],
      [InlineKeyboardButton(text='Оформить подписку ',callback_data='pay')]])

def pay_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='3 вопроса — 99 рублей',callback_data='pack:3')],[InlineKeyboardButton(text='5 вопросов — 159 рублей',callback_data='pack:5')],[InlineKeyboardButton(text='10 вопросов — 329 рублей',callback_data='pack:10')]])

def main_image(): return BASE/'Фото'/'Главное меню.jpg'
def sub_image(): return BASE/'Фото'/'Подписка.jpg'

def bot_url(): return config.PUBLIC_BASE_URL

MINIAPP_VERSION='16'

def mini_url(deck,mode,choice='manual'):
    if not bot_url().startswith('https://'): raise RuntimeError('PUBLIC_BASE_URL должен начинаться с https://')
    return (f'{bot_url()}/miniapp?deck={urllib.parse.quote(deck)}&mode={urllib.parse.quote(mode)}'
            f'&choice={urllib.parse.quote(choice)}&v={MINIAPP_VERSION}')

def mini_buttons(deck,mode):
    manual_text='Вытянуть карту дня 🌙' if deck=='day' else 'Вытянуть карты 🌙'
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=manual_text,web_app=WebAppInfo(url=mini_url(deck,mode,'manual')))],
        [InlineKeyboardButton(text='Довериться судьбе ✨',web_app=WebAppInfo(url=mini_url(deck,mode,'fate')))]
    ])

def transit_mini_button():
    if not bot_url().startswith('https://'):
        raise RuntimeError('PUBLIC_BASE_URL должен начинаться с https://')
    url=f'{bot_url()}/transits?v={TRANSIT_MINIAPP_VERSION}'
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Открыть расчёт транзитов 🌌',web_app=WebAppInfo(url=url))]])

async def transit_start(m, uid=None):
    uid=int(uid or m.from_user.id)
    await answer_user(m, 'Посмотрим, какие темы и влияния могут быть активны для тебя в выбранную дату 🌌\n\nВведи данные рождения и дату, на которую хочешь сделать расчёт.', reply_markup=transit_mini_button())


async def main_menu(m):
    u=db.get(m.from_user.id); left=(int(u['requests']) if u else 0)+(int(u['paid_requests']) if u else 0)
    text='Добро пожаловать в пространство магии 🌙️\n\nЗдесь вы можете спросить о чём угодно — найдете ответ на любой вопрос 🕯️\n\nКарты ждут вас ☀️\n\nВаше количество запросов: '+str(left)
    p=main_image()
    if p.is_file(): await answer_user_photo(m, FSInputFile(p),caption=text,reply_markup=menu())
    else: await answer_user(m, text,reply_markup=menu())

async def subscription(m):
    text='🌟 Разгадай больше секретов с подпиской 🌟\n\nПреимущества:\n🔥 С подпиской ответы больше и детальнее\n🔥 Расклад не из трех, а из девяти карт\n🔥 Полное погружение в вашу ситуацию\n\nЖдем тебя в нашем эксклюзивном сообществе ❤️'
    p=sub_image()
    if p.is_file(): await answer_user_photo(m, FSInputFile(p),caption=text,reply_markup=pay_menu())
    else: await answer_user(m, text,reply_markup=pay_menu())

async def day_start(m):
    u=db.get(m.from_user.id)
    if not u or int(u['requests'])+int(u['paid_requests'])<=0:
        await answer_user(m, 'У вас осталось 0 запросов.')
        await subscription(m)
        return
    db.set_pending(m.from_user.id,'day','free','Карта дня')
    await answer_user(m, 'Давай посмотрим, что ждет тебя сегодня. Ты можешь сам вытянуть карту из колоды или довериться судьбе❤️',reply_markup=mini_buttons('day','free'))

async def deck_start(m,deck):
    mode='premium' if premium_access(m.from_user.id) else 'free'
    db.set_pending(m.from_user.id,deck,mode,'')
    await answer_user(m, f'Давай погадаем на {DECK_NAMES[deck]}\n\nСформулируй свой вопрос и напиши его полностью ❤️\n\nНапример: Что ждет меня в следующем месяце?')

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
            db.add(referrer,1); db.event(referrer,'referral_success',str(m.from_user.id)); await send_user_message(referrer,'❤️ Вам начислен 1 бесплатный запрос за нового друга!')
    else:
        db.user(m.from_user,existing['source'] or 'telegram',existing['referrer_id'])
    db.event(m.from_user.id,'start',source if not existing else 'return')
    await main_menu(m)

HOROSCOPE_TZ = __import__('os').getenv('HOROSCOPE_TIMEZONE', 'Europe/Moscow')
HOROSCOPE_HOUR = int(__import__('os').getenv('HOROSCOPE_HOUR', '9'))
ZODIAC = [
    ('Козерог', (1,1), (1,19)), ('Водолей',(1,20),(2,18)), ('Рыбы',(2,19),(3,20)),
    ('Овен',(3,21),(4,19)), ('Телец',(4,20),(5,20)), ('Близнецы',(5,21),(6,20)),
    ('Рак',(6,21),(7,22)), ('Лев',(7,23),(8,22)), ('Дева',(8,23),(9,22)),
    ('Весы',(9,23),(10,22)), ('Скорпион',(10,23),(11,21)), ('Стрелец',(11,22),(12,21)),
    ('Козерог',(12,22),(12,31))]
HOROSCOPE_LINES = [
    ('Сегодня полезно замедлиться и выбрать главное. В работе поможет последовательность, а в отношениях — спокойный разговор без ожидания, что другой человек догадается о ваших чувствах. Финансовые решения лучше принимать без спешки.',
     'День подходит для новых идей и небольших шагов к большой цели. Не распыляйтесь: одна завершённая задача принесёт больше удовлетворения, чем несколько начатых. В личном общении проявите инициативу.',
     'Обратите внимание на баланс между желаниями и обязанностями. Возможен разговор, который прояснит ситуацию. Не соглашайтесь из вежливости на то, что вам неудобно. Вечером найдите время для восстановления сил.',
     'Сегодня многое зависит от вашего настроя. Практичный подход поможет решить денежный или рабочий вопрос. В отношениях цените конкретные поступки и не делайте выводов по одному сообщению.'),
    ('Энергия дня располагает к общению и обмену идеями. Полезный совет может прийти от неожиданного человека. Не обещайте больше, чем готовы выполнить, и оставьте немного времени для себя.',
     'Сосредоточьтесь на том, что действительно можете контролировать. Хороший день для порядка в делах, планирования бюджета и завершения старых задач. В чувствах выбирайте ясность вместо намёков.',
     'Не торопите события: некоторым решениям нужно созреть. Если возникнет напряжение, сделайте паузу и вернитесь к разговору позже. Маленькая забота о себе сегодня окажется особенно своевременной.',
     'День может принести шанс укрепить полезную связь или договорённость. Будьте открыты, но проверяйте детали. В финансовых вопросах избегайте импульсивных покупок ради быстрого настроения.'),
    ('Сегодня стоит доверять наблюдательности, но проверять первые впечатления фактами. Хорошее время для обучения и планирования. В отношениях мягкость поможет обсудить даже непростую тему.',
     'Смелая идея заслуживает внимания, если у неё есть понятный следующий шаг. Не ждите идеального момента — начните с малого. В личной жизни проявите интерес к тому, что важно близкому человеку.',
     'День напоминает о ценности устойчивости. Разберите один накопившийся вопрос и не берите на себя чужую ответственность. Возможность сэкономить или разумно распределить ресурсы окажется полезной.',
     'Сегодня лучше действовать спокойно и без сравнения себя с другими. Ваш темп имеет значение. В отношениях честный вопрос даст больше, чем догадки; в работе поможет чёткий список приоритетов.')]

def zodiac_for(birth):
    d=dt_date.fromisoformat(str(birth)); md=(d.month,d.day)
    if md >= (12,22) or md <= (1,19): return 'Козерог'
    ranges=[('Водолей',(1,20),(2,18)),('Рыбы',(2,19),(3,20)),('Овен',(3,21),(4,19)),('Телец',(4,20),(5,20)),('Близнецы',(5,21),(6,20)),('Рак',(6,21),(7,22)),('Лев',(7,23),(8,22)),('Дева',(8,23),(9,22)),('Весы',(9,23),(10,22)),('Скорпион',(10,23),(11,21)),('Стрелец',(11,22),(12,21))]
    for sign,start,end in ranges:
        if start <= md <= end: return sign
    return 'Козерог'

def horoscope_text(birth, day, sky=None):
    sign=zodiac_for(birth)
    signs=['Овен','Телец','Близнецы','Рак','Лев','Дева','Весы','Скорпион','Стрелец','Козерог','Водолей','Рыбы']
    idx=signs.index(sign)
    import hashlib
    seed=int(hashlib.sha256(f'{day}:{sign}'.encode()).hexdigest()[:8],16)
    sky=sky or daily_sky_signature(day)
    # Moon phase selects the main editorial theme; the natal Sun sign rotates
    # the advice, while Mercury's actual speed changes the communication note.
    group=int(sky.get('phase_index',0)) % len(HOROSCOPE_LINES)
    line=HOROSCOPE_LINES[group][(seed+idx+int(bool(sky.get('mercury_retrograde'))))%4]
    moon_element={'Овен':'огненной','Лев':'огненной','Стрелец':'огненной','Телец':'земной','Дева':'земной','Козерог':'земной','Близнецы':'воздушной','Весы':'воздушной','Водолей':'воздушной','Рак':'водной','Скорпион':'водной','Рыбы':'водной'}.get(sky.get('moon_sign'),'')
    phase_note={0:'Начало лунного цикла поддерживает намерения и планирование.',1:'Растущая Луна помогает постепенно развивать начатое.',2:'Первая четверть подталкивает перейти от планов к действиям.',3:'Прибывающая Луна помогает укреплять выбранное направление.',4:'Полнолуние усиливает эмоции: не торопитесь с выводами.',5:'Убывающая Луна подходит для завершения и освобождения от лишнего.',6:'Последняя четверть помогает пересмотреть привычки и приоритеты.',7:'Период перед новым циклом подходит для отдыха и подведения итогов.'}.get(int(sky.get('phase_index',0))%8,'')
    moon_note=f' Луна в {moon_element} стихии ({sky.get("moon_sign","")}) задаёт тон чувствам и реакциям.' if moon_element else ''
    mercury_note=' Меркурий ретрограден: перепроверяйте договорённости, даты и сообщения.' if sky.get('mercury_retrograde') else ''
    emoji={'Овен':'♈️','Телец':'♉️','Близнецы':'♊️','Рак':'♋️','Лев':'♌️','Дева':'♍️','Весы':'♎️','Скорпион':'♏️','Стрелец':'♐️','Козерог':'♑️','Водолей':'♒️','Рыбы':'♓️'}.get(sign,'✨')
    result=f'{emoji} {sign} · {day.strftime("%d.%m.%Y")}\n{line} {phase_note}{moon_note}{mercury_note}'
    return result[:500]

@router.message(Command('onhoroscope'))
async def on_horoscope(m):
    if not db.get(m.from_user.id): db.user(m.from_user)
    sub=db.horoscope_subscriber(m.from_user.id)
    if sub and sub['birth_date']:
        db.horoscope_toggle(m.from_user.id,True)
        db.event(m.from_user.id,'horoscope_enabled','existing_birthday')
        await answer_user(m,'🌙 Ежедневный гороскоп включён! Буду присылать его каждый день. Отключить можно командой /offhoroscope.')
        return
    db.set_horoscope_pending(m.from_user.id)
    db.set_pending(m.from_user.id,'horoscope_birth','', '')
    await answer_user(m,'🌙 Чтобы подобрать ваш знак зодиака, напишите дату рождения в формате ДД.ММ.ГГГГ. После этого ежедневный гороскоп будет включён. Команда /offhoroscope отключает рассылку.')

@router.message(Command('offhoroscope'))
async def off_horoscope(m):
    if not db.get(m.from_user.id): db.user(m.from_user)
    db.horoscope_toggle(m.from_user.id,False)
    pending=db.get_pending(m.from_user.id)
    if pending and pending['deck']=='horoscope_birth': db.clear_pending(m.from_user.id)
    db.event(m.from_user.id,'horoscope_disabled','user_command')
    await answer_user(m,'Рассылка гороскопов отключена. Если захотите вернуться, используйте /onhoroscope ❤️')

async def horoscope_dispatch_loop():
    while True:
        try:
            tz=ZoneInfo(HOROSCOPE_TZ)
            local=dt_datetime.now(tz)
            if local.hour >= HOROSCOPE_HOUR:
                today=local.date()
                sky=daily_sky_signature(today)
                for row in db.horoscope_recipients():
                    sub=db.horoscope_subscriber(row['user_id'])
                    if not sub or sub['last_sent_date']==today.isoformat(): continue
                    try:
                        await send_user_message(int(row['user_id']),horoscope_text(row['birth_date'],today,sky))
                        db.horoscope_mark_sent(row['user_id'],today.isoformat())
                        db.event(row['user_id'],'horoscope_sent',today.isoformat())
                    except Exception as exc:
                        print(f'[HOROSCOPE] send failed uid={row["user_id"]}: {type(exc).__name__}: {exc}',flush=True)
                    await asyncio.sleep(0.06)
        except Exception as exc:
            print(f'[HOROSCOPE] scheduler error: {type(exc).__name__}: {exc}',flush=True)
        await asyncio.sleep(60)

@router.message(Command('friend'))
async def friend(m): await friend_show(m)
async def friend_show(m):
    await answer_user(m, 'Создавай ссылку для своих друзей и делись ею! За каждого приведенного друга дарим тебе 1 бесплатный запрос ❤️ Действуй 🔮',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Создать ссылку',callback_data='ref:create')]]))

@router.message(Command('pay'))
async def pay_cmd(m): await subscription(m)
@router.message(Command('magic'))
async def magic(m): await deck_start(m,'waite')
@router.message(Command('manara'))
async def manara(m): await deck_start(m,'manara')
@router.message(Command('day'))
async def day_cmd(m): await day_start(m)
@router.message(Command('transits'))
async def transits_cmd(m): await transit_start(m)

@router.callback_query(F.data.startswith('deck:'))
async def deck_cb(c):
    await c.answer()
    uid=c.from_user.id
    deck=c.data.split(':',1)[1]
    if deck not in ('waite','manara'):
        return
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
    await c.message.answer(
        'Давай посмотрим, что ждет тебя сегодня. Ты можешь сам вытянуть карту из колоды или довериться судьбе❤️',
        reply_markup=mini_buttons('day','free')
    )

@router.callback_query(F.data=='transits')
async def transits_cb(c):
    await c.answer()
    await transit_start(c.message, c.from_user.id)

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
    if p['deck']=='horoscope_birth':
        raw=(m.text or '').strip()
        parsed=None
        for fmt in ('%d.%m.%Y','%Y-%m-%d','%d/%m/%Y'):
            try: parsed=dt_datetime.strptime(raw,fmt).date(); break
            except ValueError: pass
        if not parsed or parsed > dt_date.today() or parsed.year < 1900:
            await answer_user(m,'Не удалось распознать дату. Введите её в формате ДД.ММ.ГГГГ, например 14.05.1995.'); return
        db.save_horoscope_birthday(m.from_user.id,parsed.isoformat())
        db.clear_pending(m.from_user.id)
        db.event(m.from_user.id,'horoscope_enabled',zodiac_for(parsed.isoformat()))
        await answer_user(m,f'✨ Готово! Ваш знак — {zodiac_for(parsed.isoformat())}. Ежедневный гороскоп включён. Первое сообщение придёт в {HOROSCOPE_HOUR:02d}:00 ({HOROSCOPE_TZ}).')
        return
    if p['deck']=='payment':
        import re
        email=m.text.strip()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email): await answer_user(m, 'Пожалуйста, введи корректную почту.'); return
        await create_payment(m,int(p['mode']),email); db.clear_pending(m.from_user.id); return
    # question
    u=db.get(m.from_user.id); total=int(u['requests'])+int(u['paid_requests'])
    if total<=0:
        await answer_user(m, 'У вас осталось 0 запросов.')
        await subscription(m); return
    mode='premium' if premium_access(m.from_user.id) else 'free'
    deck=p['deck']; db.set_pending(m.from_user.id,deck,mode,m.text)
    db.event(m.from_user.id,'question',f'{deck}|{m.text[:500]}')
    await send_admin_question(m,deck,m.text)
    if deck=='day':
        db.set_pending(m.from_user.id,'day','free',m.text)
        await answer_user(m, 'Давай посмотрим, что ждет тебя сегодня. Ты можешь сам вытянуть карту из колоды или довериться судьбе❤️',reply_markup=mini_buttons('day','free'))
    else:
        await answer_user(m, 'Твой вопрос услышан. Сейчас карты покажут то, что важно увидеть именно тебе. Ты можешь сам вытянуть карты из колоды или довериться судьбе✨',reply_markup=mini_buttons(deck,mode))

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
        await answer_user(m, 'Оплата пока не настроена: проверьте YOOKASSA_SECRET_KEY и PUBLIC_BASE_URL в .env.'); return
    from yookassa import Configuration, Payment
    Configuration.account_id=config.YOOKASSA_SHOP_ID; Configuration.secret_key=config.YOOKASSA_SECRET_KEY
    idem=secrets.token_hex(16); amount=config.PACKAGES[n]
    # User ID in return_url lets the success page immediately reconcile the latest
    # pending payment even when YooKassa webhook delivery is delayed or misconfigured.
    return_url=f'{config.PUBLIC_BASE_URL}/payment/success?uid={m.from_user.id}'
    payment=Payment.create({
      'amount':{'value':f'{amount:.2f}','currency':'RUB'},
      'capture':True,
      'confirmation':{'type':'redirect','return_url':return_url},
      'description':'Оплата подписки Лилит',
      'receipt':{'customer':{'email':email},'items':[{'description':'Оплата подписки Лилит','quantity':'1.00','amount':{'value':f'{amount:.2f}','currency':'RUB'},'vat_code':1,'payment_mode':'full_payment','payment_subject':'service'}]},
      'metadata':{'user_id':str(m.from_user.id),'requests':str(n),'email':email}
    },idem)
    db.payment(m.from_user.id,payment.id,amount,n,'pending',email); db.event(m.from_user.id,'payment_created',str(payment.id))
    print(f'[PAYMENT] CREATED uid={m.from_user.id} payment_id={payment.id} amount={amount} requests={n}', flush=True)
    await answer_user(m, f'Перейдите к оплате: {payment.confirmation.confirmation_url}')

async def _payment_find(payment_id):
    from yookassa import Configuration, Payment
    Configuration.account_id=config.YOOKASSA_SHOP_ID; Configuration.secret_key=config.YOOKASSA_SECRET_KEY
    return await asyncio.to_thread(Payment.find_one, payment_id)

def _obj_value(obj,key,default=None):
    if isinstance(obj,dict): return obj.get(key,default)
    return getattr(obj,key,default)

async def _settle_yookassa_payment(payment_obj):
    pid=str(_obj_value(payment_obj,'id','') or '')
    status=str(_obj_value(payment_obj,'status','') or '')
    if not pid or status!='succeeded':
        return False, None
    meta=_obj_value(payment_obj,'metadata',{}) or {}
    if not isinstance(meta,dict):
        try: meta=dict(meta)
        except Exception: meta={}
    local=db.payment_status(pid)
    uid=int(meta.get('user_id') or (local['user_id'] if local else 0) or 0)
    n=int(meta.get('requests') or (local['requests'] if local else 0) or 0)
    amount_value=_obj_value(_obj_value(payment_obj,'amount',{}) or {},'value',None)
    if amount_value is None:
        amount_value=local['amount'] if local else 0
    amount=int(round(float(amount_value or 0)))
    email=str(meta.get('email') or (local['email'] if local else '') or '')
    if not uid or n not in config.PACKAGES:
        print(f'[PAYMENT] INVALID pid={pid} uid={uid} requests={n}', flush=True)
        return False, None
    added,row=db.complete_payment(pid,uid,amount,n,email)
    if added:
        print(f'[PAYMENT] CREDITED uid={uid} payment_id={pid} requests={n} amount={amount}', flush=True)
        try:
            if config.ADMIN_CHAT_ID:
                u=db.get(uid); username=f'@{u["username"]}' if u and u['username'] else '—'
                await bot.send_message(config.ADMIN_CHAT_ID, f'🔥 КЛИЕНТ ОПЛАТИЛ 🔥\n\n🕯️ Имя: {u["name"] if u else uid}\n🕯️ Ник: {username}\n🕯️ Сумма: {amount} рублей\n🕯️ Запросы: {n}')
            await send_user_message(uid,f'Оплата прошла успешно ❤️\nВам доступно {n} новых запросов.')
        except Exception as e:
            print(f'[PAYMENT] notification error uid={uid}: {type(e).__name__}: {e}', flush=True)
    return added,row

async def _reconcile_pending_payments_once(user_id=None):
    try:
        rows=db.pending_payments(20,user_id)
    except Exception as e:
        print(f'[PAYMENT] DB pending error: {type(e).__name__}: {e}', flush=True); return 0
    credited=0
    for row in rows:
        pid=str(row['payment_id'])
        try:
            obj=await _payment_find(pid)
            added,_=await _settle_yookassa_payment(obj)
            credited += int(bool(added))
        except Exception as e:
            print(f'[PAYMENT] reconcile error payment_id={pid}: {type(e).__name__}: {e}', flush=True)
    return credited

async def _yookassa_reconcile_loop():
    # Fallback for stores where webhook delivery is delayed or not configured.
    await asyncio.sleep(5)
    while True:
        await _reconcile_pending_payments_once()
        await asyncio.sleep(20)

app=FastAPI(title='Lilit Taro')
app.mount('/cards',StaticFiles(directory=str(BASE)),name='cards')

@app.get('/health')
async def health(): return {'ok':True,'service':'lilit-taro'}

@app.get('/miniapp',response_class=HTMLResponse)
async def miniapp():
    return FileResponse(
        BASE/'web'/'index.html',
        headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'}
    )

@app.get('/transits',response_class=HTMLResponse)
async def transits_miniapp():
    return FileResponse(
        BASE/'web'/'transits.html',
        headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0'}
    )

async def _geocode_city(query: str, limit: int = 5):
    global NOMINATIM_LAST
    q=str(query or '').strip()
    if len(q) < 2:
        return []
    async with NOMINATIM_LOCK:
        loop=asyncio.get_running_loop()
        wait=1.05-(loop.time()-NOMINATIM_LAST)
        if wait>0:
            await asyncio.sleep(wait)
        params={'q':q,'format':'jsonv2','limit':str(max(1,min(limit,5))),'addressdetails':'1','accept-language':'ru'}
        headers={'User-Agent':'LilitTaroBot/1.0 (transits mini app)'}
        timeout=aiohttp.ClientTimeout(total=12,connect=8,sock_connect=8,sock_read=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout,headers=headers) as session:
                async with session.get('https://nominatim.openstreetmap.org/search',params=params) as resp:
                    NOMINATIM_LAST=loop.time()
                    if resp.status>=400:
                        raise RuntimeError(f'geocoder HTTP {resp.status}')
                    data=await resp.json(content_type=None)
        except Exception as exc:
            print(f'[GEOCODE] error: {type(exc).__name__}: {exc}',flush=True)
            return []
    out=[]
    for item in data if isinstance(data,list) else []:
        try:
            out.append({
                'display_name':str(item.get('display_name') or q),
                'lat':float(item['lat']),
                'lon':float(item['lon']),
            })
        except Exception:
            continue
    return out

@app.get('/api/transits/cities')
async def transit_cities(q:str=''):
    return {'cities':await _geocode_city(q,5)}

def _validate_transit_payload(body):
    try:
        birth_date=dt_date.fromisoformat(str(body.get('birth_date','')).strip())
    except Exception as exc:
        raise HTTPException(400,'Некорректная дата рождения') from exc
    try:
        transit_date=dt_date.fromisoformat(str(body.get('transit_date','')).strip())
    except Exception as exc:
        raise HTTPException(400,'Некорректная дата транзита') from exc
    if not (1900 <= birth_date.year <= 2200 and 1900 <= transit_date.year <= 2200):
        raise HTTPException(400,'Дата должна быть в диапазоне 1900–2200')
    raw_time=str(body.get('birth_time') or '').strip()
    time_known=bool(body.get('time_known',bool(raw_time)))
    birth_time=None
    if time_known:
        try:
            birth_time=dt_time.fromisoformat(raw_time)
        except Exception as exc:
            raise HTTPException(400,'Некорректное время рождения') from exc
    city=str(body.get('city') or '').strip()
    if len(city)<2:
        raise HTTPException(400,'Укажите город рождения')
    try:
        lat=float(body.get('lat')); lon=float(body.get('lon'))
    except Exception as exc:
        raise HTTPException(400,'Выберите город из списка') from exc
    if not (-90<=lat<=90 and -180<=lon<=180):
        raise HTTPException(400,'Некорректные координаты города')
    try:
        from timezonefinder import timezone_at
        tz_name=timezone_at(lng=lon,lat=lat)
    except Exception as exc:
        raise HTTPException(500,'Не удалось определить часовой пояс города') from exc
    if not tz_name:
        raise HTTPException(400,'Не удалось определить часовой пояс города')
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(400,'Неизвестный часовой пояс города') from exc
    return birth_date,birth_time,time_known,transit_date,city,lat,lon,tz_name

@app.get('/api/transits/profile')
async def transit_profile_api(request:Request):
    tg=validate_init_data(request.query_params.get('initData',''))
    if not tg: raise HTTPException(403,'Недействительный Telegram initData')
    uid=int(tg['id'])
    row=db.transit_profile(uid)
    if not row: return {'profile':None}
    return {'profile':{
        'birth_date':row['birth_date'],'birth_time':row['birth_time'] or '',
        'time_known':bool(row['time_known']),'city':row['city'],'lat':float(row['latitude']),
        'lon':float(row['longitude']),'timezone':row['timezone']
    }}

@app.post('/api/transits/preview')
async def transit_preview_api(request:Request):
    body=await request.json()
    tg=validate_init_data(body.get('initData',''))
    if not tg: raise HTTPException(403,'Недействительный Telegram initData')
    uid=int(tg['id'])
    if not db.get(uid): raise HTTPException(404,'Пользователь не найден')
    birth_date,birth_time,time_known,transit_date,city,lat,lon,tz_name=_validate_transit_payload(body)
    try:
        calc=calculate_transits(birth_date,birth_time,transit_date,lat,lon,tz_name,city)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except Exception as exc:
        print(f'[TRANSITS] PREVIEW ERROR uid={uid}: {type(exc).__name__}: {exc}',flush=True)
        raise HTTPException(500,'Не удалось рассчитать аспекты') from exc
    aspects=[]
    for a in calc.get('aspects',[]):
        aspects.append({
            'transit_planet':a['transit_planet'],
            'aspect':a['aspect'],
            'natal_planet':a['natal_planet'],
            'orb_text':a['orb_text'],
            'state':a['state'],
            'house':a.get('house'),
            'transit_sign':a.get('transit_sign'),
            'transit_position':a.get('transit_position'),
            'transit_retrograde':bool(a.get('transit_retrograde')),
        })
    return {
        'ok':True,
        'transit_date':calc['transit_date'],
        'city':calc['city'],
        'time_known':bool(calc['time_known']),
        'ascendant_sign':calc.get('ascendant_sign'),
        'aspects':aspects,
    }



REPORT_DIR = BASE / 'generated_reports'

def _report_path(uid: int, kind: str, suffix: str = 'pdf') -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(6)
    safe_kind = re.sub(r'[^a-zA-Z0-9_-]+', '_', str(kind)).strip('_') or 'report'
    return REPORT_DIR / f'{safe_kind}_{uid}_{token}.{suffix}'

async def _send_pdf_report(uid: int, pdf_path: Path, caption: str, answer: str) -> None:
    # Keep the full answer in the admin dialogue/history without sending it
    # as a plain Telegram message to the client.
    try:
        db.log_message(int(uid), 'bot', answer, 'pdf')
    except Exception as exc:
        print(f'[PDF] dialogue log error uid={uid}: {type(exc).__name__}: {exc}', flush=True)
    await bot.send_document(int(uid), FSInputFile(pdf_path), caption=caption)

async def _run_transit(uid, payload, calc):
    try:
        # Транзиты бесплатные: запросы пользователя не списываются.
        db.event(uid,'transit_calculated',f"{calc['transit_date']}|{calc['city']}")
        print(f'[TRANSITS] START uid={uid} date={calc["transit_date"]} city={calc["city"]}',flush=True)
        await send_user_message(uid,'Загружаем Вашу натальную карту, делаем расчет...\n\nПожалуйста, подождите, мы готовим Ваш персональный прогноз на выбранную дату 🌌')
        answer=build_transit_interpretation(calc)
        db.event(uid,'transit_local_interpretation','deterministic')
        db.save_transit_reading(
            uid,calc['transit_date'],calc['city'],json.dumps(payload,ensure_ascii=False),
            json.dumps(calc,ensure_ascii=False),answer
        )
        pdf_path=_report_path(uid,'transits')
        try:
            build_transit_pdf(pdf_path, answer, calc)
            await _send_pdf_report(
                uid, pdf_path,
                'Ваш персональный прогноз по транзитам готов 🌌\n\nПолный разбор - в PDF-файле.',
                answer
            )
        finally:
            pdf_path.unlink(missing_ok=True)
        user_now=db.get(uid)
        left=(int(user_now['requests'])+int(user_now['paid_requests'])) if user_now else 0
        await send_user_message(uid,f'Ваше количество запросов: {left}\n\nЕсли хочешь посмотреть другую дату — снова открой «Транзиты» 🌌')
        print(f'[TRANSITS] DONE uid={uid} date={calc["transit_date"]}',flush=True)
    except Exception as e:
        print(f'[TRANSITS] ERROR uid={uid}: {type(e).__name__}: {e}',flush=True)
        try:
            await send_user_message(uid,'Не удалось завершить расчёт транзитов. Попробуй ещё раз немного позже.')
        except Exception as inner:
            print(f'[TRANSITS] RECOVERY ERROR uid={uid}: {type(inner).__name__}: {inner}',flush=True)


@app.post('/api/transits/calculate')
async def transit_calculate_api(request:Request):
    body=await request.json()
    tg=validate_init_data(body.get('initData',''))
    if not tg: raise HTTPException(403,'Недействительный Telegram initData')
    uid=int(tg['id'])
    if not db.get(uid): raise HTTPException(404,'Пользователь не найден')
    birth_date,birth_time,time_known,transit_date,city,lat,lon,tz_name=_validate_transit_payload(body)
    try:
        calc=calculate_transits(birth_date,birth_time,transit_date,lat,lon,tz_name,city)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except Exception as exc:
        print(f'[TRANSITS] CALC ERROR uid={uid}: {type(exc).__name__}: {exc}',flush=True)
        raise HTTPException(500,'Не удалось рассчитать транзиты') from exc
    db.save_transit_profile(uid,birth_date.isoformat(),birth_time.strftime('%H:%M') if birth_time else None,time_known,city,lat,lon,tz_name)
    payload={
        'birth_date':birth_date.isoformat(),'birth_time':birth_time.strftime('%H:%M') if birth_time else '',
        'time_known':time_known,'transit_date':transit_date.isoformat(),'city':city,'lat':lat,'lon':lon,'timezone':tz_name
    }
    # Calculation is deterministic and completes locally; the Mini App is released immediately after validation.
    task=asyncio.create_task(_run_transit(uid,payload,calc)); TRANSIT_TASKS.add(task); task.add_done_callback(TRANSIT_TASKS.discard)
    return {'ok':True,'accepted':True,'message':'Расчёт запущен'}

def _validate_relation_person(person, label):
    if not isinstance(person, dict):
        raise HTTPException(400, f'Не заполнены данные: {label}')
    name=str(person.get('name') or '').strip()
    try:
        birth_date=dt_date.fromisoformat(str(person.get('birth_date','')).strip())
    except Exception as exc:
        raise HTTPException(400, f'Некорректная дата рождения: {label}') from exc
    if not 1900 <= birth_date.year <= 2200:
        raise HTTPException(400, f'Дата рождения должна быть в диапазоне 1900–2200: {label}')
    raw_time=str(person.get('birth_time') or '').strip()
    time_known=bool(person.get('time_known',bool(raw_time)))
    birth_time=None
    if time_known:
        try: birth_time=dt_time.fromisoformat(raw_time)
        except Exception as exc: raise HTTPException(400, f'Некорректное время рождения: {label}') from exc
    city=str(person.get('city') or '').strip()
    if len(city)<2: raise HTTPException(400, f'Укажите город рождения: {label}')
    try: lat=float(person.get('lat')); lon=float(person.get('lon'))
    except Exception as exc: raise HTTPException(400, f'Выберите город из найденных вариантов: {label}') from exc
    if not (-90<=lat<=90 and -180<=lon<=180): raise HTTPException(400, f'Некорректные координаты города: {label}')
    try:
        from timezonefinder import timezone_at
        tz_name=timezone_at(lng=lon,lat=lat)
    except Exception as exc:
        raise HTTPException(500, 'Не удалось определить часовой пояс города') from exc
    if not tz_name: raise HTTPException(400, f'Не удалось определить часовой пояс города: {label}')
    try: ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc: raise HTTPException(400, f'Неизвестный часовой пояс города: {label}') from exc
    return {'name':name,'birth_date':birth_date,'birth_time':birth_time,'time_known':time_known,'city':city,'lat':lat,'lon':lon,'timezone':tz_name}

def _relation_payload_from_body(body):
    return _validate_relation_person(body.get('person1'),'человек 1'), _validate_relation_person(body.get('person2'),'человек 2')

def _relation_input_json(p1,p2,transit_date=None):
    def clean(p):
        return {'name':p['name'],'birth_date':p['birth_date'].isoformat(),'birth_time':p['birth_time'].strftime('%H:%M') if p['birth_time'] else '', 'time_known':bool(p['time_known']),'city':p['city'],'lat':p['lat'],'lon':p['lon'],'timezone':p['timezone']}
    result={'person1':clean(p1),'person2':clean(p2)}
    if transit_date is not None: result['transit_date']=transit_date.isoformat()
    return result

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
            prefix={22:'ж',36:'м',50:'п',64:'ч'}[22+14*((i-22)//14)]
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
        user_data=json.loads(data.get('user','{}'))
        if user_data.get('id'):
            try: db.touch(int(user_data['id']))
            except Exception: pass
        return user_data
    except Exception: return None

def _track_reading_task(task):
    READING_TASKS.add(task)
    task.add_done_callback(READING_TASKS.discard)


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
        await send_user_message(uid,answer)
        await send_user_message(uid,f'Ваше количество запросов: {left}\n\nЗадайте свой вопрос ❤️')
        print(f'[READING] DONE uid={uid} left={left}', flush=True)
    except Exception as e:
        print(f'[READING] ERROR uid={uid}: {type(e).__name__}: {e}', flush=True)
        try:
            db.add(uid,1)
            db.clear_pending(uid)
            await send_user_message(uid,'Не удалось получить расшифровку прямо сейчас. Запрос возвращён на баланс. Попробуйте ещё раз немного позже.')
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
        if deck not in ('waite','manara','day'):
            raise HTTPException(400,'Неизвестная колода')
        mode='premium' if (premium_access(uid) and deck!='day') else 'free'
        expected=1 if deck=='day' else (9 if mode=='premium' else 3)
        if not isinstance(cards,list) or len(cards)!=expected:
            raise HTTPException(400,'Неверное количество карт')
        # IMPORTANT: the client sends card IDs that came from /api/miniapp/config.
        # The server uses the IDs as the source of truth and derives the names
        # from the canonical deck list. The client-provided names are ignored
        # for the reading itself, preventing a name/image mismatch.
        if not isinstance(cards,list) or any(not isinstance(x,dict) for x in cards):
            raise HTTPException(400,'Неверный формат выбранных карт')
        source=WAITE if deck in ('waite','day') else MANARA
        ids=[]
        for x in cards:
            raw_id=x.get('id')
            if isinstance(raw_id,bool):
                raise HTTPException(400,'Недопустимый ID карты')
            try:
                card_id=int(raw_id)
            except (TypeError,ValueError):
                raise HTTPException(400,'Недопустимый ID карты')
            if card_id < 0 or card_id >= len(source):
                raise HTTPException(400,'Недопустимый ID карты')
            ids.append(card_id)
        if len(set(ids))!=len(ids):
            raise HTTPException(400,'Нельзя выбрать одну карту дважды')
        names=[source[i] for i in ids]
        premium=(mode=='premium' and deck!='day')
        if not consume_request(uid,premium=premium):
            raise HTTPException(409,'Нет доступных запросов')
        print(f'[MINI] ACCEPT uid={uid} deck={deck} mode={mode} card_ids={ids!r} canonical_cards={names!r}', flush=True)
        task=asyncio.create_task(process_reading(uid,deck,mode,[{'id':i,'name':n} for i,n in zip(ids,names)],question,premium))
        _track_reading_task(task)
        try:
            await send_user_message(uid,'Отправляем ваш запрос во Вселенную... Подождите...')
        except Exception as e:
            print(f'[MINI] status message error uid={uid}: {type(e).__name__}: {e}', flush=True)
        return {'ok':True,'accepted':True}
    except HTTPException:
        raise
    except Exception as e:
        print(f'[MINI] ERROR: {type(e).__name__}: {e}', flush=True)
        raise HTTPException(500,'Ошибка обработки расклада')

@app.post('/api/miniapp/fate')
async def mini_fate(request:Request):
    try:
        body=await request.json()
        tg=validate_init_data(body.get('initData',''))
        if not tg: raise HTTPException(403,'Недействительный Telegram initData')
        uid=int(tg['id'])
        user=db.get(uid)
        if not user: raise HTTPException(404,'Пользователь не найден')
        deck=body.get('deck')
        question=db.get_pending(uid)
        if not question or question['deck']!=deck or not question['question']:
            raise HTTPException(409,'Вопрос не найден')
        if deck not in ('waite','manara','day'):
            raise HTTPException(400,'Неизвестная колода')
        mode='premium' if (premium_access(uid) and deck!='day') else 'free'
        expected=1 if deck=='day' else (9 if mode=='premium' else 3)
        source=WAITE if deck in ('waite','day') else MANARA
        available=[{'id':i,'name':name,'image':card_image(deck,i,name)} for i,name in enumerate(source)]
        available=[x for x in available if x['image']]
        if len(available) < expected:
            raise HTTPException(500,'Недостаточно доступных карт')
        chosen=secrets.SystemRandom().sample(available,expected)
        # The selected IDs and canonical names are generated server-side.
        names=[source[int(x['id'])] for x in chosen]
        premium=(mode=='premium' and deck!='day')
        if not consume_request(uid,premium=premium):
            raise HTTPException(409,'Нет доступных запросов')
        print(f'[FATE] ACCEPT uid={uid} deck={deck} mode={mode} cards={names!r}',flush=True)
        task=asyncio.create_task(process_reading(uid,deck,mode,[{'name':n} for n in names],question,premium))
        _track_reading_task(task)
        try:
            await send_user_message(uid,'Судьба выбрала карты ✨ Отправляем ваш запрос во Вселенную...')
        except Exception as e:
            print(f'[FATE] status message error uid={uid}: {type(e).__name__}: {e}', flush=True)
        return {'ok':True,'accepted':True,'mode':mode,'cards':chosen}
    except HTTPException:
        raise
    except Exception as e:
        print(f'[FATE] ERROR: {type(e).__name__}: {e}',flush=True)
        raise HTTPException(500,'Ошибка выбора карт судьбой')

@app.post('/yookassa/webhook')
async def yookassa_webhook(request:Request):
    body=await request.json(); event=body.get('event','')
    if event!='payment.succeeded': return {'ok':True}
    obj=body.get('object',{})
    try:
        added,_=await _settle_yookassa_payment(obj)
        return {'ok':True,'credited':bool(added)}
    except Exception as e:
        print(f'[PAYMENT] webhook error: {type(e).__name__}: {e}', flush=True)
        raise HTTPException(500,'Ошибка обработки платежа')

@app.get('/payment/success',response_class=HTMLResponse)
async def payment_success(uid:int=0):
    credited=0
    if uid:
        credited=await _reconcile_pending_payments_once(uid)
    if credited:
        text='<h2>Оплата подтверждена ❤️</h2><p>Запросы уже начислены. Вернитесь в Telegram.</p>'
    else:
        text='<h2>Спасибо за оплату ❤️</h2><p>Проверяем платеж. Вернитесь в Telegram — запросы появятся автоматически после подтверждения.</p>'
    return '<html><meta charset="utf-8"><body style="font-family:Arial;text-align:center;padding:40px">'+text+'</body></html>'

def auth_ok(request:Request):
    a=request.headers.get('authorization','')
    if not a.startswith('Basic '): return False
    import base64
    try: raw=base64.b64decode(a[6:]).decode(); u,p=raw.split(':',1); return secrets.compare_digest(u,config.ADMIN_USERNAME) and secrets.compare_digest(p,config.ADMIN_PASSWORD)
    except: return False

def admin_page(search=''):
    s=db.stats(); us=db.users(search=search); tops=db.top_payers(); src=db.source_stats(); reads=db.recent_readings(); pays=db.recent_payments()
    with db.conn() as c:
        f={k:c.execute(q).fetchone()['n'] for k,q in {
          'visitors':'SELECT COUNT(*) n FROM users',
          'engaged':"SELECT COUNT(DISTINCT user_id) n FROM events WHERE event IN ('question','reading_completed')",
          'checkout':"SELECT COUNT(DISTINCT user_id) n FROM events WHERE event='payment_created'",
          'buyers':"SELECT COUNT(DISTINCT user_id) n FROM events WHERE event='payment_succeeded'",
          'pending':"SELECT COUNT(*) n FROM payments WHERE status='pending'",
          'failed':"SELECT COUNT(*) n FROM payments WHERE status IN ('canceled','failed')",
          'no_action':"SELECT COUNT(*) n FROM users u WHERE NOT EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.id AND e.event IN ('question','payment_created'))",
          'no_balance':'SELECT COUNT(*) n FROM users WHERE requests+paid_requests=0',
          'no_question':"SELECT COUNT(*) n FROM users u WHERE NOT EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.id AND e.event='question')",
          'question_no_checkout':"SELECT COUNT(*) n FROM users u WHERE EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.id AND e.event='question') AND NOT EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.id AND e.event='payment_created')",
          'checkout_no_sale':"SELECT COUNT(*) n FROM users u WHERE EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.id AND e.event='payment_created') AND NOT EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.id AND e.event='payment_succeeded')",
          'repeat_buyers':"SELECT COUNT(*) n FROM (SELECT user_id FROM payments WHERE status='succeeded' GROUP BY user_id HAVING COUNT(*)>1)",
          'avg_check':"SELECT COALESCE(AVG(amount),0) n FROM payments WHERE status='succeeded'"}.items()}
    pct=lambda x,y: round(x*100/y,1) if y else 0
    rows=''.join('<tr><td>{}</td><td><a href="/admin/user/{}">{}</a></td><td>@{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><a href="/admin/user/{}">Открыть</a></td></tr>'.format(u['id'],u['id'],html.escape(u['name'] or 'Без имени'),html.escape(u['username'] or '—'),int(u['requests'])+int(u['paid_requests']),u['requests'],u['paid_requests'],'ВКЛ' if has_manual_subscription(u['id']) else '—',html.escape(u['source'] or 'telegram'),html.escape((u['last_seen'] or '')[:16].replace('T',' ')),u['id']) for u in us)
    sources=''.join('<tr><td>{}</td><td>{}</td><td>{}</td><td>{} ₽</td></tr>'.format(html.escape(x['source']),x['n'],x['buyers'],x['revenue']) for x in src)
    top=''.join('<tr><td>{}</td><td>@{}</td><td>{} ₽</td></tr>'.format(html.escape(x['name'] or ''),html.escape(x['username'] or '—'),x['total_spent']) for x in tops)
    rrows=''.join('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(html.escape((r['created_at'] or '')[:16].replace('T',' ')),html.escape(r['name'] or str(r['user_id'])),html.escape(DECK_NAMES.get(r['deck'],r['deck'])),html.escape((r['question'] or '')[:120])) for r in reads)
    prows=''.join('<tr><td>{}</td><td>{}</td><td>{} ₽</td><td>{}</td><td>{}</td></tr>'.format(html.escape((p['created_at'] or '')[:16].replace('T',' ')),html.escape(p['name'] or str(p['user_id'])),p['amount'],p['requests'],html.escape(p['status'] or '')) for p in pays)
    steps=[('Новые клиенты',f['visitors'],f['visitors']),('Проявили интерес',f['engaged'],f['visitors']),('Начали оплату',f['checkout'],f['engaged']),('Купили',f['buyers'],f['checkout'])]
    funnel=''.join('<div class="funnelrow"><span>{}</span><div><b>{}</b><div class="bar"><i style="width:{}%"></i></div></div><span>{}%</span></div>'.format(label,val,pct(val,f['visitors']),pct(val,prev)) for label,val,prev in steps)
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#090b11"><title>Lilit · кабинет</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#090b11;color:#eee9e3;font:14px Arial,sans-serif}}.wrap{{max-width:1280px;margin:auto;padding:30px 24px}}h1,h2{{font-family:Georgia,serif;font-weight:500}}h1{{font-size:34px;margin:8px 0}}h2{{font-size:21px;margin:0 0 18px}}.eyebrow{{color:#a97860;letter-spacing:3px;font-size:9px;text-transform:uppercase}}.muted{{color:#85858c;line-height:1.6}}section,.stat{{background:#191d27;border:1px solid #292d37;padding:20px;margin:18px 0}}.stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}.stat{{margin:0;padding:16px}}.num{{font:26px Georgia;color:#e0b39a;margin-top:9px}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}input,select,textarea,button{{font:inherit;padding:12px;background:#0d1017;color:#eee;border:1px solid #38343a}}button{{background:#3a2926;border-color:#9a6a56;color:#eac8b4;cursor:pointer}}textarea{{width:100%;min-height:110px}}form.inline{{display:flex;gap:8px;flex-wrap:wrap}}.search{{display:flex;gap:8px;margin:12px 0}}.search input{{flex:1}}table{{width:100%;border-collapse:collapse;min-width:850px}}td,th{{padding:11px 9px;border-bottom:1px solid #30313a;text-align:left;white-space:nowrap}}th{{color:#b88a73;font-size:10px;text-transform:uppercase;letter-spacing:1px}}a{{color:#e1b69e;text-decoration:none}}.scroll{{overflow:auto}}.bar{{height:7px;background:#30323a;margin:8px 0 14px}}.bar i{{display:block;height:100%;background:#a97860}}.funnelrow{{display:grid;grid-template-columns:160px 1fr 90px;gap:12px;align-items:center;margin:13px 0}}.pill{{display:inline-block;border:1px solid #59443d;padding:8px 12px;margin:4px;color:#d6b19d}}label{{display:block;color:#aaa;font-size:12px;margin:10px 0 7px}}@media(max-width:800px){{.wrap{{padding:18px 12px}}.stats{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}h1{{font-size:27px}}section{{padding:15px}}.funnelrow{{grid-template-columns:110px 1fr 65px;font-size:12px}}}}
</style></head><body><main class="wrap"><div class="eyebrow">Lilit · private control room</div><h1>Личный кабинет бота</h1><p class="muted">Клиенты, коммуникации, платежи и аналитика в одном месте</p>
<div class="stats"><div class="stat">Клиенты<div class="num">{s['users']}</div></div><div class="stat">Активные 7 дней<div class="num">{s['active']}</div></div><div class="stat">Расклады<div class="num">{s['questions']}</div></div><div class="stat">Успешные оплаты<div class="num">{s['payments']}</div></div><div class="stat">Выручка<div class="num">{s['revenue']} ₽</div></div></div>
<section><div class="eyebrow">Sales analytics</div><h2>Воронка продаж</h2><p class="muted">Уникальные клиенты по этапам. Конверсия справа — от предыдущего этапа.</p>{funnel}<div class="grid2"><p class="muted">Ожидают оплаты: <b>{f['pending']}</b><br>Отменены / неуспешны: <b>{f['failed']}</b></p><p class="muted">Не сделали целевого действия: <b>{f['no_action']}</b><br>Нулевой баланс: <b>{f['no_balance']}</b></p><p class="muted">Средний чек: <b>{f['avg_check']:.0f} ₽</b><br>Повторные покупатели: <b>{f['repeat_buyers']}</b></p></div><p class="muted">Где теряются клиенты: без вопросов — {f['no_question']}; задавали вопрос, но не начинали оплату — {f['question_no_checkout']}; начали оплату, но покупка не подтверждена — {f['checkout_no_sale']}. Последняя группа требует проверки платежей и напоминания, вторая — оффера/цены, первая — онбординга и источника трафика. Это диагностика этапа, а не доказанная личная причина отказа: её можно узнать только из ответа клиента.</p></section>
<div class="grid2"><section><h2>Начисление запросов</h2><form class="inline" method="post" action="/admin/add-requests"><input name="uid" placeholder="Telegram ID" required><input name="amount" type="number" min="1" placeholder="Количество" required><button>Начислить</button></form><hr style="border-color:#34333a;margin:18px 0"><form class="inline" method="post" action="/admin/add-requests-all" onsubmit="return confirm('Начислить всем?')"><input name="amount" type="number" min="1" value="1"><button>Начислить всем</button></form></section>
<section><h2>Открыть / закрыть подписку</h2><p class="muted">Включает или отключает ручной доступ к режиму 9 карт.</p><form class="inline" method="post" action="/admin/set-subscription"><input name="uid" placeholder="Telegram ID" required><button name="enabled" value="1">Открыть</button><button name="enabled" value="0">Закрыть</button></form></section></div>
<section><h2>Рассылка</h2><form method="post" action="/admin/broadcast" onsubmit="return confirm('Отправить рассылку?')"><div class="grid2"><div><label>Сегмент</label><select name="segment"><option value="all">Все клиенты</option><option value="selected">Выбранные ID</option><option value="sambot">Sambot</option><option value="with_requests">Есть запросы</option><option value="subscribed">Подписка / платные запросы</option><option value="active_7d">Активные 7 дней</option><option value="no_readings">Ещё не делали расклад</option><option value="horoscope">Подписаны на гороскоп</option></select></div><div><label>Telegram ID для выбранных</label><input name="ids" placeholder="ID через запятую" style="width:100%"></div></div><label>Текст сообщения</label><textarea name="text" maxlength="4096" required placeholder="Текст рассылки..."></textarea><p><button>Запустить рассылку</button></p></form></section>
<section><h2>Все клиенты ({len(us)})</h2><form class="search" method="get" action="/admin"><input name="q" value="{html.escape(search,quote=True)}" placeholder="Поиск по имени, @username или Telegram ID"><button>Найти</button><a href="/admin" style="padding:12px">Сбросить</a></form><div class="scroll"><table><tr><th>ID</th><th>Имя</th><th>Username</th><th>Баланс</th><th>Бесплатные</th><th>Платные</th><th>Подписка</th><th>Источник</th><th>Последняя активность</th><th></th></tr>{rows or '<tr><td colspan="10">Клиенты не найдены</td></tr>'}</table></div></section>
<div class="grid2"><section><h2>Источники и продажи</h2><div class="scroll"><table><tr><th>Источник</th><th>Клиенты</th><th>Покупатели</th><th>Выручка</th></tr>{sources}</table></div></section><section><h2>Топ покупателей</h2><div class="scroll"><table><tr><th>Имя</th><th>Ник</th><th>Потрачено</th></tr>{top}</table></div></section></div>
<section><h2>Последние расклады</h2><div class="scroll"><table><tr><th>Дата</th><th>Клиент</th><th>Колода</th><th>Вопрос</th></tr>{rrows}</table></div></section><section><h2>Последние платежи</h2><div class="scroll"><table><tr><th>Дата</th><th>Клиент</th><th>Сумма</th><th>Запросы</th><th>Статус</th></tr>{prows}</table></div></section></main></body></html>'''

@app.get('/admin/user/{uid}',response_class=HTMLResponse)
async def admin_user(request:Request, uid:int):
    if not auth_ok(request):
        return HTMLResponse('Авторизация требуется',401,headers={'WWW-Authenticate':'Basic realm="Lilit Admin"'})
    u=db.get(uid)
    if not u:
        raise HTTPException(404,'Пользователь не найден')
    messages=db.user_messages(uid)
    readings=db.user_readings(uid)
    payments=db.user_payments(uid)
    events=db.user_events(uid)
    transit_readings=db.user_transit_readings(uid)
    total=int(u['requests'])+int(u['paid_requests'])
    name=html.escape(u['name'] or str(uid))
    username='@'+html.escape(u['username']) if u['username'] else '—'
    manual='ВКЛ' if has_manual_subscription(uid) else '—'

    chat_rows=[]
    for msg in messages:
        cls='user' if msg['role']=='user' else 'bot'
        who='Клиент' if msg['role']=='user' else 'Лилит'
        dt=html.escape((msg['created_at'] or '')[:19].replace('T',' '))
        body=html.escape(msg['text'] or '')
        chat_rows.append(f'<div class="msg {cls}"><div class="meta"><b>{who}</b> · {dt}</div><div class="bubble">{body}</div></div>')
    chat_html=''.join(chat_rows) if chat_rows else '<p class="muted">Сообщений пока нет. Полный журнал начнёт заполняться после установки этой версии.</p>'

    reading_rows=[]
    for r in readings:
        dt=html.escape((r['created_at'] or '')[:19].replace('T',' '))
        deck=html.escape(DECK_NAMES.get(r['deck'],r['deck']))
        q=html.escape(r['question'] or '')
        cards=html.escape(r['cards'] or '')
        ans=html.escape(r['answer'] or '')
        reading_rows.append(f'<div class="reading"><div class="meta"><b>{deck}</b> · {dt}</div><div><b>Вопрос:</b> {q}</div><div><b>Карты:</b> {cards}</div><div><b>Ответ:</b><div class="answer">{ans}</div></div></div>')
    readings_html=''.join(reading_rows) if reading_rows else '<p class="muted">Сохранённых раскладов нет.</p>'

    transit_rows=[]
    for tr in transit_readings:
        dt=html.escape((tr['created_at'] or '')[:19].replace('T',' '))
        td=html.escape(tr['transit_date'] or '')
        city=html.escape(tr['city'] or '')
        ans=html.escape(tr['answer'] or '')
        transit_rows.append(f'<div class="reading"><div class="meta"><b>Транзиты</b> · {td} · {city} · {dt}</div><div class="answer">{ans}</div></div>')
    transit_html=''.join(transit_rows) if transit_rows else '<p class="muted">Расчётов транзитов пока нет.</p>'



    pay_rows=[]
    for p in payments:
        dt=html.escape((p['created_at'] or '')[:19].replace('T',' '))
        pay_rows.append(f'<tr><td>{dt}</td><td>{p["amount"]} ₽</td><td>{p["requests"]}</td><td>{html.escape(p["status"] or "")}</td></tr>')
    payments_html=''.join(pay_rows) if pay_rows else '<tr><td colspan="4">Платежей нет.</td></tr>'

    event_rows=[]
    for ev in events[:200]:
        dt=html.escape((ev['created_at'] or '')[:19].replace('T',' '))
        event_rows.append(f'<tr><td>{dt}</td><td>{html.escape(ev["event"] or "")}</td><td>{html.escape(ev["meta"] or "")}</td></tr>')
    events_html=''.join(event_rows) if event_rows else '<tr><td colspan="3">Событий нет.</td></tr>'

    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#090816"><title>Клиент {uid} · Lilit Admin</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#090816;color:#f5e9c8;font:14px Arial,sans-serif;-webkit-text-size-adjust:100%}}.wrap{{max-width:1100px;margin:auto;padding:24px}}a{{color:#d7bb73}}.back{{display:inline-block;margin-bottom:18px;min-height:42px;padding-top:10px}}.hero{{background:#15132a;border:1px solid #302a52;border-radius:16px;padding:20px;box-shadow:0 10px 30px #0003}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}}.stat{{background:#0d0c1c;border:1px solid #292440;border-radius:12px;padding:12px}}.muted{{color:#aaa2bc;line-height:1.5}}section{{background:#15132a;border:1px solid #302a52;border-radius:16px;padding:18px;margin-top:18px;box-shadow:0 10px 30px #0003}}h1,h2{{font-weight:500}}.dialogue{{display:flex;flex-direction:column;gap:10px}}.msg{{max-width:82%}}.msg.user{{align-self:flex-end}}.msg.bot{{align-self:flex-start}}.meta{{font-size:12px;color:#aaa2bc;margin-bottom:4px}}.bubble{{white-space:pre-wrap;line-height:1.45;border-radius:14px;padding:12px 14px}}.msg.user .bubble{{background:#2b2446}}.msg.bot .bubble{{background:#211d38}}.reading{{border:1px solid #302a52;border-radius:14px;padding:14px;margin-top:10px}}.answer{{white-space:pre-wrap;line-height:1.5;margin-top:8px;background:#0d0c1c;border-radius:10px;padding:12px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:9px;border-bottom:1px solid #292440;text-align:left;vertical-align:top}}@media(max-width:800px){{.wrap{{padding:16px 12px 24px}}.hero,section{{border-radius:13px;padding:15px}}.grid{{grid-template-columns:repeat(2,1fr);gap:8px}}.msg{{max-width:94%}}.reading{{padding:12px}}.answer{{padding:10px}}table{{min-width:0}}}}@media(max-width:520px){{h1{{font-size:22px;line-height:1.2}}h2{{font-size:18px}}.stat{{padding:10px;font-size:13px}}.hero p{{word-break:break-word}}.bubble{{padding:10px 11px}}}} </style></head><body><div class="wrap">
<a class="back" href="/admin">← Вернуться в дашборд</a>
<div class="hero"><h1>{name}</h1><p>{username} · Telegram ID: <b>{uid}</b></p><div class="grid"><div class="stat">Всего запросов<br><b>{total}</b></div><div class="stat">Бесплатные<br><b>{int(u["requests"])}</b></div><div class="stat">Оплаченные<br><b>{int(u["paid_requests"])}</b></div><div class="stat">Ручная подписка<br><b>{manual}</b></div></div><p class="muted">Источник: {html.escape(u["source"] or "telegram")} · Первый вход: {html.escape((u["first_seen"] or "")[:19].replace("T"," "))} · Последний вход: {html.escape((u["last_seen"] or "")[:19].replace("T"," "))}</p></div>
<section><h2>💬 Диалог с ботом</h2><div class="dialogue">{chat_html}</div></section>
<section><h2>🔮 История раскладов</h2><p class="muted">История раскладов сохраняется отдельно и включает записи, сделанные до включения полного журнала сообщений.</p>{readings_html}</section>
<section><h2>🌌 Транзиты</h2>{transit_html}</section>
<section><h2>💳 Платежи</h2><table><tr><th>Дата</th><th>Сумма</th><th>Запросов</th><th>Статус</th></tr>{payments_html}</table></section>
<section><h2>⚙️ События</h2><table><tr><th>Дата</th><th>Событие</th><th>Данные</th></tr>{events_html}</table></section>
</div></body></html>'''

@app.get('/admin',response_class=HTMLResponse)
async def admin(request:Request):
    if not auth_ok(request): return HTMLResponse('Авторизация требуется',401,headers={'WWW-Authenticate':'Basic realm="Lilit Admin"'})
    return admin_page(str(request.query_params.get('q','')).strip())

@app.post('/admin/add-requests')
async def admin_add(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    form=await request.form(); uid=int(form['uid']); amount=int(form['amount']);
    if not db.get(uid): raise HTTPException(404,'Пользователь не найден')
    db.add(uid,amount); db.event(uid,'admin_add',str(amount)); return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin">')

@app.post('/admin/add-requests-all')
async def admin_add_all(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    form=await request.form()
    raw_amount=str(form.get('amount','')).strip()
    if not raw_amount.isdigit() or int(raw_amount) < 1:
        raise HTTPException(400,'Количество запросов должно быть целым числом не меньше 1')
    amount=int(raw_amount)
    with db.conn() as c:
        ids=[int(r['id']) for r in c.execute('SELECT id FROM users ORDER BY id').fetchall()]
        c.execute('UPDATE users SET requests=requests+?',(amount,))
        for uid in ids:
            c.execute('INSERT INTO events(user_id,event,meta,created_at) VALUES(?,?,?,?)',(uid,'admin_add_all',str(amount),db.now()))
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin">')

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

def _broadcast_targets(segment, raw_ids=''):
    segment=(segment or 'all').strip()
    if segment=='selected':
        parts=re.split(r'[\s,;]+',raw_ids.strip())
        ids=[]
        for part in parts:
            if part:
                if not part.isdigit():
                    raise ValueError('Telegram ID должен содержать только цифры')
                ids.append(int(part))
        ids=list(dict.fromkeys(ids))
        if not ids:
            raise ValueError('Укажите хотя бы один Telegram ID')
        placeholders=','.join('?' for _ in ids)
        with db.conn() as c:
            rows=c.execute(f'SELECT id FROM users WHERE id IN ({placeholders})',ids).fetchall()
        existing={int(r['id']) for r in rows}
        missing=[str(x) for x in ids if x not in existing]
        if missing:
            raise ValueError('Пользователи не найдены: '+', '.join(missing[:20]))
        return ids
    queries={
        'all':'SELECT id FROM users ORDER BY id',
        'sambot':"SELECT id FROM users WHERE COALESCE(source,'telegram')='sambot' ORDER BY id",
        'with_requests':'SELECT id FROM users WHERE requests>0 OR paid_requests>0 ORDER BY id',
        'subscribed':"SELECT u.id FROM users u WHERE u.paid_requests>0 OR EXISTS (SELECT 1 FROM manual_subscriptions ms WHERE ms.user_id=u.id AND ms.enabled=1) ORDER BY u.id",
        'active_7d':"SELECT id FROM users WHERE julianday(last_seen)>=julianday('now','-7 days') ORDER BY id",
        'no_readings':"SELECT u.id FROM users u WHERE NOT EXISTS (SELECT 1 FROM readings r WHERE r.user_id=u.id) ORDER BY u.id",
        'horoscope':"SELECT user_id id FROM horoscope_subscribers WHERE enabled=1 AND birth_date IS NOT NULL ORDER BY user_id",
    }
    if segment not in queries:
        raise ValueError('Неизвестная группа пользователей')
    with db.conn() as c:
        return [int(r['id']) for r in c.execute(queries[segment]).fetchall()]

async def _run_broadcast(ids,text_message):
    sent=failed=0
    for uid in ids:
        try:
            await send_user_message(uid,text_message)
            sent+=1
        except Exception as e:
            failed+=1
            print(f'[BROADCAST] Не удалось отправить uid={uid}: {type(e).__name__}: {e}',flush=True)
        await asyncio.sleep(0.08)
    print(f'[BROADCAST] DONE total={len(ids)} sent={sent} failed={failed}',flush=True)

def _track_broadcast_task(task):
    BROADCAST_TASKS.add(task)
    task.add_done_callback(BROADCAST_TASKS.discard)

@app.post('/admin/broadcast')
async def broadcast(request:Request):
    if not auth_ok(request): raise HTTPException(401,'Unauthorized')
    form=await request.form()
    segment=str(form.get('segment','all')).strip()
    raw_ids=str(form.get('ids','')).strip()
    text_message=str(form.get('text','')).strip()
    if not text_message: raise HTTPException(400,'Введите текст сообщения')
    if len(text_message)>4096: raise HTTPException(400,'Сообщение длиннее лимита Telegram: максимум 4096 символов')
    try:
        ids=_broadcast_targets(segment,raw_ids)
    except ValueError as e:
        raise HTTPException(400,str(e))
    if not ids: raise HTTPException(400,'В выбранной группе нет пользователей')
    task=asyncio.create_task(_run_broadcast(ids,text_message))
    _track_broadcast_task(task)
    print(f'[BROADCAST] START segment={segment} recipients={len(ids)}',flush=True)
    return HTMLResponse(
        '<meta charset="utf-8"><meta http-equiv="refresh" content="2;url=/admin">'
        '<body style="font-family:Arial;background:#090816;color:#f5e9c8;padding:40px">'
        f'<h2>Рассылка запущена ❤️</h2><p>Получателей: {len(ids)}</p>'
        '<p>Отправка продолжается в фоне.</p><a href="/admin" style="color:#d7bb73">Вернуться в дашборд</a></body>'
    )


async def main():
    global bot
    db.init()
    if not config.BOT_TOKEN: raise RuntimeError('Заполните BOT_TOKEN в .env')
    bot=Bot(config.BOT_TOKEN)
    dp=Dispatcher(); dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    port=int(__import__('os').getenv('PORT','8000'))
    server=uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=port,log_level='info'))
    payment_task=asyncio.create_task(_yookassa_reconcile_loop())
    horoscope_task=asyncio.create_task(horoscope_dispatch_loop())
    try:
        await asyncio.gather(dp.start_polling(bot), server.serve())
    finally:
        payment_task.cancel()
        horoscope_task.cancel()
        try: await horoscope_task
        except asyncio.CancelledError: pass
        try: await payment_task
        except asyncio.CancelledError: pass
        for task in list(TRANSIT_TASKS):
            task.cancel()
        for task in list(TRANSIT_TASKS):
            try: await task
            except asyncio.CancelledError: pass


if __name__=='__main__': asyncio.run(main())
