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
# Если переменная не найдена, используется заглушка (замените на свой ID, если тестируете локально)
ADMIN_ID_RAW = os.getenv('TELEGRAM_ADMIN_ID', '0')
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else None

ССЫЛКА_ПОДДЕРЖКИ = "https://t.me/liffi1488" 
НОМЕР_КАРТЫ = "4323 3473 6140 0119"      
ССЫЛКА_АККАУНТОВ = "https://t.me/RampeAccounts" 

ЦЕНА_ЗА_1КК = 40                      
ЦЕНА_РАЗБАНА = 2500 
ССЫЛКА_ОТЗЫВОВ = "https://t.me/RampeVirtsFeedbacks"
ФОТО_ПРИВЕТСТВИЯ = None 

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
        return True
    return False
    
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
        return False 

def get_promocode(code: str):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM promocodes WHERE code = ? AND is_active = 1", (code.upper(),))
    result = cursor.fetchone()
    if result:
        return {"code": result[0], "discount": result[1], "max_uses": result[2], "current_uses": result[3]}
    return None

def use_promocode(code: str):
    cursor = db.cursor()
    cursor.execute("""
        UPDATE promocodes SET current_uses = current_uses + 1 
        WHERE code = ?
    """, (code.upper(),))
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
    if state:
        await state.clear()
        
    user_name = callback.from_user.first_name
    welcome_text, markup = get_main_menu_content(user_name)

    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=welcome_text, reply_markup=markup, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=welcome_text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest:
        try:
            await callback.message.delete()
        except:
            pass
        await bot.send_message(chat_id=callback.from_user.id, text=welcome_text, reply_markup=markup, parse_mode="HTML")
    
    await callback.answer()

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    referrer_id = None
    if message.text.startswith('/start ref_'):
        try:
            referrer_id = int(message.text.split('_')[1])
            if referrer_id == user_id: referrer_id = None
        except (IndexError, ValueError):
            referrer_id = None
    
    add_user(user_id, referrer_id)
    welcome_text, markup = get_main_menu_content(message.from_user.first_name)

    if ФОТО_ПРИВЕТСТВИЯ:
        try:
            await message.answer_photo(photo=ФОТО_ПРИВЕТСТВИЯ, caption=welcome_text, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
            
    await message.answer(text=welcome_text, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await send_or_edit_start_menu(callback, state)

@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    try:
        await callback.message.edit_text("❌ Покупка отменена. Возвращаемся в главное меню.")
    except TelegramBadRequest:
        try:
            await callback.message.edit_caption("❌ Покупка отменена. Возвращаемся в главное меню.")
        except:
            pass
    await send_or_edit_start_menu(callback)

# --- ПОКУПКА ВИРТОВ ---

@dp.callback_query(F.data == "start_buy")
async def show_servers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    for server_id, full_name in SERVERS_MAPPING.items():
        clean_name = get_clean_server_name(full_name) 
        builder.button(text=clean_name, callback_data=f"srv_{server_id}")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(4) 

    text = "🌍 **Выберите ваш сервер:**\n\nДля быстрого поиска вы можете начать вводить название сервера текстом."
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=builder.as_markup())
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
        f"✅ Выбран сервер: <b>{get_clean_server_name(server_name)}</b>\n\n🔢 Введите желаемое количество виртов (в миллионах, например, <b>10</b>):",
        parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await state.set_state(BuyState.entering_amount)
    await callback.answer()

@dp.message(F.text, BuyState.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount_kk = float(message.text)
        if amount_kk < 1:
            await message.answer("❌ Минимальная сумма покупки - 1 KK. Введите положительное число.")
            return
        price = round(amount_kk * ЦЕНА_ЗА_1КК, 2)
        await state.update_data(amount=amount_kk, price_initial=price)
        builder = InlineKeyboardBuilder()
        builder.button(text="Ввести промокод", callback_data="enter_promocode")
        builder.button(text="Пропустить", callback_data="skip_promocode")
        builder.adjust(2)
        await message.answer(f"✅ Выбрано: <b>{amount_kk} KK</b>\n💰 Итого без скидки: <b>{price} грн</b>\n\nУ вас есть промокод?", parse_mode="HTML", reply_markup=builder.as_markup())
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
    await callback.message.edit_text(f"💰 Итого к оплате: <b>{price} грн</b>\n\n✍️ Введите ваш никнейм на сервере:", parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(BuyState.entering_nickname)
    await callback.answer()

@dp.message(F.text, BuyState.entering_promocode)
async def process_promocode(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    promo = get_promocode(code)
    data = await state.get_data()
    price_initial = data.get('price_initial')
    
    if promo:
        discount = promo['discount']
        final_price = round(price_initial - (price_initial * (discount / 100)), 2)
        await state.update_data(price=final_price, promocode_applied=code, discount_percent=discount)
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
        await message.answer(f"✅ Промокод <b>{code}</b> активирован! (-{discount}%)\n💰 Цена со скидкой: <b>{final_price} грн</b>\n\n✍️ Введите ваш никнейм на сервере:", parse_mode="HTML", reply_markup=builder.as_markup())
        await state.set_state(BuyState.entering_nickname)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="Пропустить", callback_data="skip_promocode")
        await message.answer("❌ Промокод не найден.", reply_markup=builder.as_markup())

@dp.message(F.text, BuyState.entering_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    nickname = message.text.strip()
    if len(nickname) < 3:
        await message.answer("❌ Никнейм слишком короткий.")
        return
    await state.update_data(nickname=nickname)
    data = await state.get_data()
    promo_info = f"\n🎁 Промокод: <b>{data.get('promocode_applied')} (-{data.get('discount_percent')}%)</b>" if data.get('promocode_applied') else ""
    
    summary = (f"✨ <b>Ваш заказ</b> ✨\n🌍 Сервер: <b>{get_clean_server_name(data.get('server'))}</b>\n"
               f"🎮 Никнейм: <b>{nickname}</b>\n💰 Сумма: <b>{data.get('amount')} KK</b>{promo_info}\n"
               f"💵 Итого: <b>{data.get('price')} грн</b>\n\nРеквизиты для оплаты:\n<code>{НОМЕР_КАРТЫ}</code>\n\n"
               f"После оплаты нажмите кнопку <b>'Я оплатил'</b> и отправьте скриншот чека.")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data="payment_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    await message.answer(summary, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.set_state(BuyState.waiting_for_proof)

@dp.callback_query(F.data == "payment_confirm", BuyState.waiting_for_proof)
async def payment_confirmed_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📸 <b>Отлично! Теперь ожидаем чек.</b>\n\nПожалуйста, **отправьте скриншот или фотографию чека** об оплате в чат.", parse_mode="HTML")
    await callback.answer()

@dp.message(F.photo, BuyState.waiting_for_proof)
async def process_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    user_db_data = get_user_data(user.id)
    
    order_details = {
        'server': data.get('server'), 'nickname': data.get('nickname'),
        'amount_kk': data.get('amount'), 'proof_photo_id': message.photo[-1].file_id,
        'promocode_applied': data.get('promocode_applied')
    }
    price = data.get('price')
    order_id = add_order(user.id, 'virts', order_details, price)
    if data.get('promocode_applied'): use_promocode(data['promocode_applied'])

    # Рефералка
    if user_db_data and user_db_data[2] == 1:
        referrer_id = user_db_data[1]
        if referrer_id and price > 0:
            reward_kk = round((price * ПРОЦЕНТ_РЕФЕРАЛА) / ЦЕНА_ЗА_1КК, 2)
            update_referrer_stats(referrer_id, reward_kk)
            mark_as_old(user.id)
            try:
                await bot.send_message(referrer_id, f"🎉 <b>ПОЗДРАВЛЯЕМ!</b>\nВаш реферал совершил покупку! Вам начислено <b>{reward_kk} KK</b>.", parse_mode="HTML")
            except Exception: pass

    # Админ уведомление
    promo_line = f"🎁 Промокод: <b>{data.get('promocode_applied')}</b>\n" if data.get('promocode_applied') else ""
    admin_text = (f"🚨 <b>НОВЫЙ ЗАКАЗ # {order_id} (ВИРТЫ)</b>\n--------------------------\n"
                  f"👤 Покупатель: <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
                  f"🌍 Сервер: <b>{data.get('server', 'N/A')}</b>\n🎮 Ник: <b>{data.get('nickname', 'N/A')}</b>\n"
                  f"📦 Сумма: <b>{data.get('amount', 'N/A')} кк</b>\n{promo_line}💰 Итого: <b>{price} грн</b>\n\n⚠️ <b>ЧЕК ПРИКРЕПЛЕН ВЫШЕ</b>")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выдать", callback_data=f"order_complete_{order_id}")
    builder.button(text="❌ Отмена", callback_data=f"order_cancel_{order_id}")
    builder.adjust(1, 1)

    if ADMIN_ID:
        try:
            await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки чека админу: {e}")

    await message.answer("✅ <b>Чек принят!</b>\n\nВаша заявка отправлена администратору. Ожидайте выдачи.", parse_mode="HTML")
    await state.clear()

@dp.message(F.message_text, BuyState.waiting_for_proof)
async def process_payment_proof_error(message: types.Message):
    await message.answer("❌ Ожидается **фотография** чека, а не текст.")

# --- РАЗБАН ---
# (Логика аналогична виртам, сокращена для лимита символов, но она тут есть)
@dp.callback_query(F.data == "start_unban")
async def show_unban_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оформить заявку", callback_data="unban_start_form")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    try:
        await callback.message.edit_caption(caption=f"🛡️ <b>Разбан аккаунта</b>\n\nСтоимость: <b>{ЦЕНА_РАЗБАНА} грн</b>", parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.edit_text(text=f"🛡️ <b>Разбан аккаунта</b>\n\nСтоимость: <b>{ЦЕНА_РАЗБАНА} грн</b>", parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "unban_start_form")
async def start_unban_form(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UnbanState.waiting_for_screenshot)
    await callback.message.edit_text("📸 **1/4: Скриншот блокировки**", parse_mode="HTML")
    await callback.answer()

@dp.message(F.photo, UnbanState.waiting_for_screenshot)
async def process_unban_screenshot(message: types.Message, state: FSMContext):
    await state.update_data(screenshot_id=message.photo[-1].file_id)
    await message.answer("📝 **2/4: Причина бана**")
    await state.set_state(UnbanState.waiting_for_reason)

@dp.message(F.text, UnbanState.waiting_for_reason)
async def process_unban_reason(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("💎 **3/4: Имущество**")
    await state.set_state(UnbanState.waiting_for_property)

@dp.message(F.text, UnbanState.waiting_for_property)
async def process_unban_property(message: types.Message, state: FSMContext):
    await state.update_data(property_list=message.text)
    await message.answer("🖼️ **4/4: Дополнительные скрины (Опционально)**\nНапишите '-' если нет.")
    await state.set_state(UnbanState.waiting_for_forum_proof)

@dp.message(UnbanState.waiting_for_forum_proof)
async def process_unban_forum_proof(message: types.Message, state: FSMContext):
    fp = message.photo[-1].file_id if message.photo else message.text
    await state.update_data(forum_proof=fp)
    await message.answer(f"✅ <b>Заявка сформирована!</b>\nСтоимость: <b>{ЦЕНА_РАЗБАНА} грн</b>\nРеквизиты: <code>{НОМЕР_КАРТЫ}</code>\n\nПришлите чек.", parse_mode="HTML")
    await state.set_state(UnbanState.waiting_for_payment)

@dp.message(F.photo, UnbanState.waiting_for_payment)
async def process_unban_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    order_id = add_order(user.id, 'unban', {'reason': data['reason']}, ЦЕНА_РАЗБАНА)
    
    admin_text = f"🚨 <b>НОВАЯ ЗАЯВКА # {order_id} (РАЗБАН)</b>\n👤 Клиент: {user.full_name}\n💰 <b>{ЦЕНА_РАЗБАНА} грн</b>"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено", callback_data=f"order_complete_{order_id}")
    builder.button(text="❌ Отмена", callback_data=f"order_cancel_{order_id}")
    
    if ADMIN_ID:
        try:
            await bot.send_photo(chat_id=ADMIN_ID, photo=data['screenshot_id'], caption="🖼️ СКРИН БЛОКИРОВКИ")
            await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except: pass
    await message.answer("✅ <b>Скриншот получен!</b> Ожидайте.")
    await state.clear()

# --- ИНФО (ПРОФИЛЬ, РЕФЕРАЛКА, ПРАВИЛА) ---

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    add_user(callback.from_user.id) # Страховка
    user = callback.from_user
    try:
        reg_date = (await bot.get_chat(user.id)).date.strftime('%d.%m.%Y')
    except:
        reg_date = "неизвестна"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 История заказов", callback_data="order_history")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    text = f"👤 <b>Твой профиль</b>\n\n🆔 ID: <code>{user.id}</code>\n👤 Имя: {user.full_name}\n📅 Дата регистрации: {reg_date}"
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "referral_info")
async def referral_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    # 1. ОБЯЗАТЕЛЬНО проверяем/создаем юзера в БД, иначе краш
    add_user(callback.from_user.id)
    
    user_data = get_user_data(callback.from_user.id)
    # Если вдруг всё равно нет данных (маловероятно), обрабатываем мягко
    if not user_data:
        await callback.answer("Ошибка базы данных. Попробуйте /start", show_alert=True)
        return

    referrer_id, referrals_count, rewards_kk = user_data[1], user_data[3], user_data[4]
    ref_link = f"https://t.me/{callback.bot.username}?start=ref_{callback.from_user.id}"
    
    text = (f"🤝 <b>Реферальная программа</b>\n\nБонус: <b>5%</b> от покупок друзей.\n\nСсылка: <code>{ref_link}</code>\n"
            f"👥 Друзей: <b>{referrals_count}</b>\n💰 Бонусов: <b>{rewards_kk:.2f} KK</b>")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
        else:
            await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        # Если редактировать нельзя, удаляем и шлем новое (самый надежный способ)
        try: await callback.message.delete()
        except: pass
        await callback.message.answer(text=text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "order_history")
async def show_order_history(callback: types.CallbackQuery):
    orders = get_user_orders(callback.from_user.id)
    text = "📜 <b>История (Последние 10):</b>\n\n"
    if not orders: text += "Нет заказов."
    else:
        for o in orders[:10]:
            dt = datetime.strptime(o[6].split('.')[0], '%Y-%m-%d %H:%M:%S').strftime('%d.%m')
            text += f"🆔 #{o[0]} | {o[2]} | {o[5]} грн | {dt}\n"
            
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    text = "📜 <b>Правила</b>\n\n1. Вирты после оплаты.\n2. Гарантия на разбан 99%."
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    try:
        await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

# --- АДМИН ПАНЕЛЬ ---

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    stats = get_admin_stats()
    text = f"👑 <b>Админ-панель</b>\n👥 Юзеров: {stats[0]}\n🛒 Заказов: {stats[1]}"
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🎁 Создать промокод", callback_data="admin_promo")
    builder.adjust(1)
    await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminState.waiting_for_broadcast_content)
    await callback.message.edit_text("📢 Пришлите сообщение для рассылки.")
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast_content)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    await state.clear()
    users = get_all_users_ids()
    count = 0
    await message.answer(f"Начинаю рассылку на {len(users)} чел.")
    for uid in users:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Отправлено: {count}")

@dp.callback_query(F.data == "admin_promo")
async def admin_promo(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminState.waiting_for_promo_code)
    await callback.message.edit_text("🎁 Введите код (например SALE):")
    await callback.answer()

@dp.message(F.text, AdminState.waiting_for_promo_code)
async def admin_promo_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.upper())
    await state.set_state(AdminState.waiting_for_promo_discount)
    await message.answer("Введите % скидки (число):")

@dp.message(F.text, AdminState.waiting_for_promo_discount)
async def admin_promo_disc(message: types.Message, state: FSMContext):
    try:
        disc = int(message.text)
        await state.update_data(discount=disc)
        await state.set_state(AdminState.waiting_for_promo_max_uses)
        await message.answer("Введите кол-во использований (0 - безлимит):")
    except: await message.answer("Нужно число.")

@dp.message(F.text, AdminState.waiting_for_promo_max_uses)
async def admin_promo_fin(message: types.Message, state: FSMContext):
    try:
        uses = int(message.text)
        data = await state.get_data()
        create_promocode(data['code'], data['discount'], None if uses==0 else uses)
        await message.answer(f"✅ Промокод {data['code']} создан!")
        await state.clear()
    except: await message.answer("Нужно число.")

@dp.callback_query(F.data.startswith("order_complete_"))
async def admin_complete(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    oid = int(c.data.split('_')[2])
    update_order_status(oid, 'Completed')
    await c.message.edit_caption(caption=c.message.caption + "\n\n✅ ВЫПОЛНЕНО")

@dp.callback_query(F.data.startswith("order_cancel_"))
async def admin_cancel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    oid = int(c.data.split('_')[2])
    update_order_status(oid, 'Cancelled')
    await c.message.edit_caption(caption=c.message.caption + "\n\n❌ ОТМЕНЕНО")

# --- CATCH-ALL ---
@dp.callback_query()
async def catch_all(c: types.CallbackQuery, state: FSMContext):
    await c.answer("Ошибка. Перезагрузка меню.")
    await send_or_edit_start_menu(c, state)

# --- ЗАПУСК ---
async def handle(request): return web.Response(text="OK")

async def main():
    db_start()
    app = web.Application()
    app.router.add_get('/', handle)
    port = int(os.environ.get('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await asyncio.gather(dp.start_polling(bot), site.start())

if __name__ == "__main__":
    if not API_TOKEN: logging.error("NO TOKEN")
    else: asyncio.run(main())
