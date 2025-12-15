import asyncio
import logging
import os
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from aiogram.client.default import DefaultBotProperties 

# 🔥 НОВИЙ ІМПОРТ ДЛЯ PostgreSQL
import asyncpg
from urllib.parse import urlparse

# === CONFIG ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
CARD = os.getenv("CARD_NUMBER", "4323 3473 8685 7285")
DATABASE_URL = os.getenv("DATABASE_URL") # 🔥 ЧИТАЄМО URL БД ЗІ ЗМІННИХ ОТОЧЕННЯ

PRICE_KK = 40
UNBAN_PRICE = 2500
REF_PERCENT = 0.05

SUPPORT = "https://t.me/liffi1488"
REVIEWS = "https://t.me/RampeVirtsFeedbacks"

# Ініціалізація бота
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Глобальна змінна для пулу з'єднань з БД
db_pool = None 

# === SERVERS === (Ваш повний список залишається)
SERVERS = {
    "1": "RED", "2": "GREEN", "3": "BLUE", "4": "YELLOW", "5": "ORANGE",
    "6": "PURPLE", "7": "LIME", "8": "PINK", "9": "CHERRY", "10": "BLACK",
    "11": "INDIGO", "12": "WHITE", "13": "MAGENTA", "14": "CRIMSON", "15": "GOLD",
    "16": "AZURE", "17": "PLATINUM", "18": "AQUA", "19": "GRAY", "20": "ICE",
    "21": "CHILLI", "22": "CHOCO", "23": "MOSCOW", "24": "SPB", "25": "UFA",
    "26": "SOCHI", "27": "KAZAN", "28": "SAMARA", "29": "ROSTOV", "30": "ANAPA",
    "31": "EKATERINBURG", "32": "KRASNODAR", "33": "ARZAMAS", "34": "NOVOSIBIRSK", "35": "GROZNY",
    "36": "SARATOV", "37": "OMSK", "38": "IRKUTSK", "39": "VOLGOGRAD", "40": "VORONEZH",
    "41": "BELGOROD", "42": "MAKHACHKALA", "43": "VLADIKAVKAZ", "44": "VLADIVOSTOK", "45": "KALININGRAD",
    "46": "CHELYABINSK", "47": "KRASNOYARSK", "48": "CHEBOKSARY", "49": "KHABAROVSK", "50": "PERM",
    "51": "TULA", "52": "RYAZAN", "53": "MURMANSK", "54": "PENZA", "55": "KURSK",
    "56": "ARKHANGELSK", "57": "ORENBURG", "58": "KIROV", "59": "KEMEROVO", "60": "TYUMEN",
    "61": "TOLYATTI", "62": "IVANOVO", "63": "STAVROPOL", "64": "SMOLENSK", "65": "PSKOV",
    "66": "BRYANSK", "67": "OREL", "68": "YAROSLAVL", "69": "BARNAUL", "70": "LIPETSK",
    "71": "ULYANOVSK", "72": "YAKUTSK", "73": "TAMBOV", "74": "BRATSK", "75": "ASTRAKHAN",
    "76": "CHITA", "77": "KOSTROMA", "78": "VLADIMIR", "79": "KALUGA", "80": "N.NOVGOROD",
    "81": "TAGANROG", "82": "VOLOGDA", "83": "TVER", "84": "TOMSK", "85": "IZHEVSK",
    "86": "SURGUT", "87": "PODOLSK", "88": "MAGADAN", "89": "CHEREPOVETS"
}


# === DB INIT FUNCTION ===
async def init_db():
    """Створює пул з'єднань і таблиці в PostgreSQL."""
    global db_pool
    if not DATABASE_URL:
        logging.error("DATABASE_URL не встановлено. Бот не може працювати з постійною БД.")
        # Для локального тестування можна використовувати заглушку, але на Render це помилка
        return

    # Парсимо DATABASE_URL для asyncpg
    url = urlparse(DATABASE_URL)
    
    # Створюємо пул з'єднань
    db_pool = await asyncpg.create_pool(
        user=url.username,
        password=url.password,
        database=url.path[1:],
        host=url.hostname,
        port=url.port,
        min_size=5,
        max_size=10
    )
    
    # Виконуємо запити на створення таблиць
    async with db_pool.acquire() as conn:
        # У PostgreSQL використовується SERIAL замість AUTOINCREMENT
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            ref_id BIGINT,
            refs_count INTEGER DEFAULT 0,
            balance_kk REAL DEFAULT 0
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            type TEXT,
            info TEXT,
            price REAL,
            date TEXT
        )""")

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            discount INTEGER,
            max_uses INTEGER,
            used INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )""")
    
    logging.info("PostgreSQL успішно підключено та ініціалізовано.")

# === FSM ===
class Buy(StatesGroup):
    server = State()
    amount = State()
    promo = State()
    nick = State()
    proof = State()

class Unban(StatesGroup):
    screen = State()
    reason = State()
    property = State()
    proof = State()

# === MENU ===
def menu(name):
    kb = InlineKeyboardBuilder()
    kb.button(text="💸 Купить вирты", callback_data="buy")
    kb.button(text="🛡 Разбан", callback_data="unban")
    kb.button(text="👤 Профиль", callback_data="profile")
    kb.button(text="🤝 Рефералка", callback_data="ref")
    kb.button(text="⭐ Отзывы", url=REVIEWS)
    kb.button(text="👨‍💻 Поддержка", url=SUPPORT)
    kb.adjust(1, 2, 2, 1)
    return f"👋 <b>Привет, {name}!</b>\n💰 Курс: {PRICE_KK} грн = 1 KK", kb.as_markup()

# === HANDLERS (Оновлені під asyncpg) ===

@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await state.clear()
    user_id = m.from_user.id
    ref_id = None
    
    async with db_pool.acquire() as conn:
        # PostgreSQL. fetchval повертає перше значення, якщо рядок знайдено
        existing_user_id = await conn.fetchval("SELECT id FROM users WHERE id=$1", user_id)
        
        if not existing_user_id:
            # Ловимо рефералку
            args = m.text.split()
            if len(args) > 1 and "ref_" in args[1]:
                try:
                    candidate = int(args[1].split("ref_")[1])
                    if candidate != user_id:
                        ref_id = candidate
                        # Оновлюємо лічильник у запросившого
                        await conn.execute("UPDATE users SET refs_count=refs_count+1 WHERE id=$1", ref_id)
                except: pass
            
            # Вставляємо нового користувача
            await conn.execute("INSERT INTO users(id, ref_id) VALUES($1, $2)", user_id, ref_id)

    text, kb = menu(m.from_user.first_name)
    await m.answer(text, reply_markup=kb)

# --- ПОКУПКА ---
@dp.callback_query(F.data == "buy")
async def buy_start(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardBuilder()
    for k, v in SERVERS.items():
        kb.button(text=f"{v} [{k}]", callback_data=f"srv_{k}")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(4) 
    await c.message.edit_text("🌍 <b>Выберите сервер:</b>", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("srv_"))
async def srv_chosen(c: types.CallbackQuery, state: FSMContext):
    srv_id = c.data.split("_")[1]
    await state.update_data(server=f"{SERVERS.get(srv_id, 'Unknown')} [{srv_id}]") 
    await state.set_state(Buy.amount)
    await c.message.edit_text("🔢 <b>Введите количество KK (цифрой):</b>")

@dp.message(F.text, Buy.amount)
async def amount_entered(m: types.Message, state: FSMContext):
    try:
        kk = float(m.text)
        if kk < 1: raise ValueError
    except:
        return await m.answer("❌ Введите число больше 1")
    
    await state.update_data(kk=kk, raw_price=kk*PRICE_KK)
    await state.set_state(Buy.promo)
    await m.answer("🎁 <b>Введите промокод</b> или отправьте «-» чтобы пропустить")

@dp.message(F.text, Buy.promo)
async def promo_entered(m: types.Message, state: FSMContext):
    data = await state.get_data()
    price = data['raw_price']
    code = m.text.strip().upper()
    used_promo = None

    if code != "-":
        async with db_pool.acquire() as conn:
            # Використовуємо $1 для плейсхолдера
            res = await conn.fetchrow("SELECT discount, max_uses, used FROM promos WHERE code=$1 AND active=1", code)
            
            if res:
                if res['max_uses'] and res['used'] >= res['max_uses']:
                    await m.answer("❌ Промокод закончился. Цена не изменена.")
                else:
                    disc = res['discount']
                    price = price * (1 - disc/100)
                    used_promo = code
                    await m.answer(f"✅ Скидка {disc}% применена!")
            else:
                await m.answer("❌ Промокод не найден. Цена не изменена.")

    await state.update_data(final_price=round(price, 2), promo_code=used_promo)
    await state.set_state(Buy.nick)
    await m.answer("🎮 <b>Введите ваш Никнейм:</b>")

@dp.message(F.text, Buy.nick)
async def nick_entered(m: types.Message, state: FSMContext):
    await state.update_data(nickname=m.text)
    data = await state.get_data()
    
    msg = (f"🧾 <b>Подтверждение заказа</b>\n"
           f"🌍 Сервер: {data['server']}\n"
           f"👤 Ник: {data['nickname']}\n"
           f"💰 Сумма: {data['kk']} KK\n"
           f"💵 К оплате: <b>{data['final_price']} грн</b>\n\n"
           f"💳 Карта: <code>{CARD}</code>\n"
           f"📸 <b>Пришлите скриншот оплаты</b>")
    
    await state.set_state(Buy.proof)
    await m.answer(msg)

@dp.message(F.photo, Buy.proof)
async def proof_received(m: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = m.from_user.id
    final_price = data['final_price']
    
    async with db_pool.acquire() as conn:
        # 1. Списываем использование промокода (если был)
        if data.get('promo_code'):
            await conn.execute("UPDATE promos SET used=used+1 WHERE code=$1", data['promo_code'])

        # 2. Начисляем бонус рефереру
        ref_id = await conn.fetchval("SELECT ref_id FROM users WHERE id=$1", user_id)
        
        if ref_id:
            reward = (final_price / PRICE_KK) * REF_PERCENT
            await conn.execute("UPDATE users SET balance_kk=balance_kk+$1 WHERE id=$2", reward, ref_id)
            try:
                await bot.send_message(ref_id, f"💸 Ваш реферал сделал заказ! Вам начислено <b>{reward:.2f} KK</b>")
            except: pass

        # 3. Сохраняем заказ
        info_json = json.dumps(data, ensure_ascii=False)
        await conn.execute("""
        INSERT INTO orders(user_id, type, info, price, date)
        VALUES($1, $2, $3, $4, $5)
        """, user_id, "virts", info_json, final_price, datetime.now().strftime("%Y-%m-%d %H:%M"))

    # 4. Уведомляем админа
    if ADMIN_ID:
        admin_msg = (f"🔥 <b>НОВЫЙ ЗАКАЗ!</b>\n"
                     f"👤 Юзер: {m.from_user.full_name} (ID: {user_id})\n"
                     f"🌍 Сервер: {data['server']}\n"
                     f"🎮 Ник: {data['nickname']}\n"
                     f"💰 Сумма: {data['kk']} KK ({final_price} грн)\n"
                     f"🎁 Промо: {data.get('promo_code', 'Нет')}")
        try:
            await bot.send_photo(ADMIN_ID, m.photo[-1].file_id, caption=admin_msg)
        except: pass

    await m.answer("✅ <b>Оплата принята!</b> Ожидайте выдачи.")
    await state.clear()

# --- РАЗБАН (Упрощено) ---
# ... (Тут потрібно оновити хендлери Unban аналогічно, використовуючи async with db_pool.acquire())

@dp.callback_query(F.data == "unban")
async def unban_start(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Unban.screen)
    await c.message.edit_text("📸 <b>Пришлите скриншот окна бана:</b>")

@dp.message(F.photo, Unban.screen)
async def unban_screen(m: types.Message, state: FSMContext):
    await state.update_data(screen_id=m.photo[-1].file_id)
    await state.set_state(Unban.proof)
    msg = (f"🛡 <b>Разбан аккаунта</b>\n"
           f"💵 Стоимость: <b>{UNBAN_PRICE} грн</b>\n"
           f"💳 Карта: <code>{CARD}</code>\n"
           f"📸 Пришлите чек об оплате.")
    await m.answer(msg)

@dp.message(F.photo, Unban.proof)
async def unban_proof(m: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = m.from_user.id
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO orders(user_id, type, info, price, date)
        VALUES($1, $2, $3, $4, $5)
        """, user_id, "unban", "Заявка на разбан", UNBAN_PRICE, datetime.now().strftime("%Y-%m-%d %H:%M"))

    if ADMIN_ID:
        try:
            await bot.send_photo(ADMIN_ID, data['screen_id'], caption="🖼 Скрин бана")
            await bot.send_photo(ADMIN_ID, m.photo[-1].file_id, 
                               caption=f"🛡 <b>ЗАЯВКА НА РАЗБАН</b>\nID: {user_id}\nЧек выше.")
        except: pass

    await m.answer("✅ Заявка принята в работу.")
    await state.clear()


# --- ПРОФИЛЬ / ИНФО ---
@dp.callback_query(F.data == "profile")
async def show_profile(c: types.CallbackQuery):
    user_id = c.from_user.id
    async with db_pool.acquire() as conn:
        # COUNT(*)
        orders_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE user_id=$1", user_id)
    
    msg = f"👤 <b>Ваш профиль</b>\n🆔 ID: <code>{user_id}</code>\n🛒 Заказов: <b>{orders_cnt}</b>"
    kb = InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="back").as_markup()
    await c.message.edit_text(msg, reply_markup=kb)

@dp.callback_query(F.data == "ref")
async def show_ref(c: types.CallbackQuery):
    user_id = c.from_user.id
    async with db_pool.acquire() as conn:
        # Вибираємо refs_count, balance_kk
        res = await conn.fetchrow("SELECT refs_count, balance_kk FROM users WHERE id=$1", user_id)
    
    refs, bal = (res['refs_count'], res['balance_kk']) if res else (0, 0.0)
    
    bot_user = await bot.get_me()
    link = f"https://t.me/{bot_user.username}?start=ref_{user_id}"
    
    msg = (f"🤝 <b>Реферальная система</b>\n"
           f"Приглашай друзей и получай {int(REF_PERCENT*100)}% от их покупок!\n\n"
           f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
           f"👥 Приглашено: {refs}\n"
           f"💰 Твой баланс: <b>{bal:.2f} KK</b>")
    
    kb = InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="back").as_markup()
    await c.message.edit_text(msg, reply_markup=kb)

@dp.callback_query(F.data == "back")
async def back_to_menu(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = menu(c.from_user.first_name)
    await c.message.edit_text(text, reply_markup=kb)

# --- WEB SERVER (Для Render) ---
async def handle(request):
    return web.Response(text="Bot is alive")

async def main():
    # 🔥 ІНІЦІАЛІЗУЄМО БД ПЕРЕД ЗАПУСКОМ БОТА
    await init_db() 

    app = web.Application()
    app.router.add_get('/', handle)
    
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await asyncio.gather(dp.start_polling(bot), site.start())

if __name__ == "__main__":
    asyncio.run(main())
