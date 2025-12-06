import asyncio
import logging
import sqlite3
import math 
import os 
import json # Додано для зберігання деталей замовлення
from datetime import datetime # Додано для дати
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
UNBAN_PRICE = 2500 # Нова константа ціни розбану
FEEDBACK_LINK = "https://t.me/RampeVirtsFeedbacks"
PHOTO_URL = None 

REFERRAL_BONUS_PERCENTAGE = 0.05 

# ... (SERVERS_MAPPING залишився без змін) ...
SERVERS_MAPPING = {
    "1": "RED", "2": "GREEN", "3": "BLUE", "4": "YELLOW", "5": "ORANGE",
    "6": "PURPLE", "7": "LIME", "8": "PINK", "9": "CHERRY", "10": "BLACK", 
    "11": "INDIGO", "12": "WHITE", "13": "MAGENTA", "14": "CRIMSON", "15": "GOLD",
    "16": "AZURE", "17": "PLATINUM", "18": "AQUA", "19": "GRAY", "20": "ICE",
    "21": "CHILLI", "22": "CHOCO", "23": "MOSCOW", "24": "SPB", "25": "UFA",
    "26": "SOCHI", "27": "KAZAN", "28": "SAMARA", "29": "ROSTOV", "30": "ANAPA",
    "31": "EKATERINBURG", "32": "KRASNODAR", "33": "ARZAMAS", "34": "NOVOSIBIRSK",
    "35": "GROZNY", "36": "SARATOV", "37": "OMSK", "38": "IRKUTSK", "39": "VOLGOGRAD",
    "40": "VORONEZH", "41": "BELGOROD", "42": "MAKHACHKALA", "43": "VLADIKAVKAZ",
    "44": "VLADIVOSTOK", "45": "KALININGRAD", "46": "CHELYABINSK", "47": "KRASNOYARSK",
    "48": "CHEBOKSARY", "49": "KHABAROVSK", "50": "PERM", "51": "TULA", "52": "RYAZAN",
    "53": "MURMANSK", "54": "PENZA", "55": "KURSK", "56": "ARKHANGELSK", "57": "ORENBURG",
    "58": "KIROV", "59": "KEMEROVO", "60": "TYUMEN", "61": "TOLYATTI", "62": "IVANOVO",
    "63": "STAVROPOL", "64": "SMOLENSK", "65": "PSKOV", "66": "BRYANSK", "67": "OREL",
    "68": "YAROSLAVL", "69": "BARNAUL", "70": "LIPETSK", "71": "ULYANOVSK", "72": "YAKUTSK",
    "73": "TAMBOV", "74": "BRATSK", "75": "ASTRAKHAN", "76": "CHITA", "77": "KOSTROMA",
    "78": "VLADIMIR", "79": "KALUGA", "80": "N.NOVGOROD", "81": "TAGANROG", "82": "VOLOGDA",
    "83": "TVER", "84": "TOMSK", "85": "IZHEVSK", "86": "SURGUT", "87": "PODOLSK",
    "88": "MAGADAN", "89": "CHEREPOVETS"
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
db = None

# --- БАЗА ДАННЫХ (SQLite) ---

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
    # НОВАЯ ТАБЛИЦА: orders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            type TEXT, -- 'virts' or 'unban'
            status TEXT DEFAULT 'Pending_Admin', -- Pending_Admin, Completed, Cancelled
            details TEXT, -- JSON с деталями заказа
            price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

# ... (add_user, get_user_data, update_referrer_stats, mark_as_old залишилися без змін) ...

def get_user_data(user_id):
    """Получение данных пользователя."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_referrer_stats(referrer_id, reward_kk):
    """Обновление статистики реферера после первой покупки приглашенного с учетом награды."""
    cursor = db.cursor()
    cursor.execute("""
        UPDATE users SET referrals_count = referrals_count + 1, 
        referral_rewards_kk = referral_rewards_kk + ? 
        WHERE user_id = ?
    """, (reward_kk, referrer_id))
    db.commit()

def mark_as_old(user_id):
    """Отмечаем пользователя как 'не новый', чтобы не вознаграждать реферера дважды."""
    cursor = db.cursor()
    cursor.execute("UPDATE users SET is_new = 0 WHERE user_id = ?", (user_id,))
    db.commit()

# --- НОВЫЕ DB ФУНКЦИИ ---

def add_order(user_id: int, order_type: str, details: dict, price: float) -> int:
    """Добавление нового заказа в базу данных и возвращение его ID."""
    cursor = db.cursor()
    details_json = json.dumps(details)
    cursor.execute("""
        INSERT INTO orders (user_id, type, details, price) 
        VALUES (?, ?, ?, ?)
    """, (user_id, order_type, details_json, price))
    db.commit()
    return cursor.lastrowid

def update_order_status(order_id: int, status: str):
    """Обновление статуса заказа."""
    cursor = db.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    db.commit()

def get_user_orders(user_id: int):
    """Получение всех заказов пользователя."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    # order_id, user_id, type, status, details, price, created_at
    return cursor.fetchall()

def get_admin_stats():
    """Получение статистики для админ-панели."""
    cursor = db.cursor()
    
    # Общее число пользователей
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    # Активные заказы
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending_Admin'")
    active_orders = cursor.fetchone()[0]
    
    # Общая реферальная награда (в KK)
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

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # ... (логика рефералки и добавления пользователя) ...
    user_id = message.from_user.id
    referrer_id = None
    
    if message.text.startswith('/start ref_'):
        try:
            referrer_id = int(message.text.split('_')[1])
            if referrer_id == user_id: 
                referrer_id = None
        except (IndexError, ValueError):
            referrer_id = None
    
    add_user(user_id, referrer_id)
    
    # 3. ОТПРАВКА МЕНЮ
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
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"🏰 Лучший магазин валюты Black Russia.\n"
        f"💰 Курс: <b>{PRICE_PER_1KK} грн₴</b> за 1кк.\n"
        f"👇 Выбирай, что нужно:"
    )

    if PHOTO_URL:
        try:
            await message.answer_photo(
                photo=PHOTO_URL,
                caption=welcome_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
            
    await message.answer(text=welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")


# --- ХЕНДЛЕРЫ КУПИТЬ ВИРТЫ (изменена логика сохранения и отправки админу) ---

# ... (show_servers, server_chosen, process_amount, process_nickname без изменений) ...

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
    
    # 1. СОХРАНЕНИЕ ЗАКАЗА В БД
    order_details = {
        'server': data.get('server'),
        'nickname': data.get('nickname'),
        'amount_kk': data.get('amount'),
        'proof_photo_id': message.photo[-1].file_id # Сохраняем ID чека
    }
    order_id = add_order(user.id, 'virts', order_details, data.get('price'))

    # 2. ЛОГИКА РЕФЕРАЛКИ (Только после первого заказа)
    if user_db_data and user_db_data[2] == 1: 
        referrer_id = user_db_data[1]
        purchase_price_uah = data.get('price', 0)
        
        if referrer_id and purchase_price_uah > 0:
            reward_uah = purchase_price_uah * REFERRAL_BONUS_PERCENTAGE
            reward_kk = reward_uah / PRICE_PER_1KK
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
    admin_caption = (
        f"🚨 <b>НОВЫЙ ЗАКАЗ # {order_id} (ВИРТЫ)</b>\n"
        f"--------------------------\n"
        f"👤 Покупатель: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username or 'нет юзернейма'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🌍 Сервер: <b>{data.get('server', 'N/A')}</b>\n"
        f"🎮 Ник: <b>{data.get('nickname', 'N/A')}</b>\n"
        f"📦 Сумма виртов: <b>{data.get('amount', 'N/A')} кк</b>\n"
        f"💰 Ожидаемый приход: <b>{data.get('price', 'N/A')} грн</b>\n\n"
        f"⚠️ <b>ЧЕК ПРИКРЕПЛЕН ВЫШЕ</b>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выдать", callback_data=f"order_complete_{order_id}")
    builder.button(text="❌ Отмена", callback_data=f"order_cancel_{order_id}")
    builder.adjust(1, 1)

    if ADMIN_ID:
        try:
            # Отправляем фото админу с деталями заказа
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


# --- ХЕНДЛЕРЫ РАЗБАНА (изменена логика сохранения и отправки админу) ---

# ... (show_unban_info, start_unban_form, process_unban_screenshot, process_unban_reason, process_unban_property, process_unban_forum_proof без изменений) ...

@dp.message(F.photo, UnbanState.waiting_for_payment)
async def process_unban_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    
    # 1. СОХРАНЕНИЕ ЗАКАЗА В БД
    order_details = {
        'reason': data.get('reason'),
        'property_list': data.get('property_list'),
        'forum_proof': data.get('forum_proof'),
        'screenshot_id': data.get('screenshot_id'),
        'payment_proof_id': message.photo[-1].file_id # Чек оплаты
    }
    order_id = add_order(user.id, 'unban', order_details, UNBAN_PRICE)
    
    # 2. ФОРМИРОВАНИЕ И ОТПРАВКА АДМИНУ (С КНОПКАМИ)
    admin_caption = (
        f"🚨 <b>НОВАЯ ЗАЯВКА # {order_id} (РАЗБАН)</b>\n"
        f"--------------------------\n"
        f"👤 Клиент: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username or 'нет юзернейма'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Ожидаемый приход: <b>{UNBAN_PRICE} грн</b>\n\n"
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
            # 1. Отправка скрина блокировки
            await bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=data['screenshot_id'], 
                caption="🖼️ СКРИН БЛОКИРОВКИ",
            )
            # 2. Отправка чека с деталями заказа
            await bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=message.photo[-1].file_id, 
                caption=admin_caption, 
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки чека разбана админу {ADMIN_ID}: {e}")

    # 3. Ответ покупателю
    await message.answer(
        "✅ <b>Скриншот оплаты получен!</b>\n\n"
        "Мы немедленно приступаем к работе по разбану вашего аккаунта. Ожидайте, мы свяжемся с вами для уточнения деталей."
    )
    
    await state.clear()


# --- НОВЫЕ ХЕНДЛЕРЫ АДМИНИСТРАТОРА (2.1 и 2.2) ---

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Админ-панель со статистикой."""
    if message.from_user.id != ADMIN_ID:
        return 
    
    total_users, active_orders, total_referral_rewards = get_admin_stats()
    
    stats_text = (
        "👑 <b>АДМИН-ПАНЕЛЬ СТАТИСТИКА</b>\n"
        "-----------------------------------\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🛒 Активных заказов (в ожидании): <b>{active_orders}</b>\n"
        f"🤝 Начислено реф. виртов (KK): <b>{total_referral_rewards:.2f}</b>\n"
        "-----------------------------------"
    )
    
    await message.answer(stats_text, parse_mode="HTML")

@dp.callback_query(F.data.startswith("order_complete_"))
async def admin_complete_order(callback: types.CallbackQuery):
    """Обработка кнопки 'Завершить заказ'."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав администратора.")
        return 

    order_id = int(callback.data.split('_')[-1])
    update_order_status(order_id, 'Completed')
    
    # 1. Обновление сообщения админа
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n🟢 <b>СТАТУС: ВЫПОЛНЕНО</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=callback.message.text + "\n\n🟢 <b>СТАТУС: ВЫПОЛНЕНО</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    
    # 2. Уведомление пользователя
    orders = get_user_orders(callback.message.reply_to_message.from_user.id) # Здесь нужна точная логика, но для простоты возьмем user_id из БД
    # В реальной реализации здесь нужно достать user_id из БД по order_id.
    
    cursor = db.cursor()
    cursor.execute("SELECT user_id, type FROM orders WHERE order_id = ?", (order_id,))
    order_data = cursor.fetchone()
    
    if order_data:
        user_id, order_type = order_data
        service_name = "разбану аккаунта" if order_type == 'unban' else "покупке виртов"
        try:
            await bot.send_message(user_id, 
                f"🎉 **Заказ #{order_id} завершен!**\n"
                f"Ваша заявка по {service_name} была успешно выполнена. Свяжитесь с нами, если у вас остались вопросы.", 
                parse_mode="Markdown")
        except TelegramForbiddenError:
            logging.warning(f"Не удалось уведомить пользователя {user_id}: Бот заблокирован.")
        except Exception as e:
            logging.error(f"Ошибка при уведомлении пользователя {user_id}: {e}")

    await callback.answer(f"Заказ #{order_id} отмечен как выполненный.")


@dp.callback_query(F.data.startswith("order_cancel_"))
async def admin_cancel_order(callback: types.CallbackQuery):
    """Обработка кнопки 'Отменить заказ'."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав администратора.")
        return 

    order_id = int(callback.data.split('_')[-1])
    update_order_status(order_id, 'Cancelled')

    # 1. Обновление сообщения админа
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n🔴 <b>СТАТУС: ОТМЕНЕНО</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=callback.message.text + "\n\n🔴 <b>СТАТУС: ОТМЕНЕНО</b>",
            reply_markup=None,
            parse_mode="HTML"
        )

    # 2. Уведомление пользователя
    cursor = db.cursor()
    cursor.execute("SELECT user_id, type FROM orders WHERE order_id = ?", (order_id,))
    order_data = cursor.fetchone()
    
    if order_data:
        user_id, order_type = order_data
        service_name = "разбану аккаунта" if order_type == 'unban' else "покупке виртов"
        try:
            await bot.send_message(user_id, 
                f"🔴 **Заказ #{order_id} отменен.**\n"
                f"Ваша заявка по {service_name} была отменена администратором. Пожалуйста, свяжитесь с поддержкой для уточнения.", 
                parse_mode="Markdown")
        except TelegramForbiddenError:
            logging.warning(f"Не удалось уведомить пользователя {user_id}: Бот заблокирован.")
        except Exception as e:
            logging.error(f"Ошибка при уведомлении пользователя {user_id}: {e}")

    await callback.answer(f"Заказ #{order_id} отменен.")


# --- ХЕНДЛЕРЫ МЕНЮ И ПРОФИЛЯ (добавлена История заказов 1.1) ---

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
    """Отображение истории заказов пользователя (1.1)."""
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
            
            # Форматирование статуса
            status_map = {
                'Pending_Admin': '⏳ Ожидает',
                'Completed': '✅ Выполнен',
                'Cancelled': '❌ Отменен'
            }
            display_status = status_map.get(status, status)
            
            # Форматирование деталей
            if order_type == 'virts':
                summary = f"💰 {details.get('amount_kk')} KK на {details.get('server')}"
            else:
                summary = f"🛡️ Разбан аккаунта"

            # Форматирование даты
            date_obj = datetime.strptime(created_at.split('.')[0], '%Y-%m-%d %H:%M:%S')
            
            history_text += (
                f"--------------------------\n"
                f"🆔 **Заказ #{order_id}** ({order_type.upper()})\n"
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


# ... (Все остальные хендлеры (referral_info, rules, back_to_menu, cancel) остались без изменений) ...


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
