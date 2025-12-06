import asyncio
import logging
import sqlite3
import math 
import os 
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web 

# --- КОНФИГУРАЦИЯ ---

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')          
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID')) if os.getenv('TELEGRAM_ADMIN_ID') else None 

SUPPORT_LINK = "https://t.me/liffi1488" 
CARD_NUMBER = "4323 3473 6140 0119"      
ACCOUNTS_CHANNEL_LINK = "https://t.me/RampeAccounts" # НОВАЯ КОНСТАНТА

PRICE_PER_1KK = 40                      
FEEDBACK_LINK = "https://t.me/RampeVirtsFeedbacks"
PHOTO_URL = None 

REFERRAL_BONUS_PERCENTAGE = 0.05 


# --- КОРРЕКТНЫЙ СПИСОК СЕРВЕРОВ ---
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

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class BuyState(StatesGroup):
    """Состояния для процесса покупки виртов."""
    choosing_server = State()
    entering_amount = State()
    entering_nickname = State() 
    waiting_for_proof = State() 

class UnbanState(StatesGroup):
    """НОВЫЙ КЛАСС: Состояния для разбана аккаунта."""
    waiting_for_screenshot = State()    # 1. Скриншот блокировки
    waiting_for_reason = State()        # 2. Описание причины бана
    waiting_for_property = State()      # 3. Список имущества
    waiting_for_forum_proof = State()   # 4. Скриншот обращения на форуме
    waiting_for_payment = State()       # 5. Ожидание оплаты

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
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
    
    # --- ОБНОВЛЕННОЕ ГЛАВНОЕ МЕНЮ ---
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Купить вирты", callback_data="start_buy")
    builder.button(text="🛡️ Разбан аккаунта", callback_data="start_unban") # НОВАЯ КНОПКА
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="🤝 Рефералка", callback_data="referral_info") 
    builder.button(text="⭐ Отзывы", url=FEEDBACK_LINK)
    builder.button(text="🛍️ Купить аккаунт", url=ACCOUNTS_CHANNEL_LINK) # НОВАЯ КНОПКА
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

# --- БЛОК РАЗБАНА АККАУНТА ---

@dp.callback_query(F.data == "start_unban")
async def show_unban_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear() # Очистка любых предыдущих состояний
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оформить заявку", callback_data="unban_start_form")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    info_text = (
        "🛡️ <b>Разбан аккаунта</b>\n\n"
        "Вернём доступ к аккаунту и имущество в целости и сохранности.\n\n"
        "Стоимость: <b>2500 грн</b>\n"
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
    
    data = await state.get_data()
    
    # --- ВЫВОД РЕКВИЗИТОВ И ЗАПРОС ОПЛАТЫ ---
    payment_text = (
        f"✅ <b>Заявка сформирована!</b>\n\n"
        f"Стоимость: <b>2500 грн</b>\n"
        f"Реквизиты для оплаты:\n"
        f"<code>{CARD_NUMBER}</code>\n\n"
        f"**После оплаты отправьте скриншот платежа сюда** — мы приступим к делу и свяжемся для уточнения деталей."
    )
    
    await message.answer(payment_text, parse_mode="HTML")
    await state.set_state(UnbanState.waiting_for_payment)

@dp.message(F.photo, UnbanState.waiting_for_payment)
async def process_unban_payment_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user
    
    admin_caption = (
        f"🚨 <b>НОВАЯ ЗАЯВКА НА РАЗБАН!</b>\n"
        f"--------------------------\n"
        f"👤 Клиент: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username or 'нет юзернейма'})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Ожидаемый приход: <b>2500 грн</b>\n\n"
        f"**ДАННЫЕ ЗАЯВКИ:**\n"
        f"• **Причина бана:** {data.get('reason', 'N/A')}\n"
        f"• **Имущество:** {data.get('property_list', 'N/A')}\n"
        f"• **Форум/Админ:** {'Чек прикреплен' if isinstance(data.get('forum_proof'), str) and data.get('forum_proof') != '-' else 'Нет/Текст'}\n"
        f"**⚠️ ЧЕК ПРИКРЕПЛЕН ВЫШЕ**"
    )

    # 1. Отправка скрина блокировки
    if ADMIN_ID and data.get('screenshot_id'):
        await bot.send_photo(
            chat_id=ADMIN_ID, 
            photo=data['screenshot_id'], 
            caption="🖼️ СКРИН БЛОКИРОВКИ"
        )
    
    # 2. Отправка чека
    if ADMIN_ID:
        try:
            await bot.send_photo(
                chat_id=ADMIN_ID, 
                photo=message.photo[-1].file_id, 
                caption=admin_caption, 
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


@dp.message(UnbanState.waiting_for_payment)
async def process_unban_payment_proof_error(message: types.Message, state: FSMContext):
    await message.answer("❌ Ожидается **фотография** или **скриншот** оплаты. Пожалуйста, отправьте его.")


# --- СУЩЕСТВУЮЩИЕ ХЕНДЛЕРЫ КУПИТЬ ВИРТЫ (сокращено) ---
# (Они остались, но здесь я их сократил для краткости. В финальном коде они есть.)

@dp.callback_query(F.data == "start_buy")
async def show_servers(callback: types.CallbackQuery, state: FSMContext):
    # ... (логика выбора серверов)
    await callback.message.edit_text("🌍 Выберите ваш сервер:", reply_markup=InlineKeyboardBuilder().as_markup())
    await state.set_state(BuyState.choosing_server)
    await callback.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)
    await callback.answer()

# --- ЗАПУСК БОТА (ВЫПРАВЛЕНИЕ ДЛЯ RENDER) ---

async def handle(request):
    return web.Response(text="Bot is running via polling.")

async def main():
    db_start()
    
    # --- БЛОК ЗАПУСКУ ДЛЯ RENDER WEB SERVICE ---
    
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
    # ------------------------------------------------------------------

if __name__ == "__main__":
    if not API_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN не встановлено у змінних середовищах!")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("Бот остановлен вручную.")
