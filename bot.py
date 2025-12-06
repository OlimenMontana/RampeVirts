import asyncio
import logging
import sqlite3
import math 
import os 
import json 
from datetime import datetime 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiohttp import web 

# --- КОНФИГУРАЦИЯ ---

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')          
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID')) if os.getenv('TELEGRAM_ADMIN_ID') else None 

SUPPORT_LINK = "https://t.me/liffi1488" 
CARD_NUMBER = "4323 3473 6140 0119"      
ACCOUNTS_CHANNEL_LINK = "https://t.me/RampeAccounts" 

PRICE_PER_1KK = 40                      
UNBAN_PRICE = 2500 
FEEDBACK_LINK = "https://t.me/RampeVirtsFeedbacks"
PHOTO_URL = None 

REFERRAL_BONUS_PERCENTAGE = 0.05 

SERVERS_MAPPING = {
    "1": "RED [1]", "2": "GREEN [2]", "3": "BLUE [3]", "4": "YELLOW [4]", "5": "ORANGE [5]",
    "6": "PURPLE [6]", "7": "LIME [7]", "8": "PINK [8]", "9": "CHERRY [9]", "10": "BLACK [10]", 
    "11": "INDIGO [11]", "12": "WHITE [12]", "13": "MAGENTA [13]", "14": "CRIMSON [14]", "15": "GOLD [15]",
    "16": "AZURE [16]", "17": "PLATINUM [17]", "18": "AQUA [18]", "19": "GRAY [19]", "20": "ICE [20]",
    "21": "CHILLI [21]", "22": "CHOCO [22]", "23": "MOSCOW [23]", "24": "SPB [24]", "25": "UFA [25]",
    "26": "SOCHI [26]", "27": "KAZAN [27]", "28": "SAMARA [28]", "29": "ROSTOV [29]", "30": "ANAPA [30]",
    "31": "EKATERINBURG [31]", "32": "KRASNODAR [32]", "33": "ARZAMAS [33]", "34": "NOVOSIBIRSK [34]",
    "35": "GROZNY [35]", "36": "SARATOV [36]", "37": "OMSK [37]", "38": "IRKUTSK [38]", "39": "VOLGOGRAD [39]",
    "40": "VORONEZH [40]", "41": "BELGOROD [41]", "42": "MAKHACHKALA [42]", "43": "VLADIKAVKAZ [43]",
    "44": "VLADIVOSTOK [44]", "45": "KALININGRAD [45]", "46": "CHELYABINSK [46]", "47": "KRASNOYARSK [47]",
    "48": "CHEBOKSARY [48]", "49": "KHABAROVSK [49]", "50": "PERM [50]", "51": "TULA [51]", "52": "RYAZAN [52]",
    "53": "MURMANSK [53]", "54": "PENZA [54]", "55": "KURSK [55]", "56": "ARKHANGELSK [56]", "57": "ORENBURG [57]",
    "58": "KIROV [58]", "59": "KEMEROVO [59]", "60": "TYUMEN [60]", "61": "TOLYATTI [61]", "62": "IVANOVO [62]",
    "63": "STAVROPOL [63]", "64": "SMOLENSK [64]", "65": "PSKOV [65]", "66": "BRYANSK [66]", "67": "OREL [67]",
    "68": "YAROSLAVL [68]", "69": "BARNAUL [69]", "70": "LIPETSK [70]", "71": "ULYANOVSK [71]", "72": "YAKUTSK [72]",
    "73": "TAMBOV [73]", "74": "BRATSK [74]", "75": "ASTRAKHAN [75]", "76": "CHITA [76]", "77": "KOSTROMA [77]",
    "78": "VLADIMIR [78]", "79": "KALUGA [79]", "80": "N.NOVGOROD [80]", "81": "TAGANROG [81]", "82": "VOLOGDA [82]",
    "83": "TVER [83]", "84": "TOMSK [84]", "85": "IZHEVSK [85]", "86": "SURGUT [86]", "87": "PODOLSK [87]",
    "88": "MAGADAN [88]", "89": "CHEREPOVETS [89]"
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
db = None

# --- БАЗА ДАННЫХ (DB) ---
# ... (db_start, add_user, get_user_data, update_referrer_stats, mark_as_old, add_order, update_order_status, get_user_orders, get_admin_stats остались без изменений) ...

def db_start():
    """Инициализация базы данных, создание таблиц 'users' и 'orders'."""
    global db
    db = sqlite3.connect('virts_shop.db')
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            is_new INTEGER DEFAULT 1,
            referrals_count INTEGER DEFAULT 0,
            referral_rewards_kk REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            type TEXT, 
            status TEXT DEFAULT 'Pending_Admin', 
            details TEXT, 
            price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

def add_user(user_id, referrer_id=None):
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
        db.commit()
    
def get_user_data(user_id):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_referrer_stats(referrer_id, reward_kk):
    cursor = db.cursor()
    cursor.execute("""
        UPDATE users SET referrals_count = referrals_count + 1, 
        referral_rewards_kk = referral_rewards_kk + ? 
        WHERE user_id = ?
    """, (reward_kk, referrer_id))
    db.commit()

def mark_as_old(user_id):
    cursor = db.cursor()
    cursor.execute("UPDATE users SET is_new = 0 WHERE user_id = ?", (user_id,))
    db.commit()

def add_order(user_id: int, order_type: str, details: dict, price: float) -> int:
    cursor = db.cursor()
    details_json = json.dumps(details)
    cursor.execute("""
        INSERT INTO orders (user_id, type, details, price) 
        VALUES (?, ?, ?, ?)
    """, (user_id, order_type, details_json, price))
    db.commit()
    return cursor.lastrowid

def update_order_status(order_id: int, status: str):
    cursor = db.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    db.commit()

def get_user_orders(user_id: int):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    return cursor.fetchall()

def get_admin_stats():
    cursor = db.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending_Admin'")
    active_orders = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(referral_rewards_kk) FROM users")
    total_referral_rewards = cursor.fetchone()[0] or 0.0
    
    return total_users, active_orders, total_referral_rewards

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class BuyState(StatesGroup):
    choosing_server = State()
    entering_amount = State()
    entering_nickname = State() 
    waiting_for_proof = State() 

class UnbanState(StatesGroup):
    waiting_for_screenshot = State()
    waiting_for_reason = State()      
    waiting_for_property = State()      
    waiting_for_forum_proof = State()  
    waiting_for_payment = State() 

# --- НОВЫЕ ФУНКЦИИ ДЛЯ МЕНЮ ---

def get_main_menu_content(user_name: str):
    """Генерирует текст и клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Купить вирты", callback_data="start_buy")
    builder.button(text="🛡️ Разбан аккаунта", callback_data="start_unban")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🤝 Рефералка", callback_data="referral_info") 
    builder.button(text="⭐ Отзывы", url=FEEDBACK_LINK)
    builder.button(text="🛍️ Купить аккаунт", url=ACCOUNTS_CHANNEL_LINK)
    builder.button(text="📜 Правила / FAQ", callback_data="rules")
    builder.button(text="👨‍💻 Поддержка", url=SUPPORT_LINK)
    
    builder.adjust(1, 1, 2, 2, 2)

    welcome_text = (
        f"👋 <b>Привет, {user_name}!</b>\n\n"
        f"🏰 Лучший магазин валюты Black Russia.\n"
        f"💰 Курс: <b>{PRICE_PER_1KK} грн₴</b> за 1кк.\n"
        f"👇 Выбирай, что нужно:"
    )
    return welcome_text, builder.as_markup()

async def send_or_edit_start_menu(callback: types.CallbackQuery, state: FSMContext = None):
    """
    Безопасно возвращает пользователя в главное меню путем редактирования 
    текущего сообщения или отправки нового.
    """
    if state:
        await state.clear()
        
    user_name = callback.from_user.first_name
    welcome_text, markup = get_main_menu_content(user_name)

    try:
        # 1. Попытка отредактировать текущее сообщение (самый чистый способ)
        if callback.message.photo:
            # Если это было фото с подписью
            await callback.message.edit_caption(
                caption=welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            # Если это был обычный текст
            await callback.message.edit_text(
                text=welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            
    except TelegramBadRequest:
        # 2. Если редактирование не удалось (часто из-за смены типа сообщения), 
        # удаляем старое и отправляем новое
        try:
            await callback.message.delete()
        except Exception:
            pass # Если сообщение уже удалено, игнорируем
            
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=welcome_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    await callback.answer()


# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    referrer_id = None
    
    # 1. ПРОВЕРКА РЕФЕРАЛЬНОЙ ССЫЛКИ
    if message.text.startswith('/start ref_'):
        try:
            referrer_id = int(message.text.split('_')[1])
            if referrer_id == user_id: 
                referrer_id = None
        except (IndexError, ValueError):
            referrer_id = None
    
    # 2. ДОБАВЛЕНИЕ/ОБНОВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ
    add_user(user_id, referrer_id)
    
    # 3. ОТПРАВКА МЕНЮ (Используем новую функцию для генерации контента)
    welcome_text, markup = get_main_menu_content(message.from_user.first_name)

    if PHOTO_URL:
        try:
            await message.answer_photo(
                photo=PHOTO_URL,
                caption=welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
            
    await message.answer(text=welcome_text, reply_markup=markup, parse_mode="HTML")

# ... (Все остальные хендлеры покупки виртов, разбана, и админки остались без изменений) ...

# --- ИСПРАВЛЕННЫЕ ХЕНДЛЕРЫ НАЗАД В МЕНЮ ---

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    """ИСПРАВЛЕНО: Безопасное возвращение в главное меню."""
    await send_or_edit_start_menu(callback)


@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    """ИСПРАВЛЕНО: Безопасное возвращение в главное меню после отмены."""
    await state.clear() 
    
    # Вывод сообщения об отмене
    try:
        await callback.message.edit_text("❌ Покупка отменена. Возвращаемся в главное меню.")
    except TelegramBadRequest:
        await callback.message.edit_caption("❌ Покупка отменена. Возвращаемся в главное меню.")
        
    # Возвращение в меню
    await send_or_edit_start_menu(callback)


# --- ЗАПУСК БОТА ---

async def handle(request):
    """Проста відповідь для Health Check Render."""
    return web.Response(text="Bot is running via polling.")

async def main():
    db_start()
    
    app = web.Application()
    app.router.add_get('/', handle)
    
    port = int(os.environ.get('PORT', 8080))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    
    await asyncio.gather(
        dp.start_polling(bot),
        site.start()
    )

if __name__ == "__main__":
    if not API_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN не встановлено у змінних середовищах!")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Бот остановлен вручную.")

