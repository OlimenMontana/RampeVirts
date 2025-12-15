import asyncio, logging, sqlite3, os, json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
CARD = os.getenv("CARD_NUMBER", "НЕ УКАЗАНА")

PRICE_KK = 40
REF_PERCENT = 0.05
MIN_WITHDRAW_KK = 10

SUPPORT = "https://t.me/liffi1488"
REVIEWS = "https://t.me/RampeVirtsFeedbacks"

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ================= SERVERS =================
SERVERS = {str(i): f"SERVER {i}" for i in range(1, 90)}

# ================= DB =================
db = sqlite3.connect("shop.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    ref_id INTEGER,
    refs INTEGER DEFAULT 0,
    balance REAL DEFAULT 0
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    info TEXT,
    price REAL,
    status TEXT DEFAULT 'pending',
    date TEXT
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY,
    discount INTEGER,
    max_uses INTEGER,
    used INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS promo_uses (
    user_id INTEGER,
    code TEXT,
    PRIMARY KEY(user_id, code)
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS withdraws (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    status TEXT DEFAULT 'pending'
)""")

db.commit()

# ================= FSM =================
class Buy(StatesGroup):
    server = State()
    amount = State()
    promo = State()
    nick = State()
    proof = State()

class AdminFSM(StatesGroup):
    broadcast = State()
    promo_code = State()
    promo_disc = State()
    promo_limit = State()

# ================= MENUS =================
def main_menu(name):
    kb = InlineKeyboardBuilder()
    kb.button(text="💸 Купить", callback_data="buy")
    kb.button(text="👤 Профиль", callback_data="profile")
    kb.button(text="🤝 Рефералка", callback_data="ref")
    if ADMIN_ID:
        kb.button(text="👑 Админ", callback_data="admin")
    kb.button(text="⭐ Отзывы", url=REVIEWS)
    kb.button(text="👨‍💻 Поддержка", url=SUPPORT)
    kb.adjust(2,2,2)
    return f"👋 <b>{name}</b>\n💰 {PRICE_KK} грн = 1 KK", kb.as_markup()

def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm_stats")
    kb.button(text="📣 Рассылка", callback_data="adm_bc")
    kb.button(text="🎁 Промокод", callback_data="adm_promo")
    kb.button(text="💸 Выводы", callback_data="adm_withdraws")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

# ================= START =================
@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id

    cur.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cur.fetchone():
        ref = None
        if "ref_" in m.text:
            try:
                ref = int(m.text.split("ref_")[1])
                if ref != uid:
                    cur.execute("UPDATE users SET refs=refs+1 WHERE id=?", (ref,))
            except: pass
        cur.execute("INSERT INTO users(id, ref_id) VALUES(?,?)", (uid, ref))
        db.commit()

    text, kb = main_menu(m.from_user.first_name)
    await m.answer(text, reply_markup=kb)

# ================= BUY =================
@dp.callback_query(F.data=="buy")
async def buy(c: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for k,v in SERVERS.items():
        kb.button(text=f"{v} [{k}]", callback_data=f"srv_{k}")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(4)
    await state.clear()
    await c.message.edit_text("🌍 Выберите сервер", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("srv_"))
async def srv(c: types.CallbackQuery, state: FSMContext):
    sid = c.data.split("_")[1]
    await state.update_data(server=SERVERS[sid])
    await state.set_state(Buy.amount)
    await c.message.edit_text("🔢 Введите KK")

@dp.message(F.text, Buy.amount)
async def amount(m: types.Message, state: FSMContext):
    try:
        kk = float(m.text)
        if kk < 1: raise
    except:
        return await m.answer("❌ Число больше 1")

    await state.update_data(kk=kk, price=kk*PRICE_KK)
    await state.set_state(Buy.promo)
    await m.answer("🎁 Промокод или '-'")

@dp.message(F.text, Buy.promo)
async def promo(m: types.Message, state: FSMContext):
    data = await state.get_data()
    code = m.text.upper()
    price = data["price"]

    if code != "-":
        cur.execute("SELECT discount FROM promos WHERE code=? AND active=1", (code,))
        p = cur.fetchone()
        if not p:
            return await m.answer("❌ Нет такого промо")
        cur.execute("SELECT 1 FROM promo_uses WHERE user_id=? AND code=?", (m.from_user.id, code))
        if cur.fetchone():
            return await m.answer("❌ Вы уже использовали")
        price *= (100-p[0])/100
        await state.update_data(promo=code)

    await state.update_data(price=round(price,2))
    await state.set_state(Buy.nick)
    await m.answer("🎮 Никнейм")

@dp.message(F.text, Buy.nick)
async def nick(m: types.Message, state: FSMContext):
    await state.update_data(nick=m.text)
    d = await state.get_data()
    await state.set_state(Buy.proof)
    await m.answer(
        f"💰 {d['kk']} KK = <b>{d['price']} грн</b>\n"
        f"💳 <code>{CARD}</code>\n📸 Чек"
    )

@dp.message(F.photo, Buy.proof)
async def proof(m: types.Message, state: FSMContext):
    d = await state.get_data()
    uid = m.from_user.id

    cur.execute(
        "INSERT INTO orders(user_id,type,info,price,date) VALUES(?,?,?,?,?)",
        (uid,"virts",json.dumps(d),d["price"],datetime.now().isoformat())
    )

    if d.get("promo"):
        cur.execute("INSERT OR IGNORE INTO promo_uses VALUES(?,?)", (uid,d["promo"]))

    cur.execute("SELECT ref_id FROM users WHERE id=?", (uid,))
    ref = cur.fetchone()[0]
    if ref:
        bonus = (d["price"]/PRICE_KK)*REF_PERCENT
        cur.execute("UPDATE users SET balance=balance+? WHERE id=?", (bonus,ref))

    db.commit()

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполнено", callback_data=f"ord_ok_{uid}")
    kb.button(text="❌ Отказ", callback_data=f"ord_no_{uid}")
    kb.adjust(2)

    if ADMIN_ID:
        await bot.send_photo(
            ADMIN_ID, m.photo[-1].file_id,
            caption=f"🛒 Заказ от {uid}\n{d}",
            reply_markup=kb.as_markup()
        )

    await m.answer("✅ Принято")
    await state.clear()

# ================= ADMIN =================
@dp.callback_query(F.data=="admin")
async def admin(c: types.CallbackQuery):
    if c.from_user.id!=ADMIN_ID: return
    await c.message.edit_text("👑 Админка", reply_markup=admin_menu())

@dp.callback_query(F.data=="adm_stats")
async def stats(c: types.CallbackQuery):
    if c.from_user.id!=ADMIN_ID: return
    cur.execute("SELECT COUNT(*) FROM users")
    u=cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders")
    o=cur.fetchone()[0]
    await c.message.edit_text(f"📊 Users: {u}\n🛒 Orders: {o}", reply_markup=admin_menu())

@dp.callback_query(F.data=="adm_bc")
async def bc(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id!=ADMIN_ID: return
    await state.set_state(AdminFSM.broadcast)
    await c.message.edit_text("📣 Текст рассылки")

@dp.message(AdminFSM.broadcast)
async def bc_send(m: types.Message, state: FSMContext):
    if m.from_user.id!=ADMIN_ID: return
    cur.execute("SELECT id FROM users")
    for (uid,) in cur.fetchall():
        try: await bot.send_message(uid, m.text)
        except: pass
    await state.clear()
    await m.answer("✅ Готово")

# ================= REF =================
@dp.callback_query(F.data=="ref")
async def ref(c: types.CallbackQuery):
    cur.execute("SELECT refs,balance FROM users WHERE id=?", (c.from_user.id,))
    r,b=cur.fetchone()
    link=f"https://t.me/{(await bot.me()).username}?start=ref_{c.from_user.id}"

    kb=InlineKeyboardBuilder()
    if b>=MIN_WITHDRAW_KK:
        kb.button(text="💸 Вывести KK", callback_data="withdraw")
    kb.button(text="🔙 Назад", callback_data="back")

    await c.message.edit_text(
        f"🤝 Рефералка\n👥 {r}\n💰 {b:.2f} KK\n🔗 {link}",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data=="withdraw")
async def withdraw(c: types.CallbackQuery):
    cur.execute("SELECT balance FROM users WHERE id=?", (c.from_user.id,))
    b=cur.fetchone()[0]
    if b<MIN_WITHDRAW_KK:
        return await c.answer("❌ Минимум 10 KK", show_alert=True)

    cur.execute("INSERT INTO withdraws(user_id,amount) VALUES(?,?)",(c.from_user.id,b))
    cur.execute("UPDATE users SET balance=0 WHERE id=?", (c.from_user.id,))
    db.commit()

    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, f"💸 Вывод {b} KK от {c.from_user.id}")

    await c.message.edit_text("✅ Заявка отправлена")

# ================= BACK =================
@dp.callback_query(F.data=="back")
async def back(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    t,k=main_menu(c.from_user.first_name)
    await c.message.edit_text(t, reply_markup=k)

# ================= WEB =================
async def handle(req): return web.Response(text="OK")

async def main():
    app=web.Application()
    app.router.add_get("/",handle)
    runner=web.AppRunner(app)
    await runner.setup()
    site=web.TCPSite(runner,"0.0.0.0",int(os.getenv("PORT",8080)))
    await asyncio.gather(dp.start_polling(bot), site.start())

if __name__=="__main__":
    asyncio.run(main())
