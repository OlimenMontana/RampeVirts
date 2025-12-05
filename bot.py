import asyncio
import logging
import sqlite3
import math 
import os # Додано для змінних середовища
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web # ДОДАНО для запуску веб-сервера на Render

# --- КОНФИГУРАЦИЯ (ЧИТАЕТСЯ ИЗ ПЕРЕМЕННЫХ СРЕДЫ) ---

# Читаем токен и ID из Environment Variables (это безопасно)
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')          
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID')) if os.getenv('TELEGRAM_ADMIN_ID') else None 

SUPPORT_LINK = "https://t.me/liffi1488" 
CARD_NUMBER = "4323 3473 6140 0119"      

PRICE_PER_1KK = 40                      
FEEDBACK_LINK = "https://t.me/RampeVirtsFeedbacks"
PHOTO_URL = None 

REFERRAL_BONUS_PERCENTAGE = 0.05 


# --- КОРРЕКТНЫЙ СПИСОК СЕРВЕРОВ ---
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

# --- БАЗА ДАННЫХ (SQLite) ---

def db_start():
    """Инициализация базы данных и создание таблицы 'users', если она не существует."""
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
    db.commit()

def add_user(user_id, referrer_id=None):
    """Добавление нового пользователя и фиксация реферера."""
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
        db.commit()
    
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

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class BuyState(StatesGroup):
    """Состояния для процесса покупки."""
    choosing_server = State()
    entering_amount = State()

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
    
    # 3. ОТПРАВКА МЕНЮ
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Купить вирты", callback_data="start_buy")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🤝 Рефералка", callback_data="referral_info") 
    builder.button(text="⭐ Отзывы", url=FEEDBACK_LINK)
    builder.button(text="📜 Правила / FAQ", callback_data="rules")
    builder.button(text="👨‍💻 Поддержка", url=SUPPORT_LINK)
    
    builder.adjust(1, 2, 1, 2)

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


# ИСПРАВЛЕНИЕ: Устойчивость edit_caption
@dp.callback_query(F.data == "start_buy")
async def show_servers(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    
    for server_id, server_full_name in SERVERS_MAPPING.items():
        builder.button(text=f"🟢 {server_full_name}", callback_data=f"srv_{server_id}")
    
    builder.adjust(3)
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    caption_text = "🌍 Выберите ваш сервер:"
    
    try:
        await callback.message.edit_caption(
            caption=caption_text,
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=caption_text, 
            reply_markup=builder.as_markup()
        )
    await state.set_state(BuyState.choosing_server)


# ИСПРАВЛЕНИЕ: Устойчивость edit_caption
@dp.callback_query(F.data.startswith("srv_"), BuyState.choosing_server)
async def server_chosen(callback: types.CallbackQuery, state: FSMContext):
    server_id = callback.data.split("_")[1]
    
    server_name = SERVERS_MAPPING.get(server_id, "Неизвестный сервер")
    
    await state.update_data(server=server_name)
    
    caption_text = (f"✅ Выбран сервер: <b>{server_name}</b>\n\n"
                    f"Введите количество виртов (в миллионах).\n"
                    f"Например, если нужно 5кк, просто напишите цифру: <b>5</b>")
    
    try:
        await callback.message.edit_caption(
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=None 
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=caption_text,
            parse_mode="HTML",
            reply_markup=None 
        )
    await state.set_state(BuyState.entering_amount)

@dp.message(BuyState.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите только число (например: 5).")
        return

    amount_kk = int(message.text)
    
    if amount_kk < 1:
        await message.answer("❌ Минимальная покупка — 1 миллион.")
        return

    total_price = amount_kk * PRICE_PER_1KK
    data = await state.get_data()
    server_name = data['server']

    await state.update_data(amount=amount_kk, price=total_price)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data="payment_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)

    await message.answer(
        f"🧾 <b>Счет на оплату</b>\n"
        f"--------------------------\n"
        f"🌍 Сервер: <b>{server_name}</b>\n"
        f"📦 Товар: <b>{amount_kk} KK</b> (миллионов)\n"
        f"💵 К оплате: <b>{total_price} грн</b>\n"
        f"--------------------------\n\n"
        f"💳 Реквизиты:\n"
        f"<code>{CARD_NUMBER}</code>\n\n"
        f"⚠️ После перевода нажмите кнопку <b>«Я оплатил»</b> ниже и ожидайте выдачи.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "payment_confirm")
async def payment_confirmed(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user
    user_db_data = get_user_data(user.id)
    
    # --- ЛОГИКА РЕФЕРАЛКИ (5% от покупки) ---
    if user_db_data and user_db_data[2] == 1: # Проверяем, является ли пользователь новым (is_new == 1)
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
                    f"На ваш бонусный счет зачислено <b>{reward_kk_rounded} KK</b> ({REFERRAL_BONUS_PERCENTAGE*100}% от покупки).", 
                    parse_mode="HTML")
            except Exception as e:
                logging.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")
    # -------------------------

    admin_text = (
        f"🚨 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
        f"👤 Покупатель: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username or 'нет юзернейма'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🌍 Сервер: <b>{data.get('server', 'N/A')}</b>\n"
        f"📦 Сумма виртов: <b>{data.get('amount', 'N/A')} кк</b>\n"
        f"💰 Ожидаемый приход: <b>{data.get('price', 'N/A')} грн</b>\n\n"
        f"⚠️ Проверь поступление на карту и свяжись с покупателем!"
    )
    
    if ADMIN_ID:
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки сообщения админу {ADMIN_ID}: {e}")

    await callback.message.edit_text(
        "✅ <b>Заявка отправлена администратору!</b>\n\n"
        "Мы проверим платеж и свяжемся с вами для выдачи валюты.",
        parse_mode="HTML"
    )
    await state.clear()


# ИСПРАВЛЕНИЕ: Устойчивость edit_caption
@dp.callback_query(F.data == "referral_info")
async def show_referral_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    
    referrals_count = data[3] if data else 0
    rewards = data[4] if data else 0.0
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")

    referral_text = (
        f"🤝 <b>Твоя Реферальная Система</b>\n\n"
        f"🔗 <b>Твоя уникальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 Приглашенных друзей: <b>{referrals_count}</b>\n"
        f"🎁 Твой бонусный баланс: <b>{rewards} KK</b>\n\n"
        f"💰 <b>Правила:</b> Ты получаешь <b>{REFERRAL_BONUS_PERCENTAGE*100}%</b> от суммы первой покупки каждого друга на бонусный баланс!"
    )
    
    try:
        await callback.message.edit_caption(
            caption=referral_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=referral_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    await callback.answer()


# ИСПРАВЛЕНИЕ: Безопасное получение даты и устойчивость edit_caption
@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    user = callback.from_user
    registration_date = "неизвестна"

    # --- БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ДАТЫ (ИСПРАВЛЕНИЕ ОШИБКИ) ---
    try:
        chat_info = await bot.get_chat(user.id)
        if chat_info.date:
            registration_date = chat_info.date.strftime('%d.%m.%Y')
    except Exception:
        registration_date = "недоступна"
    # ----------------------------------------------------
    
    caption_text = (
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 Твой ID: <code>{user.id}</code>\n"
        f"👤 Имя: {user.full_name}\n"
        f"📅 Дата регистрации: {registration_date}\n\n"
        f"💸 Чтобы увидеть историю покупок, совершите первый заказ."
    )
    
    try:
        await callback.message.edit_caption(
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=callback.message.reply_markup
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            text=caption_text,
            parse_mode="HTML",
            reply_markup=callback.message.reply_markup
        )
    await callback.answer() 

# ИСПРАВЛЕНИЕ: Устойчивость edit_caption
@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    
    rules_text = (
        "📜 <b>ПРАВИЛА И FAQ</b>\n\n"
        "1️⃣ <b>Время выдачи:</b> Обычно 5-15 минут после оплаты (если мы онлайн).\n"
        "2️⃣ <b>Способ выдачи:</b> Мы переводим на банковский счет в игре, передаем трейдом или через ФА.\n"
        "3️⃣ <b>Гарантии:</b> Смотрите раздел 'Отзывы'. Мы дорожим репутацией.\n"
        "4️⃣ <b>Безопасность:</b> Не обсуждайте покупку виртов В ИГРЕ, чтобы избежать бана."
    )
    
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

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() 
    
    await callback.message.edit_text("❌ Покупка отменена. Возвращаемся в главное меню.")
    await cmd_start(callback.message) 
    await callback.answer()


# --- ЗАПУСК БОТА (ВЫПРАВЛЕНИЕ ДЛЯ RENDER) ---

# ДОДАЄМО aiohttp handle для задоволення вимог Web Service
async def handle(request):
    """Проста відповідь для Health Check Render."""
    return web.Response(text="Bot is running via polling.")

async def main():
    db_start()
    
    # --- БЛОК ЗАПУСКУ ДЛЯ RENDER WEB SERVICE (ПОТРІБЕН ФІНАНСАМИ 0) ---
    
    app = web.Application()
    app.router.add_get('/', handle)
    
    # Визначаємо порт, який Render буде шукати. Порт береться з Environment Variables
    port = int(os.environ.get('PORT', 8080))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    
    # Запускаємо Polling та Web-сервер одночасно
    await asyncio.gather(
        dp.start_polling(bot),
        site.start()
    )
    # ------------------------------------------------------------------

if __name__ == "__main__":
    if not API_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN не встановлено у змінних середовищах!")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Бот остановлен вручную.")
