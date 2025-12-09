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
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiohttp import web 

# --- КОНФИГУРАЦИЯ ---

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')          
# Установите ваш реальный ID администратора
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID', 123456789)) # *** ЗАМЕНИТЕ 123456789 НА ВАШ АДМИН ID ***

ССЫЛКА_ПОДДЕРЖКИ = "https://t.me/liffi1488" 
НОМЕР_КАРТЫ = "4323 3473 6140 0119"      
ССЫЛКА_АККАУНТОВ = "https://t.me/RampeAccounts" 

ЦЕНА_ЗА_1КК = 40                      
ЦЕНА_РАЗБАНА = 2500 
ССЫЛКА_ОТЗЫВОВ = "https://t.me/RampeVirtsFeedbacks"
ФОТО_ПРИВЕТСТВИЯ = None # Замените на 'media_id' вашего фото, если используете

ПРОЦЕНТ_РЕФЕРАЛА = 0.05 

# --- СПИСОК СЕРВЕРОВ ---
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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_clean_server_name(full_name: str) -> str:
    """Извлекает только название сервера без номера в скобках."""
    return full_name.split(' [')[0]

# --- БАЗА ДАННЫХ (DB) ---
def db_start():
    """Инициализация базы данных, создание таблиц 'users', 'orders' и 'promocodes'."""
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            discount_percent INTEGER NOT NULL,
            max_uses INTEGER,
            current_uses INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)
    db.commit()

# --- DB-Функции ---

def add_user(user_id, referrer_id=None):
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
        db.commit()
    
def get_all_users_ids():
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

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

# --- DB-Функции для Промокодов ---
def create_promocode(code: str, discount: int, max_uses: int):
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO promocodes (code, discount_percent, max_uses) 
            VALUES (?, ?, ?)
        """, (code.upper(), discount, max_uses))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Код уже существует

def get_promocode(code: str):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM promocodes WHERE code = ? AND is_active = 1", (code.upper(),))
    result = cursor.fetchone()
    if result:
        # code, discount_percent, max_uses, current_uses, is_active
        return {
            "code": result[0],
            "discount": result[1],
            "max_uses": result[2],
            "current_uses": result[3],
        }
    return None

def use_promocode(code: str):
    cursor = db.cursor()
    cursor.execute("""
        UPDATE promocodes SET current_uses = current_uses + 1 
        WHERE code = ?
    """, (code.upper(),))
    
    # Деактивация, если достигнут лимит
    cursor.execute("""
        UPDATE promocodes SET is_active = 0 
        WHERE code = ? AND max_uses IS NOT NULL AND current_uses >= max_uses
    """, (code.upper(),))
    
    db.commit()

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class BuyState(StatesGroup):
    choosing_server = State()
    entering_amount = State()
    entering_promocode = State()
    entering_nickname = State() 
    waiting_for_proof = State() 

class UnbanState(StatesGroup):
    waiting_for_screenshot = State()
    waiting_for_reason = State()      
    waiting_for_property = State()      
    waiting_for_forum_proof = State()  
    waiting_for_payment = State() 

class AdminState(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_promo_code = State()
    waiting_for_promo_discount = State()
    waiting_for_promo_max_uses = State()

# --- ФУНКЦИИ ГЛАВНОГО МЕНЮ И НАВИГАЦИИ ---

def get_main_menu_content(user_name: str):
    """Генерирует текст и клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Купить вирты", callback_data="start_buy")
    builder.button(text="🛡️ Разбан аккаунта", callback_data="start_unban")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🤝 Рефералка", callback_data="referral_info") 
    builder.button(text="⭐ Отзывы", url=ССЫЛКА_ОТЗЫВОВ)
    builder.button(text="🛍️ Купить аккаунт", url=ССЫЛКА_АККАУНТОВ)
    builder.button(text="📜 Правила / FAQ", callback_data="rules")
    builder.button(text="👨‍💻 Поддержка", url=ССЫЛКА_ПОДДЕРЖКИ)
    
    builder.adjust(1, 1, 2, 2, 2)

    welcome_text = (
        f"👋 <b>Привет, {user_name}!</b>\n\n"
        f"🏰 Лучший магазин валюты Black Russia.\n"
        f"💰 Курс: <b>{ЦЕНА_ЗА_1КК} грн₴</b> за 1кк.\n"
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
        # Попытка отредактировать текущее сообщение
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            
    except TelegramBadRequest:
        # Если редактирование не удалось (например, сообщение слишком старое), 
        # удаляем старое и отправляем новое
        try:
            await callback.message.delete()
        except Exception:
            pass 
            
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=welcome_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    
    await callback.answer()


# --- ХЕНДЛЕРЫ: СТАРТ И ОСНОВНАЯ НАВИГАЦИЯ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    referrer_id = None
    
    # 1. ЛОГИКА РЕФЕРАЛКИ
    if message.text.startswith('/start ref_'):
        try:
            referrer_id = int(message.text.split('_')[1])
            if referrer_id == user_id: 
                referrer_id = None
        except (IndexError, ValueError):
            referrer_id = None
    
    add_user(user_id, referrer_id)
    
    # 2. ОТПРАВКА МЕНЮ
    welcome_text, markup = get_main_menu_content(message.from_user.first_name)

    if ФОТО_ПРИВЕТСТВИЯ:
        try:
            await message.answer_photo(
                photo=ФОТО_ПРИВЕТСТВИЯ,
                caption=welcome_text,
                reply_markup=markup,
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
            
    await message.answer(text=welcome_text, reply_markup=markup, parse_mode="HTML")


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Безопасное возвращение в главное меню."""
    await send_or_edit_start_menu(callback, state)


@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    """Безопасное возвращение в главное меню после отмены."""
    await state.clear() 
    
    try:
        # Пытаемся отредактировать
        await callback.message.edit_text("❌ Покупка отменена. Возвращаемся в главное меню.")
    except TelegramBadRequest:
        # Если не удалось, пробуем отредактировать caption (для фото) или удалить/отправить новое
        try:
            await callback.message.edit_caption("❌ Покупка отменена. Возвращаемся в главное меню.")
        except Exception:
            try:
                await callback.message.delete()
            except Exception:
                pass
        
    # Всегда отправляем новое сообщение меню, если редактирование не удалось
    await send_or_edit_start_menu(callback)


# --- ХЕНДЛЕРЫ: КУПИТЬ ВИРТЫ (С ПРОМОКОДОМ) ---

@dp.callback_query(F.data == "start_buy")
async def show_servers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    
    # Отображаем ВСЕ серверы, используя чистые названия
    for server_id, full_name in SERVERS_MAPPING.items():
        clean_name = get_clean_server_name(full_name) 
        builder.button(text=clean_name, callback_data=f"srv_{server_id}")
    
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(4) 

    try:
        await callback.message.edit_caption(
            caption="🌍 **Выберите ваш сервер:**\n\n"
                    "Для быстрого поиска вы можете начать вводить название сервера текстом.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text="🌍 **Выберите ваш сервер:**\n\n"
                 "Для быстрого поиска вы можете начать вводить название сервера текстом.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    await state.set_state(BuyState.choosing_server)
    await callback.answer()

@dp.callback_query(F.data.startswith("srv_"), BuyState.choosing_server)
async def server_chosen(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split('_')[1]
    server_name = SERVERS_MAPPING.get(server_id, f"Сервер {server_id}")
    await state.update_data(server_id=server_id, server=server_name)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    await callback.message.edit_text(
        f"✅ Выбран сервер: <b>{get_clean_server_name(server_name)}</b>\n\n"
        f"🔢 Введите желаемое количество виртов (в миллионах, например, <b>10</b>):",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BuyState.entering_amount)
    await callback.answer()

@dp.message(F.text, BuyState.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount_kk = float(message.text)
        if amount_kk <= 0 or amount_kk < 1:
            await message.answer("❌ Минимальная сумма покупки - 1 KK. Введите положительное число.")
            return

        price = round(amount_kk * ЦЕНА_ЗА_1КК, 2)
        await state.update_data(amount=amount_kk, price_initial=price)

        builder = InlineKeyboardBuilder()
        builder.button(text="Ввести промокод", callback_data="enter_promocode")
        builder.button(text="Пропустить", callback_data="skip_promocode")
        builder.adjust(2)
        
        await message.answer(
            f"✅ Выбрано: <b>{amount_kk} KK</b>\n"
            f"💰 Итого без скидки: <b>{price} грн</b>\n\n"
            f"У вас есть промокод?",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await state.set_state(BuyState.entering_promocode)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (количество KK), например, <b>15</b>.")

@dp.callback_query(F.data == "enter_promocode", BuyState.entering_promocode)
async def enter_promocode(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎁 **Введите ваш промокод:**", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "skip_promocode", BuyState.entering_promocode)
async def skip_promocode(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    price = data.get('price_initial')
    
    await state.update_data(price=price, promocode_applied=None)

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")

    await callback.message.edit_text(
        f"💰 Итого к оплате: <b>{price} грн</b>\n\n"
        f"✍️ Введите ваш никнейм на сервере:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BuyState.entering_nickname)
    await callback.answer()


@dp.message(F.text, BuyState.entering_promocode)
async def process_promocode(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    promo = get_promocode(code)
    data = await state.get_data()
    price_initial = data.get('price_initial')
    
    if promo:
        discount_percent = promo['discount']
        discount_amount = price_initial * (discount_percent / 100)
        final_price = round(price_initial - discount_amount, 2)
        
        await state.update_data(
            price=final_price, 
            promocode_applied=code, 
            discount_percent=discount_percent
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")

        await message.answer(
            f"✅ Промокод <b>{code}</b> активирован! ({discount_percent}% скидка)\n"
            f"💰 Цена со скидкой: <b>{final_price} грн</b>\n\n"
            f"✍️ Введите ваш никнейм на сервере:",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await state.set_state(BuyState.entering_nickname)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="Пропустить", callback_data="skip_promocode")
        
        await message.answer("❌ Промокод не найден или недействителен. Вы можете пропустить ввод.", reply_markup=builder.as_markup())


@dp.message(F.text, BuyState.entering_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    nickname = message.text.strip()
    if not nickname or len(nickname) < 3:
        await message.answer("❌ Никнейм слишком короткий или пустой.")
        return

    await state.update_data(nickname=nickname)
    data = await state.get_data()

    promocode_info = ""
    if data.get('promocode_applied'):
        promocode_info = f"\n🎁 Промокод: <b>{data.get('promocode_applied')} (-{data.get('discount_percent')}%)</b>"

    order_summary = (
        f"✨ <b>Ваш заказ</b> ✨\n"
        f"🌍 Сервер: <b>{get_clean_server_name(data.get('server'))}</b>\n"
        f"🎮 Никнейм: <b>{nickname}</b>\n"
        f"💰 Сумма: <b>{data.get('amount')} KK</b>"
        f"{promocode_info}\n"
        f"💵 Итого: <b>{data.get('price')} грн</b>\n\n"
        f"Реквизиты для оплаты:\n"
        f"<code>{НОМЕР_КАРТЫ}</code>\n\n"
        f"После оплаты нажмите кнопку <b>'Я оплатил'</b> и отправьте скриншот чека."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data="payment_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)

    await message.answer(order_summary, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(BuyState.waiting_for_proof)

@dp.callback_query(F.data == "payment_confirm", BuyState.waiting_for_proof)
async def payment_confirmed_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📸 <b>Отлично! Теперь ожидаем чек.</b>\n\n"
        "Пожалуйста, **отправьте скриншот или фотографию чека** об оплате в чат.\n"
        "Это нужно для быстрой проверки и выдачи вашего заказа.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo, BuyState.waiting_for_proof)
async def process_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    user_db_data = get_user_data(user.id)
    
    # 1. СОХРАНЕНИЕ ЗАКАЗА В БД И АКТИВАЦИЯ ПРОМОКОДА
    order_details = {
        'server': data.get('server'),
        'nickname': data.get('nickname'),
        'amount_kk': data.get('amount'),
        'proof_photo_id': message.photo[-1].file_id,
        'promocode_applied': data.get('promocode_applied'),
    }
    price = data.get('price')
    order_id = add_order(user.id, 'virts', order_details, price)
    
    if data.get('promocode_applied'):
        use_promocode(data['promocode_applied'])

    # 2. ЛОГИКА РЕФЕРАЛКИ (Только после первого заказа)
    if user_db_data and user_db_data[2] == 1: 
        referrer_id = user_db_data[1]
        purchase_price_uah = price 
        
        if referrer_id and purchase_price_uah > 0:
            reward_uah = purchase_price_uah * ПРОЦЕНТ_РЕФЕРАЛА
            reward_kk = reward_uah / ЦЕНА_ЗА_1КК
            reward_kk_rounded = round(reward_kk, 2)
            
            update_referrer_stats(referrer_id, reward_kk_rounded)
            mark_as_old(user.id)
            
            try:
                await bot.send_message(referrer_id, 
                    f"🎉 <b>ПОЗДРАВЛЯЕМ!</b>\n"
                    f"Ваш друг (<a href='tg://user?id={user.id}'>{user.full_name}</a>) совершил первую покупку на сумму {purchase_price_uah} грн!\n"
                    f"На ваш бонусный счет зачислено <b>{reward_kk_rounded} KK</b>.", 
                    parse_mode="HTML")
            except Exception as e:
                logging.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")
    
    # 3. ФОРМИРОВАНИЕ И ОТПРАВКА АДМИНУ (С КНОПКАМИ)
    promocode_line = f"🎁 Промокод: <b>{data.get('promocode_applied')}</b>\n" if data.get('promocode_applied') else ""
    
    admin_caption = (
        f"🚨 <b>НОВЫЙ ЗАКАЗ # {order_id} (ВИРТЫ)</b>\n"
        f"--------------------------\n"
        f"👤 Покупатель: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username or 'нет юзернейма'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🌍 Сервер: <b>{data.get('server', 'N/A')}</b>\n"
        f"🎮 Ник: <b>{data.get('nickname', 'N/A')}</b>\n"
        f"📦 Сумма виртов: <b>{data.get('amount', 'N/A')} кк</b>\n"
        f"{promocode_line}"
        f"💰 Итоговая цена: <b>{price} грн</b>\n\n"
        f"⚠️ <b>ЧЕК ПРИКРЕПЛЕН ВЫШЕ</b>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выдать", callback_data=f"order_complete_{order_id}")
    builder.button(text="❌ Отмена", callback_data=f"order_cancel_{order_id}")
    builder.adjust(1, 1)

    if ADMIN_ID:
        try:
            await bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=message.photo[-1].file_id, 
                caption=admin_caption, 
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки чека админу {ADMIN_ID}: {e}")

    # 4. ОТВЕТ ПОКУПАТЕЛЮ
    await message.answer(
        "✅ <b>Чек принят!</b>\n\n"
        "Ваша заявка отправлена администратору. Ожидайте, мы проверим оплату и свяжемся с вами для выдачи.",
        parse_mode="HTML"
    )
    
    await state.clear()

@dp.message(F.message_text, BuyState.waiting_for_proof)
async def process_payment_proof_error(message: types.Message):
    await message.answer("❌ Ожидается **фотография** или **скриншот** оплаты, а не текст. Пожалуйста, отправьте его.")


# --- ХЕНДЛЕРЫ: РАЗБАН АККАУНТА ---

# (Оставлены без изменений)
@dp.callback_query(F.data == "start_unban")
async def show_unban_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оформить заявку", callback_data="unban_start_form")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    info_text = (
        "🛡️ <b>Разбан аккаунта</b>\n\n"
        "Вернём доступ к аккаунту и имущество в целости и сохранности.\n\n"
        f"Стоимость: <b>{ЦЕНА_РАЗБАНА} грн</b>\n"
        "Работают профильные специалисты.\n\n"
        "📝 **Что подготовить для заявки:**\n"
        "• Скриншот блокировки\n"
        "• Короткое описание причины бана\n"
        "• Список ценного имущества\n"
        "• (Опционально) Скриншот обращения на форуме/ответ администрации"
    )

    try:
        await callback.message.edit_caption(
            caption=info_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=info_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    await callback.answer()

@dp.callback_query(F.data == "unban_start_form")
async def start_unban_form(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UnbanState.waiting_for_screenshot)
    
    await callback.message.edit_text(
        "📸 **1/4: Скриншот блокировки**\n\n"
        "Пришлите, пожалуйста, **скриншот** или **фотографию** экрана блокировки аккаунта.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo, UnbanState.waiting_for_screenshot)
async def process_unban_screenshot(message: types.Message, state: FSMContext):
    await state.update_data(screenshot_id=message.photo[-1].file_id)
    
    await message.answer(
        "📝 **2/4: Причина бана**\n\n"
        "Кратко опишите ситуацию, которая привела к блокировке аккаунта."
    )
    await state.set_state(UnbanState.waiting_for_reason)

@dp.message(F.text, UnbanState.waiting_for_reason)
async def process_unban_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    
    await message.answer(
        "💎 **3/4: Имущество**\n\n"
        "Перечислите самое ценное имущество на аккаунте (машины, дома, бизнес и т.д.)."
    )
    await state.set_state(UnbanState.waiting_for_property)

@dp.message(F.text, UnbanState.waiting_for_property)
async def process_unban_property(message: types.Message, state: FSMContext):
    await state.update_data(property_list=message.text)
    
    await message.answer(
        "🖼️ **4/4: Дополнительные скрины (Опционально)**\n\n"
        "Если имеется, пришлите скриншот обращения на форуме или ответ администрации. Если нет, **просто напишите '-'.**"
    )
    await state.set_state(UnbanState.waiting_for_forum_proof)

@dp.message(UnbanState.waiting_for_forum_proof)
async def process_unban_forum_proof(message: types.Message, state: FSMContext):
    forum_proof = message.photo[-1].file_id if message.photo else message.text
    await state.update_data(forum_proof=forum_proof)
    
    payment_text = (
        f"✅ <b>Заявка сформирована!</b>\n\n"
        f"Стоимость: <b>{ЦЕНА_РАЗБАНА} грн</b>\n"
        f"Реквизиты для оплаты:\n"
        f"<code>{НОМЕР_КАРТЫ}</code>\n\n"
        f"**После оплаты отправьте скриншот платежа сюда** — мы приступим к делу и свяжемся для уточнения деталей."
    )
    
    await message.answer(payment_text, parse_mode="HTML")
    await state.set_state(UnbanState.waiting_for_payment)

@dp.message(F.photo, UnbanState.waiting_for_payment)
async def process_unban_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    
    order_details = {
        'reason': data.get('reason'),
        'property_list': data.get('property_list'),
        'forum_proof': data.get('forum_proof'),
        'screenshot_id': data.get('screenshot_id'),
        'payment_proof_id': message.photo[-1].file_id
    }
    order_id = add_order(user.id, 'unban', order_details, ЦЕНА_РАЗБАНА)
    
    admin_caption = (
        f"🚨 <b>НОВАЯ ЗАЯВКА # {order_id} (РАЗБАН)</b>\n"
        f"--------------------------\n"
        f"👤 Клиент: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username or 'нет юзернейма'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Ожидаемый приход: <b>{ЦЕНА_РАЗБАНА} грн</b>\n\n"
        f"**ДАННЫЕ ЗАЯВКИ:**\n"
        f"• **Причина бана:** {data.get('reason', 'N/A')}\n"
        f"• **Имущество:** {data.get('property_list', 'N/A')}\n"
        f"• **Форум/Админ:** {'Чек прикреплен' if isinstance(data.get('forum_proof'), str) and data.get('forum_proof') != '-' else 'Нет/Текст'}\n"
        f"⚠️ **ЧЕК ОПЛАТЫ ПРИКРЕПЛЕН ВЫШЕ**"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено", callback_data=f"order_complete_{order_id}")
    builder.button(text="❌ Отмена", callback_data=f"order_cancel_{order_id}")
    builder.adjust(1, 1)

    if ADMIN_ID:
        try:
            await bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=data['screenshot_id'], 
                caption="🖼️ СКРИН БЛОКИРОВКИ",
            )
            await bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=message.photo[-1].file_id, 
                caption=admin_caption, 
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки чека разбана админу {ADMIN_ID}: {e}")

    await message.answer(
        "✅ <b>Скриншот оплаты получен!</b>\n\n"
        "Мы немедленно приступаем к работе по разбану вашего аккаунта. Ожидайте, мы свяжемся с вами для уточнения деталей."
    )
    
    await state.clear()

@dp.message(UnbanState.waiting_for_payment)
async def process_unban_payment_proof_error(message: types.Message):
    await message.answer("❌ Ожидается **фотография** или **скриншот** оплаты. Пожалуйста, отправьте его.")


# --- ХЕНДЛЕРЫ: ПРОФИЛЬ, РЕФЕРАЛКА, ПРАВИЛА ---

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    user = callback.from_user
    registration_date = "неизвестна"

    try:
        chat_info = await bot.get_chat(user.id)
        if chat_info.date:
            registration_date = chat_info.date.strftime('%d.%m.%Y')
    except Exception:
        registration_date = "недоступна"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 История заказов", callback_data="order_history")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    caption_text = (
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 Твой ID: <code>{user.id}</code>\n"
        f"👤 Имя: {user.full_name}\n"
        f"📅 Дата регистрации: {registration_date}\n\n"
    )
    
    try:
        await callback.message.edit_caption(
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=caption_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    await callback.answer() 

@dp.callback_query(F.data == "order_history")
async def show_order_history(callback: types.CallbackQuery):
    user_orders = get_user_orders(callback.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    if not user_orders:
        history_text = "📜 <b>История заказов</b>\n\nУ вас пока нет оформленных заказов."
    else:
        history_text = "📜 <b>История заказов</b> (Последние 10):\n\n"
        
        for order in user_orders[:10]:
            order_id, _, order_type, status, details_json, price, created_at = order
            
            details = json.loads(details_json)
            
            status_map = {
                'Pending_Admin': '⏳ Ожидает',
                'Completed': '✅ Выполнен',
                'Cancelled': '❌ Отменен'
            }
            display_status = status_map.get(status, status)
            
            if order_type == 'virts':
                server_name = details.get('server')
                clean_server_name = get_clean_server_name(server_name) if server_name else 'N/A'
                summary = f"💰 {details.get('amount_kk')} KK на {clean_server_name}"
                if details.get('promocode_applied'):
                     summary += f" (Промокод: {details.get('promocode_applied')})"
            else:
                summary = f"🛡️ Разбан аккаунта"

            date_obj = datetime.strptime(created_at.split('.')[0], '%Y-%m-%d %H:%M:%S')
            
            history_text += (
                f"--------------------------\n"
                f"🆔 **Заказ #{order_id}** ({'ВИРТЫ' if order_type == 'virts' else 'РАЗБАН'})\n"
                f"{summary}\n"
                f"💵 Сумма: {price} грн | 📅 {date_obj.strftime('%d.%m.%Y')}\n"
                f"**Статус:** {display_status}\n"
            )
        history_text += "--------------------------"


    try:
        await callback.message.edit_caption(
            caption=history_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=history_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    await callback.answer()

# *** ФИНАЛЬНО ИСПРАВЛЕННЫЙ ХЕНДЛЕР РЕФЕРАЛКИ ***
@dp.callback_query(F.data == "referral_info")
async def referral_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() 

    user_data = get_user_data(callback.from_user.id)
    if not user_data:
        await callback.answer("Ошибка данных пользователя. Попробуйте перезапустить бота командой /start.", show_alert=True)
        return
        
    referrer_id, referrals_count, rewards_kk = user_data[1], user_data[3], user_data[4]
    
    # 1. Формирование контента
    referral_link = f"https://t.me/{callback.bot.username}?start=ref_{callback.from_user.id}"
    
    info_text = (
        "🤝 <b>Реферальная программа</b>\n\n"
        "Приглашайте друзей и получайте бонус!\n"
        "Вы получаете <b>5%</b> от суммы первого заказа каждого приглашенного пользователя (в KK).\n\n"
        f"Ваша реферальная ссылка: \n<code>{referral_link}</code>\n\n"
        f"👥 Приглашено друзей: <b>{referrals_count}</b>\n"
        f"💰 Накоплено бонусов: <b>{rewards_kk:.2f} KK</b>\n"
        f"Ваш реферер: {'Нет' if not referrer_id else str(referrer_id)}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    # 2. Принудительная отправка/редактирование с обработкой ошибок
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=info_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        else:
            await callback.message.edit_text(
                text=info_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            
    except TelegramBadRequest:
        # Если редактирование не удалось, отправляем новое сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass 
            
        await callback.message.answer(
            text=info_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    """Хендлер для кнопки 'Правила / FAQ'."""
    rules_text = (
        "📜 <b>Правила и FAQ</b>\n\n"
        "1. Мы не несем ответственность за баны аккаунта, если вы совершаете покупку виртов.\n"
        "2. Выдача виртов происходит только после 100% предоплаты и проверки чека.\n"
        "3. Разбан аккаунта имеет 99% гарантию.\n"
        "4. Возврат средств возможен только в исключительных случаях (если администратор не смог выдать вирты или разбанить).\n\n"
        "❓ **Часто задаваемые вопросы:**\n"
        "• Как происходит выдача? — Мы заходим на ваш аккаунт и передаем вирты через банк или трейд.\n"
        "• Это безопасно? — Да, мы используем максимально безопасные методы, но риск всегда есть.\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    try:
        await callback.message.edit_caption(
            caption=rules_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=rules_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    await callback.answer()


# --- ХЕНДЛЕРЫ: АДМИН-ПАНЕЛЬ (НОВЫЕ ФУНКЦИИ) ---

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return 
    
    total_users, active_orders, total_referral_rewards = get_admin_stats()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Начать рассылку", callback_data="admin_broadcast_start")
    builder.button(text="🎁 Создать промокод", callback_data="admin_create_promo")
    builder.adjust(1)
    
    stats_text = (
        "👑 <b>АДМИН-ПАНЕЛЬ СТАТИСТИКА</b>\n"
        "-----------------------------------\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🛒 Активных заказов (в ожидании): <b>{active_orders}</b>\n"
        f"🤝 Начислено реф. виртов (KK): <b>{total_referral_rewards:.2f}</b>\n"
        "-----------------------------------"
    )
    
    try:
        # Попытка редактировать, если сообщение пришло из колбека
        await message.edit_text(stats_text, parse_mode="HTML", reply_markup=builder.as_markup())
    except AttributeError:
        # Если это чистая команда /admin
        await message.answer(stats_text, parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        # Если редактирование не удалось
        await message.answer(stats_text, parse_mode="HTML", reply_markup=builder.as_markup())

# --- АДМИН: РАССЫЛКА ---

@dp.callback_query(F.data == "admin_broadcast_start")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.waiting_for_broadcast_content)
    await callback.message.edit_text("📢 **Режим рассылки.**\n\nПришлите сообщение (текст/фото), которое нужно отправить всем пользователям.", parse_mode="HTML")
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast_content)
async def broadcast_send(message: types.Message, state: FSMContext):
    await state.clear()
    
    user_ids = get_all_users_ids()
    sent_count = 0
    blocked_count = 0
    
    await message.answer(f"Начинаю рассылку для {len(user_ids)} пользователей. Это может занять время...")
    
    for user_id in user_ids:
        try:
            if message.text:
                await bot.send_message(user_id, message.text, parse_mode="HTML")
            elif message.photo:
                await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode="HTML")
            
            sent_count += 1
            await asyncio.sleep(0.05)
            
        except TelegramForbiddenError:
            blocked_count += 1
        except TelegramRetryAfter as e:
            logging.warning(f"Flood control: waiting for {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            try:
                if message.text:
                    await bot.send_message(user_id, message.text, parse_mode="HTML")
                elif message.photo:
                    await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption, parse_mode="HTML")
                sent_count += 1
            except Exception:
                blocked_count += 1
        except Exception:
            blocked_count += 1
            
    await message.answer(
        f"✅ **Рассылка завершена.**\n"
        f"Отправлено: <b>{sent_count}</b>\n"
        f"Не доставлено (заблокировали): <b>{blocked_count}</b>",
        parse_mode="HTML"
    )
    # Возвращаем админ-панель после рассылки
    await cmd_admin(message)


# --- АДМИН: СОЗДАНИЕ ПРОМОКОДА ---

@dp.callback_query(F.data == "admin_create_promo")
async def create_promo_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.waiting_for_promo_code)
    await callback.message.edit_text("🎁 **Создание промокода (Шаг 1/3)**\n\nВведите **текст** промокода (например, `SALE2025`):", parse_mode="HTML")
    await callback.answer()

@dp.message(F.text, AdminState.waiting_for_promo_code)
async def create_promo_code(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    if len(code) < 3 or ' ' in code:
        await message.answer("❌ Код слишком короткий или содержит пробелы. Попробуйте еще.")
        return
    
    # Проверка на существование
    if get_promocode(code):
        await message.answer(f"❌ Промокод <b>{code}</b> уже существует. Придумайте другой.", parse_mode="HTML")
        return
        
    await state.update_data(new_promo_code=code)
    await message.answer("🎁 **Создание промокода (Шаг 2/3)**\n\nВведите **размер скидки** в процентах (целое число, например, `15`):")
    await state.set_state(AdminState.waiting_for_promo_discount)

@dp.message(F.text, AdminState.waiting_for_promo_discount)
async def create_promo_discount(message: types.Message, state: FSMContext):
    try:
        discount = int(message.text)
        if not 1 <= discount <= 100:
            raise ValueError
        
        await state.update_data(new_promo_discount=discount)
        await message.answer("🎁 **Создание промокода (Шаг 3/3)**\n\nВведите **максимальное количество использований** (целое число). Напишите `0`, если ограничений нет:")
        await state.set_state(AdminState.waiting_for_promo_max_uses)
    except ValueError:
        await message.answer("❌ Введите целое число от 1 до 100.")

@dp.message(F.text, AdminState.waiting_for_promo_max_uses)
async def create_promo_max_uses(message: types.Message, state: FSMContext):
    try:
        max_uses = int(message.text)
        if max_uses < 0:
            raise ValueError
            
        data = await state.get_data()
        code = data['new_promo_code']
        discount = data['new_promo_discount']
        max_uses_final = None if max_uses == 0 else max_uses
        
        create_promocode(code, discount, max_uses_final)
        
        await message.answer(
            f"✅ **Промокод создан!**\n\n"
            f"Код: <b>{code}</b>\n"
            f"Скидка: <b>{discount}%</b>\n"
            f"Лимит: <b>{'Безлимитный' if max_uses == 0 else str(max_uses)}</b>",
            parse_mode="HTML"
        )
        await state.clear()
        # Возвращаем админ-панель после создания промокода
        await cmd_admin(message)

    except ValueError:
        await message.answer("❌ Введите целое положительное число или 0.")

# --- УСИЛЕНИЕ УСТОЙЧИВОСТИ: CATCH-ALL ХЕНДЛЕРЫ ---

@dp.callback_query()
async def unhandled_callback_query(callback: types.CallbackQuery, state: FSMContext):
    """Ловит любые колбеки, которые не были обработаны."""
    current_state = await state.get_state()
    logging.warning(f"Необработанный колбек: User={callback.from_user.id}, Data='{callback.data}', State={current_state}")
    
    if current_state:
        # Если находились в FSM, сообщаем об ошибке и предлагаем вернуться в меню
        await callback.answer("❌ Произошла ошибка. Отмените текущую операцию.", show_alert=True)
    else:
        # Если находились в главном меню
        await callback.answer("⏳ Не удалось обновить меню. Повторите попытку.")
        # Принудительно отправляем меню
        await send_or_edit_start_menu(callback, state)


@dp.message()
async def unhandled_message(message: types.Message, state: FSMContext):
    """Ловит любые сообщения, которые не были обработаны в текущем FSM-состоянии."""
    current_state = await state.get_state()
    
    if current_state:
        # Если находились в FSM, напоминаем, что ожидается
        await message.answer(
            "❌ <b>Неверный ввод.</b> Ожидается информация для продолжения заявки.\n"
            "Нажмите ❌ Отмена, если хотите вернуться в меню.",
            parse_mode="HTML"
        )
    else:
        # Если находились в главном меню
        welcome_text, markup = get_main_menu_content(message.from_user.first_name)
        await message.answer(
            f"❓ <b>Неизвестная команда.</b> Выберите действие в меню:",
            reply_markup=markup,
            parse_mode="HTML"
        )


# --- ЗАПУСК БОТА ---

async def handle(request):
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
        logging.error("TELEGRAM_BOT_TOKEN не установлен в переменных среды!")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Бот остановлен вручную.")
