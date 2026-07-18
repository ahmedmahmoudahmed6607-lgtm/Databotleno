import asyncio
import logging
import aiosqlite
import datetime
import os
import aiohttp
import html
from aiogram import Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ══════════════════════════════════════
# 💾 ذاكرة الكاش المؤقتة للبث والمجموعات
# ══════════════════════════════════════
mg_buf = {}      
mg_meta = {}     
mg_timers = {}   

SETTINGS_CACHE = {}
SUB_CACHE = {}
SUB_CACHE_TTL = 300  # 5 دقايق بدل 15 ثانية لتخفيف الضغط على Telegram API

# ══════════════════════════════════════
# ⚙️ الإعدادات العامة للبوت
# ══════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "8657973094:AAHURWh7s0kTjJO38MIDzwczkuuZHmz5Zd8")
ADMIN_ID  = 7916842400
DB_PATH   = "bot_data.db"

# ══════════════════════════════════════
# 🌟 نظام التعبيرات والإيموجي المخصص
# ══════════════════════════════════════
E_FALLBACK = {
    "5355180574313060180": "⭐", "5357272206206342962": "🔥", "5354797987216265138": "💎",
    "5357581641420143839": "👑", "5357169569372866445": "⚡", "5355057446190613905": "✅",
    "5355023563193619708": "🔒", "5355332431471748210": "➡️", "5355200176543799124": "💸",
    "5354973921961611463": "🔔", "5204242830687494041": "🛡️", "5377336227533969892": "👋",
    "5472250091332993630": "🚀", "5235794253149394263": "👁️", "5461128651477111908": "🔑",
    "5215420556089776398": "❤️", "5381975814415866082": "🎁", "5462902520215002477": "🌙",
    "5472239203590888751": "☀️", "5400090058030075645": "☁️"
}

def ce(eid): 
    fallback = E_FALLBACK.get(eid, "⭐")
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'

E = {
    "star": "5355180574313060180",
    "fire": "5357272206206342962",
    "diamond": "5354797987216265138",
    "crown": "5357581641420143839",
    "flash": "5357169569372866445",
    "check": "5355057446190613905",
    "lock": "5355023563193619708",
    "arrow": "5355332431471748210",
    "money": "5355200176543799124",
    "bell": "5354973921961611463",
    "shield": "5204242830687494041",
    "wave": "5377336227533969892",
    "rocket": "5472250091332993630",
    "eye": "5235794253149394263",
    "key": "5461128651477111908",
    "heart": "5215420556089776398",
    "gift": "5381975814415866082",
    "moon": "5462902520215002477",
    "sun": "5472239203590888751",
    "cloud": "5400090058030075645"
}

# ══════════════════════════════════════
# 🔍 فك وترميز بيانات الرقم القومي
# ══════════════════════════════════════
def parse_nid(nid):
    if not nid.isdigit() or len(nid) != 14: return None
    c = int(nid[0]); y_p = "19" if c == 2 else "20" if c == 3 else None
    if not y_p: return None
    y, m, d, gov_c, gen_c = y_p + nid[1:3], nid[3:5], nid[5:7], nid[7:9], int(nid[12])
    v_m = {
        '01':'القاهرة','02':'الإسكندرية','03':'بورسعيد','04':'السويس','11':'دمياط','12':'الدقهلية','13':'الشرقية','14':'القليوبية',
        '15':'كفر الشيخ','16':'الغربية','17':'المنوفية','18':'البحيرة','19':'الإسماعيلية','21':'الجيزة','22':'بني سويف','23':'الفيوم',
        '24':'المنيا','25':'أسيوط','26':'سوهاج','27':'قنا','28':'أسوان','29':'الأقصر','31':'البحر الأحمر','32':'الوادي الجديد',
        '33':'مطروح','34':'شمال سيناء','35':'جنوب سيناء','88':'خارج مصر'
    }
    gov, gen = v_m.get(gov_c, "غير معروف"), ("ذكر" if gen_c % 2 != 0 else "أنثى")
    try:
        b_d = datetime.datetime(int(y), int(m), int(d))
        age = datetime.datetime.now().year - b_d.year - ((datetime.datetime.now().month, datetime.datetime.now().day) < (b_d.month, b_d.day))
    except: return None
    return {"y":y, "m":m, "d":d, "gov":gov, "gen":gen, "age":age}

# ══════════════════════════════════════
# 🗄️ قاعدة البيانات (Async + WAL Mode)
# ══════════════════════════════════════
_db = None
db_lock = asyncio.Lock()  

async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA synchronous=NORMAL")
        await _db.execute("PRAGMA cache_size=10000")
        await _db.execute("PRAGMA temp_store=MEMORY")
    else:
        try:
            await _db.execute("SELECT 1")
        except Exception:
            try:
                await _db.close()
            except:
                pass
            _db = await aiosqlite.connect(DB_PATH)
            _db.row_factory = aiosqlite.Row
            await _db.execute("PRAGMA journal_mode=WAL")
            await _db.execute("PRAGMA synchronous=NORMAL")
            await _db.execute("PRAGMA cache_size=10000")
            await _db.execute("PRAGMA temp_store=MEMORY")
    return _db

async def preload_settings():
    global SETTINGS_CACHE
    try:
        db = await get_db()
        async with db.execute("SELECT key, value FROM settings") as c:
            rows = await c.fetchall()
            for r in rows:
                SETTINGS_CACHE[r['key']] = r['value']
        logging.info("Settings cache preloaded successfully.")
    except Exception as e:
        logging.error(f"Error preloading settings: {e}")

async def db_init():
    async with db_lock:
        db = await get_db()
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS sections (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, status TEXT DEFAULT 'open', color TEXT, emoji TEXT);
            CREATE TABLE IF NOT EXISTS section_cash (section_id INTEGER PRIMARY KEY, cash_number TEXT);
            CREATE TABLE IF NOT EXISTS section_admins (section_id INTEGER, admin_id INTEGER, PRIMARY KEY (section_id, admin_id));
            CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, full_name TEXT, section_name TEXT, section_price INTEGER, screenshot_id TEXT, phone_number TEXT, status TEXT DEFAULT 'pending', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, section_id INTEGER, quantity INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, joined_at DATETIME DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS force_channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, title TEXT);
            CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, added_at DATETIME DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS request_messages (req_id INTEGER, admin_id INTEGER, message_id INTEGER, PRIMARY KEY (req_id, admin_id));
            CREATE TABLE IF NOT EXISTS trust_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, req_id INTEGER, user_name TEXT, section_name TEXT, section_price INTEGER, quantity INTEGER, posted_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        """)
        try:
            async with db.execute("SELECT color FROM sections LIMIT 1") as cursor: pass
        except Exception:
            await db.execute("ALTER TABLE sections ADD COLUMN color TEXT")
            await db.execute("ALTER TABLE sections ADD COLUMN emoji TEXT")
            
        try:
            async with db.execute("SELECT url FROM force_channels LIMIT 1") as cursor: pass
        except Exception:
            await db.execute("ALTER TABLE force_channels ADD COLUMN url TEXT")

        try:
            async with db.execute("SELECT quantity FROM requests LIMIT 1") as cursor: pass
        except Exception:
            await db.execute("ALTER TABLE requests ADD COLUMN quantity INTEGER DEFAULT 1")

        try:
            async with db.execute("SELECT id FROM trust_posts LIMIT 1") as cursor: pass
        except Exception:
            await db.execute("CREATE TABLE IF NOT EXISTS trust_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, req_id INTEGER, user_name TEXT, section_name TEXT, section_price INTEGER, quantity INTEGER, posted_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

        await db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('trust_channel_id','')")
        await db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('trust_posts_enabled','1')")
        
        defs = {
            "cash_number": "01000000000",
            "trust_channel": "@trust_channel",
            "trust_channel_id": "",
            "support_username": "@support_admin",
            "welcome_message": (
                f"{ce(E['star'])} <b>أهلاً وسهلاً بك عزيزي العميل {{name}}</b> {ce(E['star'])}\n"
                f"أنت الآن داخل بوت استخراج البيانات الخاص بـ <b>L. G</b> {ce(E['diamond'])}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<blockquote>{ce(E['check'])} <b>للحفاظ على سلامة حسابك، يرجى الالتزام بما يلي</b> {ce(E['lock'])}</blockquote>\n"
                f"1 · تجنّب تكرار نفس الطلب أكثر من مرة {ce(E['shield'])}\n"
                f"2 · تأكد من إرسال جميع البيانات المطلوبة بشكل صحيح {ce(E['check'])}\n"
                f"3 · لا ترسل بيانات المحفظة إلا عند الحاجة الفعلية {ce(E['money'])}\n"
                f"4 · الصبر مطلوب، طلبك سيُعالج بالترتيب {ce(E['flash'])}\n"
                f"5 · يُمنع إرسال رسائل خارج نطاق البوت في الدعم {ce(E['bell'])}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<blockquote>{ce(E['check'])} <b>خطوات تقديم الطلب</b> {ce(E['arrow'])}</blockquote>\n"
                f"① · اختار عايز تسحب على كام رقم\n"
                f"② · هيظهرلك رقم الكاش اللي هتحول عليه\n"
                f"③ · ابعت سكرين التحويل\n"
                f"④ · ابعت الرقم اللي حولت منه\n"
                f"⑤ · ابعت الرقم اللي هتسحب عليه\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>سيتم مراجعة طلبك فوراً بعد الإرسال، فقط انتظر قليلاً</i>"
            ),
            "welcome_photo": ""
        }
        for k, v in defs.items(): await db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        
        # التأكد من وجود قسم معلومات الرقم القومي
        async with db.execute("SELECT id FROM sections WHERE name=?", ("معلومات رقم قومي",)) as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO sections(name,price) VALUES(?,?)", ("معلومات رقم قومي", 10))
        
        await db.commit()
    await preload_settings()

async def q(sql, p=(), all=False):
    global _db
    is_write = not sql.strip().upper().startswith("SELECT")
    async with db_lock:
        db = await get_db()
        try:
            async with db.execute(sql, p) as c:
                r = await c.fetchall() if all else await c.fetchone()
            if is_write:
                await db.commit()
            return r
        except Exception as e:
            logging.error(f"Database error on query '{sql}': {e}")
            try:
                await _db.close()
            except:
                pass
            _db = None
            raise e

async def gs(k):
    if k in SETTINGS_CACHE:
        return SETTINGS_CACHE[k]
    r = await q("SELECT value FROM settings WHERE key=?", (k,))
    val = r['value'] if r else ""
    SETTINGS_CACHE[k] = val
    return val

async def ss(k, v):
    await q("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, v))
    SETTINGS_CACHE[k] = v

async def is_own(u): return u == ADMIN_ID
async def is_adm(u):
    if u == ADMIN_ID: return True
    r = await q("SELECT id FROM admins WHERE id=?", (u,)); return r is not None
async def is_sec_adm(u, sid):
    if await is_own(u): return True
    r = await q("SELECT 1 FROM section_admins WHERE section_id=? AND admin_id=?", (sid, u)); return r is not None
async def get_sec_cash(sid):
    r = await q("SELECT cash_number FROM section_cash WHERE section_id=?", (sid,)); return r['cash_number'] if r else await gs("cash_number")

# ══════════════════════════════════════
# 💬 دوال مساعدة في تعديل وإرسال الرسائل
# ══════════════════════════════════════
async def edit_or_reply(c: CallbackQuery, text: str, reply_markup=None):
    if not c.message.text:
        try: await c.message.delete()
        except: pass
        return await c.message.answer(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        try:
            return await c.message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            if "message is not modified" in str(e):
                return c.message
            try: await c.message.delete()
            except: pass
            return await c.message.answer(text, parse_mode="HTML", reply_markup=reply_markup)

async def post_trust_channel(bot: Bot, req_id: int, user_name: str, section_name: str, section_price: int, quantity: int):
    try:
        ch_id = await gs("trust_channel_id")
        if not ch_id or not str(ch_id).strip():
            logging.info(f"trust_channel_id not set, skipping post for req #{req_id}")
            return
        
        now = datetime.datetime.now().strftime("%Y/%m/%d — %I:%M %p")
        qty_txt = f"{quantity} أرقام" if quantity > 1 else "رقم واحد"
        safe_user_name = html.escape(str(user_name))
        safe_section_name = html.escape(str(section_name))
        msg_txt = (
            f"{ce(E['check'])} {ce(E['star'])} <b>تم التسليم بنجاح</b> {ce(E['star'])}\n\n"
            f"{ce(E['crown'])} <b>اسم العميل:</b> {safe_user_name}\n"
            f"{ce(E['diamond'])} <b>القسم:</b> {safe_section_name}\n"
            f"{ce(E['fire'])} <b>العدد:</b> {qty_txt}\n"
            f"{ce(E['money'])} <b>المبلغ:</b> <code>{section_price} جنيه</code>\n"
            f"{ce(E['shield'])} <b>الحالة:</b> <i>تم التسليم</i> {ce(E['check'])}\n"
            f"{ce(E['bell'])} <b>الوقت:</b> <code>{now}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{ce(E['gift'])} <b>شكراً لثقتك بنا — L. G</b> {ce(E['heart'])}"
        )
        
        cid = int(ch_id.strip()) if str(ch_id).strip().lstrip('-').isdigit() else ch_id.strip()
        await bot.send_message(cid, msg_txt, parse_mode="HTML")
        await q("INSERT INTO trust_posts(req_id,user_name,section_name,section_price,quantity) VALUES(?,?,?,?,?)",
                (req_id, user_name, section_name, section_price, quantity))
        logging.info(f"✅ trust_channel post sent for req #{req_id}")
    except Exception as e:
        logging.error(f"❌ trust_channel post FAILED for req #{req_id}: {e}")

# ══════════════════════════════════════
# 🧠 الحالات (FSM States)
# ══════════════════════════════════════
class S(StatesGroup):
    wait_val = State(); wait_screenshot = State(); wait_phone = State(); wait_target = State(); admin_reply = State()

# ══════════════════════════════════════
# ⌨️ لوحات المفاتيح والأزرار التفاعلية
# ══════════════════════════════════════
def back_kb(d="adm_back"):
    kb = InlineKeyboardBuilder(); kb.button(text="🔙 رجوع", callback_data=d, style="danger"); return kb.as_markup()

async def get_admin_kb(uid):
    kb = InlineKeyboardBuilder()
    if await is_own(uid):
        kb.button(text="➕ اضافة قسم", callback_data="adm_add_sec", style="primary")
        kb.button(text="📋 ادارة الاقسام", callback_data="adm_sections", style="primary")
        kb.button(text="💸 تغيير رقم الكاش", callback_data="adm_cash", style="primary")
        u_count = (await q("SELECT COUNT(*) FROM users"))[0]
        kb.button(text=f"📢 اذاعة ({u_count})", callback_data="adm_broadcast", style="primary")
        kb.button(text="✏️ رسالة الترحيب", callback_data="adm_welcome_msg", style="primary")
        kb.button(text="🖼️ صورة الترحيب", callback_data="adm_welcome_photo", style="primary")
        kb.button(text="🔗 قناة الثقة", callback_data="adm_trust", style="primary")
        kb.button(text="📢 قناة التسليمات", callback_data="adm_trust_post_ch", style="primary")
        kb.button(text="👤 حساب الدعم", callback_data="adm_support", style="primary")
        kb.button(text="👥 المستخدمين", callback_data="adm_users", style="primary")
        kb.button(text="📊 الاحصائيات", callback_data="adm_stats", style="primary")
        kb.button(text="📣 الاشتراك الاجباري", callback_data="adm_force", style="primary")
        kb.button(text="🚨 الطلبات المعلقة", callback_data="adm_pending", style="primary")
        kb.button(text="👮 ادارة الادمنز", callback_data="adm_admins", style="primary")
    else:
        kb.button(text="📋 أقسامي", callback_data="adm_mysecs", style="primary")
        kb.button(text="🚨 طلباتي المعلقة", callback_data="adm_mypending", style="primary")
    kb.adjust(2); return kb.as_markup()

async def get_home_kb():
    kb = InlineKeyboardBuilder()
    rows = await q("SELECT id, name, status, color, emoji FROM sections", all=True)
    for r in rows:
        text = f"{r['emoji']} {r['name']}" if r['emoji'] else r['name']
        if r['status'] != 'open': text = f"🔒 {text}"
        kb.row(InlineKeyboardButton(text=text, callback_data=f"sec_{r['id']}", style="primary"))
    kb.row(InlineKeyboardButton(text="🏢 تواصل مع الشركات", callback_data="contact_companies", style="primary"))
    kb.row(InlineKeyboardButton(text="📊 احصائياتي", callback_data="my_stats", style="primary"))
    kb.row(InlineKeyboardButton(text="📣 قناة الثقة", url=f"https://t.me/{(await gs('trust_channel')).lstrip('@')}", style="primary"),
           InlineKeyboardButton(text="💬 تواصل مع الدعم", url=f"https://t.me/{(await gs('support_username')).lstrip('@')}", style="primary"))
    return kb.as_markup()

def get_companies_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 فودافون", callback_data="comp_voda", style="primary")
    kb.button(text="🟠 أورنج", callback_data="comp_orange", style="primary")
    kb.button(text="🟢 اتصالات", callback_data="comp_etisalat", style="primary")
    kb.button(text="🔴 وي", callback_data="comp_we", style="primary")
    kb.button(text="🔙 رجوع", callback_data="go_home", style="danger")
    kb.adjust(2, 2, 1); return kb.as_markup()

# ══════════════════════════════════════
# 📣 معالجة الاشتراك الإجباري والعبور الآمن
# ══════════════════════════════════════
router = Router()

async def check_sub(bot: Bot, uid: int):
    if await is_adm(uid):
        return []
        
    now = datetime.datetime.now().timestamp()
    if uid in SUB_CACHE:
        ts, cached_val = SUB_CACHE[uid]
        if now - ts < SUB_CACHE_TTL:
            return cached_val

    chans = await q("SELECT channel, title, url FROM force_channels", all=True)
    if not chans:
        SUB_CACHE[uid] = (now, [])
        return []
        
    async def check(row):
        ch = row['channel']
        try:
            chat_id = int(ch) if str(ch).lstrip('-').isdigit() else ch
            # وضع حد أقصى للانتظار 5 ثوانٍ لمنع تهنيج البوت وتوقف استجابته
            m = await asyncio.wait_for(bot.get_chat_member(chat_id, uid), timeout=2.0)
            status = m.status.value if hasattr(m.status, 'value') else m.status
            if status in ["left", "kicked"]: return row
            return None  # مشترك
        except asyncio.TimeoutError:
            logging.error(f"Timeout checking subscription for user {uid} in channel {ch}")
            # Fail-Open: لا نمنع العميل من الدخول في حال بطء أو انقطاع تليجرام مؤقتاً
            return None
        except Exception as e:
            logging.warning(f"check_sub error for channel {ch}: {e}")
            # Fail-Open: لو البوت اتحذف منه أدمن أو تعطلت إعدادات القناة لا نقوم بقفل البوت للجميع
            return None
            
    results = await asyncio.gather(*(check(r) for r in chans))
    not_joined = [r for r in results if r]
    SUB_CACHE[uid] = (now, not_joined)
    return not_joined

async def send_home(msg, bot, user=None):
    u = user or msg.from_user
    w = (await gs("welcome_message")).replace("{name}", u.first_name if u else "أيها العميل")
    p, kb = await gs("welcome_photo"), await get_home_kb()
    if p:
        try: return await msg.answer_photo(p, caption=w, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to send welcome photo, resetting welcome_photo: {e}")
            await ss("welcome_photo", "")
    await msg.answer(w, reply_markup=kb, parse_mode="HTML")

# ══════════════════════════════════════
# 🚀 المعالجات (Handlers)
# ══════════════════════════════════════
@router.message(Command("start"))
async def cmd_start(msg: Message, bot: Bot, state: FSMContext):
    # تفريغ أي حالة مدخلات معلقة لمنع المشاكل والتعليق
    await state.clear()

    uid, u = msg.from_user.id, msg.from_user

    # تسجيل المستخدم لو جديد
    is_new = not await q("SELECT id FROM users WHERE id=?", (uid,))
    if is_new:
        await q("INSERT OR IGNORE INTO users(id,username,full_name) VALUES(?,?,?)", (uid, u.username or "", u.first_name or ""))
        total = (await q("SELECT COUNT(*) FROM users"))[0]
        try:
            await bot.send_message(ADMIN_ID, f"{ce(E['bell'])} <b>مستخدم جديد 🆕</b>\n\n👤 {u.first_name} (@{u.username or 'لا يوجد'})\n🆔 <code>{u.id}</code>\n👥 اجمالي المستخدمين: <b>{total}</b>", parse_mode="HTML")
        except Exception as e:
            logging.warning(f"Failed to send new user notification to admin {ADMIN_ID}: {e}")

    # ✅ الأدمن يدخل مباشرة بدون أي فحص اشتراك
    if await is_adm(uid):
        greeting = f"{ce(E['crown'])} <b>اهلا ادمن!</b>" if await is_own(uid) else f"{ce(E['shield'])} <b>اهلا مشرف!</b>"
        return await msg.answer(greeting, reply_markup=await get_admin_kb(uid), parse_mode="HTML")

    # مسح الكاش للعميل العادي فقط عند /start لإجبار فحص جديد
    SUB_CACHE.pop(uid, None)

    nj = await check_sub(bot, uid)
    if nj:
        kb = InlineKeyboardBuilder()
        for row in nj:
            ch, title, url = row['channel'], row['title'], row['url']
            if not url:
                if str(ch).startswith("@"):
                    url = f"https://t.me/{str(ch).lstrip('@')}"
                else:
                    url = f"https://t.me/c/{str(ch).replace('-100', '')}"
            kb.button(text=f"📣 {title or ch}", url=url, style="primary")
        kb.button(text="✅ اشتركت! تحقق", callback_data="check_sub", style="primary"); kb.adjust(1)
        return await msg.answer(f"{ce(E['bell'])} <b>يجب الاشتراك في القنوات التالية اولاً:</b>", parse_mode="HTML", reply_markup=kb.as_markup())

    await send_home(msg, bot)

@router.callback_query(F.data == "check_sub")
async def call_check(call: CallbackQuery, bot: Bot, state: FSMContext):
    # مسح الحالات المعلقة عند بدء الفحص الجديد
    await state.clear()
    uid = call.from_user.id
    SUB_CACHE.pop(uid, None)  # إفراغ الكاش للتحقق فوراً
    
    if await check_sub(bot, uid): 
        return await call.answer("❌ لسه مش مشترك في كل القنوات!", show_alert=True)
        
    await call.answer("✅ تم التحقق! اهلا بك")
    try: await call.message.delete()
    except: pass
    if await is_adm(uid):
        greeting = f"{ce(E['crown'])} <b>اهلا ادمن!</b>" if await is_own(uid) else f"{ce(E['shield'])} <b>اهلا مشرف!</b>"
        return await call.message.answer(greeting, reply_markup=await get_admin_kb(uid), parse_mode="HTML")
    await send_home(call.message, bot, call.from_user)

@router.callback_query(F.data == "my_stats")
async def my_stats(c: CallbackQuery):
    uid = c.from_user.id
    t = (await q("SELECT COUNT(*) FROM requests WHERE user_id=?", (uid,)))[0]
    a = (await q("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='accepted'", (uid,)))[0]
    p = (await q("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='pending'", (uid,)))[0]
    r = (await q("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='rejected'", (uid,)))[0]
    text = (f"{ce(E['star'])} <b>احصائياتك</b>\n\n"
            f"📋 اجمالي طلباتك: <b>{t}</b>\n"
            f"✅ مقبولة: <b>{a}</b>\n"
            f"⏳ معلقة: <b>{p}</b>\n"
            f"❌ مرفوضة: <b>{r}</b>")
    await edit_or_reply(c, text, reply_markup=back_kb("go_home"))

@router.callback_query(F.data == "go_home")
async def go_h(c: CallbackQuery, bot: Bot, state: FSMContext):
    # تنظيف حالة FSM تماماً عند العودة إلى القائمة الرئيسية
    await state.clear()
    try: await c.message.delete()
    except: pass
    await send_home(c.message, bot, c.from_user)

@router.callback_query(F.data == "contact_companies")
async def contact_comps(c: CallbackQuery):
    await edit_or_reply(c, f"{ce(E['star'])} <b>قسم التواصل مع الشركات</b>\n\nاختر الشركة التي تريد التواصل معها مباشرة:", reply_markup=get_companies_kb())

COMP_CONFIGS = {
    "voda": {"name": "فودافون", "chat_url": "https://web.vodafone.com.eg/ar/contact-us", "logo": "🔴", "color": "فودافون"},
    "orange": {"name": "أورنج", "chat_url": "https://www.orange.eg/ar/help/contact-us", "logo": "🟠", "color": "أورنج"},
    "etisalat": {"name": "اتصالات", "chat_url": "https://www.etisalat.eg/etisalat/portal/contact_us_ar", "logo": "🟢", "color": "اتصالات"},
    "we": {"name": "وي", "chat_url": "https://te.eg/wps/portal/te/Personal/Help", "logo": "🔴", "color": "وي"},
}

@router.callback_query(F.data.in_(["comp_voda", "comp_orange", "comp_etisalat", "comp_we"]))
async def comp_intro(c: CallbackQuery):
    comp = c.data.split("_")[1]; conf = COMP_CONFIGS[comp]
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🚀 فتح موقع {conf['name']} الرسمي", url=conf['chat_url'], style="primary")
    kb.button(text="🔙 رجوع", callback_data="contact_companies", style="danger")
    kb.adjust(1)
    text = (f"<b>أهلاً بك في قسم تواصل {conf['name']} 🤖</b>\n\n"
            f"لا توفر شركات الاتصالات إمكانية ربط الشات الخاص بها داخل تطبيقات أخرى (مثل تليجرام) لأسباب أمنية.\n\n"
            f"لذلك، اضغط على الزر بالأسفل للتوجه إلى الموقع الرسمي والتحدث مع خدمة العملاء الحقيقية لشركة {conf['name']}.")
    await edit_or_reply(c, text, reply_markup=kb.as_markup())

# ══════════════════════════════════════
# 🛒 نظام تدفق وإنشاء طلب سحب الداتا
# ══════════════════════════════════════
@router.callback_query(F.data.startswith("sec_"))
async def sec_sel(call: CallbackQuery, state: FSMContext, bot: Bot):
    if await check_sub(bot, call.from_user.id): return await call.answer("❌ اشترك اولا!", show_alert=True)
    sid = int(call.data.split("_")[1]); r = await q("SELECT * FROM sections WHERE id=?", (sid,))
    if not r or r['status'] != 'open': return await call.answer("🔒 هذا القسم مغلق حاليا!", show_alert=True)
    
    await state.update_data(sid=sid, name=r['name'], unit_price=r['price'])
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تأكيد واختيار العدد", callback_data=f"conf_order_{sid}", style="primary")
    kb.button(text="❌ إلغاء", callback_data="go_home", style="primary")
    kb.adjust(1)
    
    text = (f"{ce(E['diamond'])} <b>لقد اخترت قسم:</b> <code>{r['name']}</code>\n\n"
            f"{ce(E['money'])} <b>سعر الرقم الواحد:</b> <code>{r['price']} جنيه</code>\n\n"
            f"{ce(E['star'])} <b>هل تريد تأكيد الطلب والاستمرار؟</b>")
    await edit_or_reply(call, text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("conf_order_"))
async def conf_order(c: CallbackQuery, state: FSMContext):
    sid = int(c.data.split("_")[2])
    kb = InlineKeyboardBuilder()
    for i in range(1, 11): kb.button(text=str(i), callback_data=f"qty_order_{sid}_{i}", style="primary")
    kb.button(text="🔙 رجوع", callback_data=f"sec_{sid}", style="danger")
    kb.adjust(5, 5, 1)
    
    text = (f"{ce(E['rocket'])} <b>من فضلك حدد عدد الأرقام التي تريدها:</b>\n\n"
            f"{ce(E['fire'])} <i>يمكنك اختيار من 1 إلى 10 أرقام في الطلب الواحد.</i>")
    await edit_or_reply(c, text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("qty_order_"))
async def qty_order(c: CallbackQuery, state: FSMContext):
    p = c.data.split("_"); sid, qty = int(p[2]), int(p[3])
    r = await q("SELECT * FROM sections WHERE id=?", (sid,))
    if not r: return await c.answer("❌ القسم غير موجود!", show_alert=True)
    
    total = qty * r['price']; cash = await get_sec_cash(sid)
    await state.update_data(sid=sid, name=r['name'], unit_price=r['price'], qty=qty, total_price=total)
    await state.set_state(S.wait_screenshot)
    
    kb = InlineKeyboardBuilder(); kb.button(text="❌ إلغاء الطلب والعودة", callback_data="go_home", style="primary")
    
    text = (f"{ce(E['money'])} <b>فاتورة الطلب النهائي</b>\n\n"
            f"{ce(E['diamond'])} <b>القسم:</b> <code>{r['name']}</code>\n"
            f"{ce(E['star'])} <b>العدد:</b> <code>{qty} أرقام</code>\n"
            f"{ce(E['money'])} <b>المبلغ الإجمالي:</b> <code>{total} جنيه</code>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"{ce(E['flash'])} <b>يرجى تحويل المبلغ على الرقم التالي:</b>\n"
            f"📲 <code>{cash}</code>\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{ce(E['eye'])} <b>بعد التحويل، أرسل (سكرين شوت) الإيصال هنا 👇</b>")
    await edit_or_reply(c, text, reply_markup=kb.as_markup())

@router.message(S.wait_screenshot, F.photo)
async def get_sc(msg: Message, state: FSMContext):
    await state.update_data(sc=msg.photo[-1].file_id); await state.set_state(S.wait_phone)
    await msg.answer(f"{ce(E['check'])} <b>استلمنا السكرين!</b>\n\n{ce(E['arrow'])} دلوقتي ابعت <b>الرقم اللي حولت منه</b>:", parse_mode="HTML")

@router.message(S.wait_phone, F.text)
async def get_ph(msg: Message, state: FSMContext):
    await state.update_data(ph=msg.text); await state.set_state(S.wait_target)
    d = await state.get_data(); await msg.answer(f"{ce(E['check'])} <b>استلمنا الرقم!</b>\n\n{ce(E['arrow'])} دلوقتي ابعت <b>الرقم اللي عايز تسحب عليه {d['name']}</b>:", parse_mode="HTML")

@router.message(S.wait_target, F.text)
async def get_tg(msg: Message, state: FSMContext, bot: Bot):
    d, u = await state.get_data(), msg.from_user
    await q("INSERT INTO requests(user_id,username,full_name,section_name,section_price,screenshot_id,phone_number,section_id,quantity) VALUES(?,?,?,?,?,?,?,?,?)", (u.id, u.username or "", u.first_name or "", d['name'], d['total_price'], d['sc'], f"{d['ph']}|{msg.text}", d['sid'], d['qty']))
    rid = (await q("SELECT last_insert_rowid()"))[0]; await state.clear()
    await msg.answer(f"{ce(E['check'])} <b>تم ارسال طلبك للمشرفين!</b>\n\n{ce(E['rocket'])} سيتم الرد عليك قريباً", parse_mode="HTML")
    txt = (f"{ce(E['star'])} <b>طلب جديد #{rid}</b>\n\n"
           f"{ce(E['star'])} المستخدم: {u.first_name} (@{u.username or 'بدون'})\n"
           f"🆔 <code>{u.id}</code>\n"
           f"📂 القسم: {d['name']}\n"
           f"🔢 العدد: {d['qty']}\n"
           f"{ce(E['star'])} إجمالي المبلغ: {d['total_price']} جنيه\n"
           f"📞 رقم التحويل: <code>{d['ph']}</code>\n"
           f"🎯 الرقم التارجت: <code>{msg.text}</code>")
    
    if d['name'] == "معلومات رقم قومي":
        info = parse_nid(msg.text)
        if info:
            txt += (f"\n\n🔍 <b>تحليل تلقائي:</b>\n"
                   f"📅 مولود سنة كام: {info['y']} \n"
                   f"📆 شهر كام: {info['m']} \n"
                   f"🗓️ يوم كام: {info['d']} \n"
                   f"📍 منين: {info['gov']} \n"
                   f"👤 ذكر ولا انثي: {info['gen']} \n"
                   f"🎂 كام سنه: {info['age']} ")

    kb = InlineKeyboardBuilder(); kb.button(text="✅ قبول", callback_data=f"adm_acc_{rid}", style="primary"); kb.button(text="❌ رفض", callback_data=f"adm_rej_{rid}", style="primary")
    s_adms = await q("SELECT admin_id FROM section_admins WHERE section_id=?", (d['sid'],), all=True)
    for aid in {ADMIN_ID} | {a['admin_id'] for a in s_adms}:
        try:
            m = await bot.send_photo(aid, d['sc'], caption=txt, parse_mode="HTML", reply_markup=kb.as_markup())
            await q("INSERT INTO request_messages(req_id,admin_id,message_id) VALUES(?,?,?)", (rid, aid, m.message_id))
        except Exception as e:
            logging.warning(f"Failed to send request notification to admin {aid}: {e}")

# ══════════════════════════════════════
# 👮 لوحة التحكم وإجراءات المشرفين (Admin)
# ══════════════════════════════════════
@router.callback_query(F.data == "adm_broadcast")
async def adm_br(c: CallbackQuery, state: FSMContext):
    if not await is_own(c.from_user.id): return await c.answer("❌ غير مسموح لك!", show_alert=True)
    u_count = (await q("SELECT COUNT(*) FROM users"))[0]
    await state.set_state(S.wait_val); await state.update_data(act="broadcast")
    await edit_or_reply(c, f"{ce(E['star'])} <b>قسم الاذاعة للكل</b>\n\nعدد المستخدمين: <b>{u_count}</b>\n\nابعت الرسالة اللي عايز تذيعها دلوقتي (نص، صورة، فيديو، بصمة.. أي حاجة)\nسيتم ارسالها بنفس التنسيق والايموجي المميز.", reply_markup=back_kb())

@router.callback_query(F.data == "adm_back")
async def adm_b(c: CallbackQuery, state: FSMContext):
    await state.clear(); uid = c.from_user.id
    title = f"{ce(E['crown'])} <b>لوحة الادمن</b>" if await is_own(uid) else f"{ce(E['shield'])} <b>لوحة المشرف</b>"
    await edit_or_reply(c, title, reply_markup=await get_admin_kb(uid))

@router.callback_query(F.data == "adm_pending")
async def adm_p(c: CallbackQuery):
    if not await is_own(c.from_user.id): return await c.answer("❌ مش مسموح!", show_alert=True)
    secs = await q("SELECT id, name FROM sections", all=True); kb = InlineKeyboardBuilder()
    for s in secs:
        count = (await q("SELECT COUNT(*) FROM requests WHERE status='pending' AND section_id=?", (s['id'],)))[0]
        if count > 0: kb.button(text=f"{s['name']} ({count})", callback_data=f"adm_psec_{s['id']}", style="primary")
    
    uncat = (await q("SELECT COUNT(*) FROM requests WHERE status='pending' AND (section_id IS NULL OR section_id=0)"))[0]
    if uncat > 0: kb.button(text=f"⚠️ بدون قسم ({uncat})", callback_data="adm_psec_0", style="primary")
    
    kb.button(text="🔙 رجوع", callback_data="adm_back", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "🚨 الطلبات المعلقة حسب الأقسام:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("adm_psec_"))
async def adm_ps(c: CallbackQuery):
    if not await is_own(c.from_user.id): return await c.answer("❌ مش مسموح!", show_alert=True)
    sid = int(c.data.split("_")[2])
    if sid == 0: rows = await q("SELECT id, full_name, section_name FROM requests WHERE status='pending' AND (section_id IS NULL OR section_id=0)", all=True)
    else: rows = await q("SELECT id, full_name, section_name FROM requests WHERE status='pending' AND section_id=?", (sid,), all=True)
    kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"#{r['id']} | {r['full_name']}", callback_data=f"adm_view_{r['id']}", style="primary")
    kb.button(text="🔙 رجوع", callback_data="adm_pending", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "📋 اختر طلباً للمراجعة:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("adm_view_"))
async def adm_v(c: CallbackQuery):
    rid = int(c.data.split("_")[2]); r = await q("SELECT * FROM requests WHERE id=?", (rid,))
    if not r: return await c.answer("❌ الطلب غير موجود!", show_alert=True)
    if not await is_sec_adm(c.from_user.id, r['section_id']): return await c.answer("❌ مش مسموح!", show_alert=True)
    kb = InlineKeyboardBuilder(); kb.button(text="✅ قبول + ارسال البيانات", callback_data=f"adm_acc_{rid}", style="primary"); kb.button(text="❌ رفض", callback_data=f"adm_rej_{rid}", style="primary"); kb.button(text="🔙 رجوع", callback_data="adm_pending", style="danger"); kb.adjust(1)
    ph, target = r['phone_number'].split("|") if "|" in r['phone_number'] else (r['phone_number'], "غير معروف")
    txt = (f"{ce(E['star'])} <b>طلب #{rid}</b>\n\n"
           f"{ce(E['star'])} المستخدم: {r['full_name']} (@{r['username'] or 'بدون'})\n"
           f"🆔 <code>{r['user_id']}</code>\n"
           f"📂 القسم: {r['section_name']}\n"
           f"🔢 العدد: {r['quantity']}\n"
           f"{ce(E['star'])} إجمالي المبلغ: {r['section_price']} جنيه\n"
           f"📞 رقم التحويل: <code>{ph}</code>\n"
           f"🎯 الرقم التارجت: <code>{target}</code>")
    
    if r['section_name'] == "معلومات رقم قومي":
        info = parse_nid(target)
        if info:
            txt += (f"\n\n🔍 <b>تحليل تلقائي:</b>\n"
                   f"📅 مولود سنة كام: {info['y']} 😘\n"
                   f"📆 شهر كام: {info['m']} 😘\n"
                   f"🗓️ يوم كام: {info['d']} 😂😘\n"
                   f"📍 منين: {info['gov']} 😘\n"
                   f"👤 ذكر ولا انثي: {info['gen']} 😘\n"
                   f"🎂 كام سنه: {info['age']} 😘")

    if r['screenshot_id']: await c.message.answer_photo(r['screenshot_id'], caption=txt, parse_mode="HTML", reply_markup=kb.as_markup()); await c.message.delete()
    else: await edit_or_reply(c, txt, reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm_admins")
async def adm_adms(c: CallbackQuery):
    if not await is_own(c.from_user.id): return await c.answer("❌ مش مسموح!", show_alert=True)
    rows = await q("SELECT * FROM admins", all=True); kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"🗑️ حذف: {r['full_name'] or r['id']}", callback_data=f"adm_deladm_{r['id']}", style="primary")
    kb.button(text="➕ اضافة ادمن", callback_data="adm_addadm", style="primary"); kb.button(text="🔙 رجوع", callback_data="adm_back", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "👮 ادارة الادمنز العموميين:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm_addadm")
async def adm_aadm(c: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="add_admin")
    await edit_or_reply(c, "ابعت ID الادمن الجديد:", reply_markup=back_kb("adm_admins"))

@router.callback_query(F.data.startswith("adm_deladm_"))
async def adm_dadm(c: CallbackQuery):
    aid = int(c.data.split("_")[2]); await q("DELETE FROM admins WHERE id=?", (aid,)); await c.answer("✅ تم الحذف"); await adm_adms(c)

@router.callback_query(F.data == "adm_force")
async def adm_f(c: CallbackQuery):
    if not await is_own(c.from_user.id): return await c.answer("❌ مش مسموح!", show_alert=True)
    rows = await q("SELECT * FROM force_channels", all=True); kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"🗑️ {r['title']}", callback_data=f"adm_delf_{r['id']}", style="primary")
    kb.button(text="➕ اضافة قناة", callback_data="adm_addf", style="primary"); kb.button(text="🔙 رجوع", callback_data="adm_back", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "📣 الاشتراك الاجباري:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm_addf")
async def adm_af(c: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="add_force")
    await edit_or_reply(c, "ابعت يوزر أو رابط القناة/الجروب:\n\nأمثلة:\n• @channel_username\n• https://t.me/channel_username\n• -1001234567890\n\n📌 <b>للقنوات الخاصة:</b>\nضيف البوت كأدمن في القناة الأول، وبعدين <b>اعمل توجيه (Forward)</b> لرسالة من القناة هنا، والبوت هيحفظها تلقائياً ✅", reply_markup=back_kb("adm_force"))

@router.callback_query(F.data.startswith("adm_delf_"))
async def adm_df(c: CallbackQuery):
    fid = int(c.data.split("_")[2]); await q("DELETE FROM force_channels WHERE id=?", (fid,)); await c.answer("✅ تم الحذف"); await adm_f(c)

@router.callback_query(F.data == "adm_sections")
async def adm_s(c: CallbackQuery):
    if not await is_own(c.from_user.id): return await c.answer("❌ مش مسموح!", show_alert=True)
    rows = await q("SELECT * FROM sections", all=True); kb = InlineKeyboardBuilder()
    for r in rows:
        disp = f"{r['emoji']} {r['name']}" if r['emoji'] else r['name']
        kb.button(text=f"{'🟢' if r['status']=='open' else '🔴'} {disp}", callback_data=f"adm_secm_{r['id']}", style="primary")
    kb.button(text="➕ اضافة قسم", callback_data="adm_add_sec", style="primary"); kb.button(text="🔙 رجوع", callback_data="adm_back", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "📋 ادارة الاقسام:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("adm_secm_"))
async def adm_secm(c: CallbackQuery):
    sid = int(c.data.split("_")[2])
    r = await q("SELECT * FROM sections WHERE id=?", (sid,))
    # حماية: لو القسم اتحذف أو مش موجود
    if not r: return await c.answer("❌ القسم غير موجود!", show_alert=True)
    if not await is_sec_adm(c.from_user.id, sid): return await c.answer("❌ مش مسموح!", show_alert=True)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 اغلاق" if r['status']=='open' else "🟢 فتح", callback_data=f"adm_sectog_{sid}", style="primary")
    if await is_own(c.from_user.id):
        kb.button(text="👮 ادمنز القسم", callback_data=f"adm_secadms_{sid}", style="primary")
        kb.button(text="💸 تعيين كاش القسم", callback_data=f"adm_seccash_{sid}", style="primary")
        kb.button(text="💰 تغيير السعر", callback_data=f"adm_secprice_{sid}", style="primary")
        kb.button(text="✏️ تغيير اسم القسم", callback_data=f"adm_secname_{sid}", style="primary")
        kb.button(text="🗑️ حذف كاش القسم", callback_data=f"adm_secdelc_{sid}", style="primary")
        if r['name'] != "معلومات رقم قومي":
            kb.button(text="🗑️ حذف القسم", callback_data=f"adm_secdel_{sid}", style="primary")
        kb.button(text="🔙 رجوع", callback_data="adm_sections", style="danger")
    else:
        kb.button(text="🔙 رجوع", callback_data="adm_mysecs", style="danger")
    kb.adjust(1)
    try: await edit_or_reply(c, f"📂 <b>{r['name']}</b>\nالسعر: {r['price']}ج\nالحالة: {r['status']}", reply_markup=kb.as_markup())
    except: pass

@router.callback_query(F.data.startswith("adm_sectog_"))
async def adm_sectog(c: CallbackQuery):
    sid = int(c.data.split("_")[2]); r = await q("SELECT status FROM sections WHERE id=?", (sid,))
    new = 'close' if r['status']=='open' else 'open'; await q("UPDATE sections SET status=? WHERE id=?", (new, sid))
    await c.answer("✅ تم التغيير"); await adm_secm(c)

@router.callback_query(F.data == "adm_mysecs")
async def adm_mysecs(c: CallbackQuery):
    rows = await q("SELECT s.* FROM sections s JOIN section_admins sa ON s.id = sa.section_id WHERE sa.admin_id = ?", (c.from_user.id,), all=True)
    kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"{'🟢' if r['status']=='open' else '🔴'} {r['name']}", callback_data=f"adm_secm_{r['id']}", style="primary")
    kb.button(text="🔙 رجوع", callback_data="adm_back", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "📋 أقسامي المسؤل عنها:", reply_markup=kb.as_markup())

@router.callback_query(F.data == "adm_mypending")
async def adm_mypend(c: CallbackQuery):
    rows = await q("SELECT r.* FROM requests r JOIN section_admins sa ON r.section_id = sa.section_id WHERE sa.admin_id = ? AND r.status='pending'", (c.from_user.id,), all=True)
    kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"#{r['id']} | {r['full_name']}", callback_data=f"adm_view_{r['id']}", style="primary")
    kb.button(text="🔙 رجوع", callback_data="adm_back", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "🚨 طلبات أقسامي المعلقة:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("adm_acc_"))
async def adm_a(c: CallbackQuery, state: FSMContext, bot: Bot):
    rid = int(c.data.split("_")[2]); r = await q("SELECT * FROM requests WHERE id=?", (rid,))
    if not r or r['status'] != 'pending': return await c.answer("⚠️ معالج مسبقا", show_alert=True)
    if not await is_sec_adm(c.from_user.id, r['section_id']): return await c.answer("❌ مش مسموح!", show_alert=True)
    
    await q("UPDATE requests SET status='accepted' WHERE id=?", (rid,)); await c.answer("✅ تم القبول!")
    
    ms = await q("SELECT admin_id, message_id FROM request_messages WHERE req_id=?", (rid,), all=True)
    for m in ms: 
        try: await bot.edit_message_reply_markup(m['admin_id'], m['message_id'], reply_markup=None)
        except: pass
    
    if r['section_name'] == "معلومات رقم قومي":
        target = r['phone_number'].split("|")[1] if "|" in r['phone_number'] else r['phone_number']
        info = parse_nid(target)
        if info:
            res = (f"{ce(E['check'])} <b>تم قبول طلبك! إليك بيانات الرقم القومي:</b>\n\n"
                   f"📅 مولود سنة كام: <b>{info['y']}</b> 😘\n"
                   f"📆 شهر كام: <b>{info['m']}</b> 😘\n"
                   f"🗓️ يوم كام: <b>{info['d']}</b> 😂😘\n"
                   f"📍 منين: <b>{info['gov']}</b> 😘\n"
                   f"👤 ذكر ولا انثي: <b>{info['gen']}</b> 😘\n"
                   f"🎂 كام سنه: <b>{info['age']}</b> 😘")
            
            kb_u = InlineKeyboardBuilder()
            kb_u.button(text="✅ تم الاستلام", callback_data=f"cli_done_{rid}")
            
            await bot.send_message(r['user_id'], res, parse_mode="HTML", reply_markup=kb_u.as_markup())
            await post_trust_channel(bot, rid, r['full_name'], r['section_name'], r['section_price'], r['quantity'] or 1)
            await bot.send_message(c.from_user.id, f"{ce(E['check'])} <b>تم إرسال التحليل التلقائي للعميل بنجاح!</b>", parse_mode="HTML", reply_markup=await get_admin_kb(c.from_user.id))
            return

    await bot.send_message(r['user_id'], f"{ce(E['check'])} <b>تم قبول طلبك!</b>\n\n{ce(E['rocket'])} استنى.. البيانات هتوصلك دلوقتي", parse_mode="HTML"); await state.update_data(rid=rid, cid=r['user_id']); await state.set_state(S.admin_reply)
    await c.message.answer(f"{ce(E['arrow'])} <b>ابعت البيانات للعميل</b> (نص او صورة او اكتر من صورة) — طلب #{rid}:", parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_rej_"))
async def adm_rej(c: CallbackQuery, bot: Bot):
    rid = int(c.data.split("_")[2]); r = await q("SELECT user_id, section_id, status FROM requests WHERE id=?", (rid,))
    if not r or r['status'] != 'pending': return await c.answer("⚠️ معالج مسبقا", show_alert=True)
    if not await is_sec_adm(c.from_user.id, r['section_id']): return await c.answer("❌ مش مسموح!", show_alert=True)
    await q("UPDATE requests SET status='rejected' WHERE id=?", (rid,)); await c.answer("❌ تم الرفض")
    ms = await q("SELECT admin_id, message_id FROM request_messages WHERE req_id=?", (rid,), all=True)
    for m in ms: 
        try: await bot.edit_message_reply_markup(m['admin_id'], m['message_id'], reply_markup=None)
        except: pass
    sup = await gs("support_username")
    kb = InlineKeyboardBuilder(); kb.button(text="💬 تواصل مع الدعم", url=f"https://t.me/{sup.lstrip('@')}", style="primary")
    await bot.send_message(r['user_id'], f"{ce(E['shield'])} <b>تم رفض طلبك.</b>\n\nللاستفسار تواصل مع الدعم.", parse_mode="HTML", reply_markup=kb.as_markup())

@router.message(S.admin_reply)
async def adm_r(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data(); rid, cid = d['rid'], d['cid']
    kb = InlineKeyboardBuilder(); kb.button(text="✅ تم الاستلام", callback_data=f"cli_done_{rid}", style="primary"); kb.button(text="❌ في مشكلة", callback_data=f"cli_issue_{rid}", style="primary"); kb.adjust(2)
    
    if msg.media_group_id:
        mgid = msg.media_group_id
        if mgid not in mg_buf:
            mg_buf[mgid] = []; mg_meta[mgid] = {**d, "caption": msg.caption}
            async def flush(mid):
                await asyncio.sleep(2)
                files = mg_buf.pop(mid, []); meta = mg_meta.pop(mid, {})
                if not files: return
                media = [InputMediaPhoto(media=f) for f in files]
                cap = f"{ce(E['bell'])} <b>رد من الادارة على طلبك:</b>"
                if meta.get('caption'): cap += f"\n\n{meta['caption']}"
                media[0].caption = cap; media[0].parse_mode = "HTML"
                try:
                    await bot.send_media_group(meta['cid'], media)
                    await bot.send_message(meta['cid'], f"{ce(E['check'])} <b>تأكيد الاستلام:</b>", parse_mode="HTML", reply_markup=kb.as_markup())
                    await bot.send_message(ADMIN_ID, f"{ce(E['check'])} <b>تم ارسال الرد للعميل ({len(files)} صورة).</b>", parse_mode="HTML")
                    # نشر في قناة الثقة فور تسليم البيانات
                    req = await q("SELECT full_name, section_name, section_price, quantity FROM requests WHERE id=?", (meta['rid'],))
                    if req:
                        await post_trust_channel(bot, meta['rid'], req['full_name'], req['section_name'], req['section_price'], req['quantity'] or 1)
                except Exception as e:
                    logging.error(f"Failed to send media group reply to client: {e}")
                finally:
                    mg_timers.pop(mid, None)
                    await state.clear()
            mg_timers[mgid] = asyncio.create_task(flush(mgid))
        mg_buf[mgid].append(msg.photo[-1].file_id)
        return

    try:
        if msg.photo:
            cap = f"{ce(E['bell'])} <b>رد من الادارة على طلبك:</b>"
            if msg.caption: cap += f"\n\n{msg.caption}"
            await bot.send_photo(cid, msg.photo[-1].file_id, caption=cap, parse_mode="HTML", reply_markup=kb.as_markup())
        else: await bot.send_message(cid, f"{ce(E['bell'])} <b>رد من الادارة:</b>\n\n{msg.text}", parse_mode="HTML", reply_markup=kb.as_markup())
        await msg.answer(f"{ce(E['check'])} <b>تم ارسال الرد للعميل.</b>", parse_mode="HTML")
        # نشر في قناة الثقة فور تسليم البيانات
        req = await q("SELECT full_name, section_name, section_price, quantity FROM requests WHERE id=?", (rid,))
        if req:
            await post_trust_channel(bot, rid, req['full_name'], req['section_name'], req['section_price'], req['quantity'] or 1)
        await state.clear()
    except Exception as e:
        logging.error(f"Failed to send reply to client: {e}")
        await msg.answer("❌ فشل")

@router.callback_query(F.data.startswith("cli_done_"))
async def cli_d(c: CallbackQuery, bot: Bot):
    rid = int(c.data.split("_")[2])
    await c.answer("✅ تم تاكيد الاستلام! شكراً لتعاملك معنا.", show_alert=True)
    try: await c.message.edit_reply_markup(reply_markup=None)
    except: pass
    await bot.send_message(ADMIN_ID, f"{ce(E['check'])} <b>العميل اكد استلام طلب #{rid}</b>", parse_mode="HTML")

@router.callback_query(F.data == "adm_users")
async def adm_users(c: CallbackQuery):
    if not await is_own(c.from_user.id): return await c.answer("❌ مش مسموح!", show_alert=True)
    rows = await q("SELECT id, username, full_name, joined_at FROM users ORDER BY joined_at DESC LIMIT 20", all=True)
    total = (await q("SELECT COUNT(*) FROM users"))[0]
    txt = f"{ce(E['crown'])} <b>آخر 20 مستخدم</b> — إجمالي: <b>{total}</b>\n\n━━━━━━━━━━━━━━\n"
    for r in rows:
        name = r['full_name'] or "بدون اسم"
        un = f"@{r['username']}" if r['username'] else "بدون يوزر"
        txt += f"👤 {name} | {un} | <code>{r['id']}</code>\n"
    await edit_or_reply(c, txt, reply_markup=back_kb())

@router.callback_query(F.data == "adm_stats")
async def adm_st(c: CallbackQuery):
    if not await is_own(c.from_user.id): return
    counts = await q("SELECT (SELECT COUNT(*) FROM users) as u, (SELECT COUNT(*) FROM requests) as t, (SELECT COUNT(*) FROM requests WHERE status='pending') as p, (SELECT COUNT(*) FROM requests WHERE status='accepted') as a")
    u, t, p, a = counts['u'], counts['t'], counts['p'], counts['a']
    c_g = await gs("cash_number")
    secs = await q("""
        SELECT s.*, 
            (SELECT COUNT(*) FROM requests WHERE section_id=s.id) as st,
            (SELECT COUNT(*) FROM requests WHERE section_id=s.id AND status='accepted') as sa,
            (SELECT COUNT(*) FROM requests WHERE section_id=s.id AND status='pending') as sp,
            COALESCE(sc.cash_number, (SELECT value FROM settings WHERE key='cash_number')) as cash
        FROM sections s
        LEFT JOIN section_cash sc ON s.id = sc.section_id
    """, all=True)
    s_txt = ""
    for s in secs:
        disp = f"{s['emoji']} {s['name']}" if s['emoji'] else s['name']
        s_txt += f"\n📂 <b>{disp}</b> | كل: {s['st']} | ✅ {s['sa']} | ⏳ {s['sp']} | 💸 <code>{s['cash']}</code>"
    txt = (f"{ce(E['crown'])} <b>الاحصائيات</b>\n\n👥 المستخدمين: <b>{u}</b>\n📋 الطلبات الكلية: <b>{t}</b>\n⏳ معلقة: <b>{p}</b>\n✅ مقبولة: <b>{a}</b>\n"
           f"{ce(E['money'])} رقم الكاش العام: <code>{c_g}</code>\n\n━━━━━━━━━━━━━━\n<b>📊 إحصائيات الأقسام:</b>{s_txt}")
    await edit_or_reply(c, txt, reply_markup=back_kb())

@router.callback_query(F.data.startswith("cli_issue_"))
async def cli_issue(c: CallbackQuery, bot: Bot):
    rid = int(c.data.split("_")[2]); sup = await gs("support_username")
    kb = InlineKeyboardBuilder(); kb.button(text="💬 تواصل مع الدعم", url=f"https://t.me/{sup.lstrip('@')}", style="primary")
    txt = f"{ce(E['shield'])} <b>ناسف على المشكلة! تواصل مع الدعم.</b>"
    try:
        if c.message.caption: await c.message.edit_caption(caption=txt, parse_mode="HTML", reply_markup=kb.as_markup())
        else: await edit_or_reply(c, txt, reply_markup=kb.as_markup())
    except: pass
    await bot.send_message(ADMIN_ID, f"⚠️ <b>العميل ابلغ عن مشكلة في طلب #{rid}</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_secadms_"))
async def adm_sadms(c: CallbackQuery):
    sid = int(c.data.split("_")[2])
    rows = await q("SELECT a.* FROM admins a JOIN section_admins sa ON a.id = sa.admin_id WHERE sa.section_id = ?", (sid,), all=True)
    kb = InlineKeyboardBuilder()
    for r in rows: kb.button(text=f"🗑️ حذف: {r['full_name'] or r['id']}", callback_data=f"adm_rsadm_{sid}_{r['id']}", style="primary")
    kb.button(text="➕ اضافة ادمن للقسم", callback_data=f"adm_asadd_{sid}", style="primary")
    kb.button(text="🔙 رجوع", callback_data=f"adm_secm_{sid}", style="danger"); kb.adjust(1)
    await edit_or_reply(c, "👮 ادمنز هذا القسم:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("adm_rsadm_"))
async def adm_rsadm(c: CallbackQuery):
    p = c.data.split("_"); sid, aid = int(p[2]), int(p[3])
    await q("DELETE FROM section_admins WHERE section_id=? AND admin_id=?", (sid, aid))
    await c.answer("✅ تم الحذف"); await adm_sadms(c)

@router.callback_query(F.data.startswith("adm_asadd_"))
async def adm_asadd(c: CallbackQuery, state: FSMContext):
    sid = int(c.data.split("_")[2]); await state.set_state(S.wait_val)
    await state.update_data(act="add_sec_adm", sid=sid)
    await edit_or_reply(c, "ابعت ID الادمن المراد اضافته للقسم:", reply_markup=back_kb(f"adm_secadms_{sid}"))

@router.callback_query(F.data.startswith("adm_seccash_"))
async def adm_scash(c: CallbackQuery, state: FSMContext):
    sid = int(c.data.split("_")[2]); await state.set_state(S.wait_val)
    await state.update_data(act="set_sec_cash", sid=sid)
    await edit_or_reply(c, "ابعت رقم الكاش الجديد لهذا القسم:", reply_markup=back_kb(f"adm_secm_{sid}"))

@router.callback_query(F.data.startswith("adm_secprice_"))
async def adm_sprice(c: CallbackQuery, state: FSMContext):
    sid = int(c.data.split("_")[2]); await state.set_state(S.wait_val)
    await state.update_data(act="set_sec_price", sid=sid)
    await edit_or_reply(c, "ابعت السعر الجديد للقسم:", reply_markup=back_kb(f"adm_secm_{sid}"))

@router.callback_query(F.data.startswith("adm_secname_"))
async def adm_secname(c: CallbackQuery, state: FSMContext):
    sid = int(c.data.split("_")[2]); await state.set_state(S.wait_val)
    await state.update_data(act="set_sec_name", sid=sid)
    await edit_or_reply(c, "✏️ ابعت الاسم الجديد للقسم:", reply_markup=back_kb(f"adm_secm_{sid}"))

@router.callback_query(F.data.startswith("adm_secdelc_"))
async def adm_sdc(c: CallbackQuery):
    sid = int(c.data.split("_")[2]); await q("DELETE FROM section_cash WHERE section_id=?", (sid,))
    await c.answer("✅ تم حذف كاش القسم (سيتم استخدام العام)"); await adm_secm(c)

@router.callback_query(F.data.startswith("adm_secdel_"))
async def adm_sdel(c: CallbackQuery):
    sid = int(c.data.split("_")[2]); r = await q("SELECT name FROM sections WHERE id=?", (sid,))
    if r and r['name'] == "معلومات رقم قومي": return await c.answer("❌ لا يمكن حذف هذا القسم!", show_alert=True)
    await q("DELETE FROM sections WHERE id=?", (sid,))
    await q("DELETE FROM section_admins WHERE section_id=?", (sid,))
    await q("DELETE FROM section_cash WHERE section_id=?", (sid,))
    await c.answer("🗑️ تم حذف القسم"); await adm_s(c)

@router.callback_query(F.data == "adm_trust")
async def adm_t_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="set_trust")
    await edit_or_reply(call, "ابعت يوزر قناة الثقة (مثال: @channel):", reply_markup=back_kb())

@router.message(Command("debug_trust"))
async def cmd_debug_trust(msg: Message, bot: Bot):
    if msg.from_user.id != ADMIN_ID: return
    ch_id = await gs("trust_channel_id")
    ch_id_raw = repr(ch_id)
    is_empty = not ch_id or not str(ch_id).strip()
    result = f"🔍 <b>تشخيص قناة التسليمات</b>\n\n"
    result += f"القيمة المحفوظة: <code>{ch_id_raw}</code>\n"
    result += f"فاضية: <b>{'نعم ❌' if is_empty else 'لا ✅'}</b>\n\n"
    if not is_empty:
        cid_str = str(ch_id).strip()
        is_num = cid_str.lstrip('-').isdigit()
        cid = int(cid_str) if is_num else cid_str
        result += f"سيُرسل على: <code>{cid}</code>\n"
        result += f"نوع: {'numeric ID' if is_num else '@username'}\n\n"
        result += "🧪 جاري اختبار الإرسال..."
        await msg.answer(result, parse_mode="HTML")
        try:
            test_now = datetime.datetime.now().strftime("%Y/%m/%d — %I:%M %p")
            await bot.send_message(cid, f"✅ <b>رسالة تشخيص — قناة التسليمات تعمل!</b>\n⏰ <code>{test_now}</code>", parse_mode="HTML")
            await msg.answer("✅ <b>نجح الاختبار! القناة شغالة.</b>", parse_mode="HTML")
        except Exception as e:
            await msg.answer(f"❌ <b>فشل الاختبار:</b>\n<code>{e}</code>\n\nتأكد إن البوت ادمن في القناة.", parse_mode="HTML")
    else:
        result += "⚠️ لم يتم ضبط قناة التسليمات بعد!\nاستخدم زر 📢 قناة التسليمات من لوحة الأدمن."
        await msg.answer(result, parse_mode="HTML")

@router.callback_query(F.data == "adm_trust_post_ch")
async def adm_tpc_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="set_trust_post_ch")
    cur = await gs("trust_channel_id")
    cur_txt = f"\n\n⚙️ الحالي: <code>{cur}</code>" if cur else "\n\n⚙️ لم يتم الضبط بعد"
    await edit_or_reply(call, f"ابعت <b>ID قناة التسليمات</b> (مثال: <code>-1001234567890</code>)\nالبوت لازم يكون ادمن في القناة.{cur_txt}", reply_markup=back_kb())

@router.callback_query(F.data == "adm_support")
async def adm_s_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="set_support")
    await edit_or_reply(call, "ابعت يوزر الدعم (مثال: @user):", reply_markup=back_kb())

@router.callback_query(F.data == "adm_welcome_msg")
async def adm_w_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="set_welcome")
    await edit_or_reply(call, "ابعت رسالة الترحيب الجديدة:", reply_markup=back_kb())

@router.callback_query(F.data == "adm_welcome_photo")
async def adm_p_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="set_photo")
    await edit_or_reply(call, "ابعت صورة الترحيب الجديدة:", reply_markup=back_kb())

@router.callback_query(F.data == "adm_cash")
async def adm_c_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="set_cash")
    await edit_or_reply(call, "ابعت رقم الكاش العام الجديد:", reply_markup=back_kb())

@router.callback_query(F.data == "adm_add_sec")
async def adm_as_btn(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.wait_val); await state.update_data(act="add_sec_name")
    await edit_or_reply(call, "ابعت اسم القسم الجديد:", reply_markup=back_kb())

@router.callback_query(F.data.startswith("adm_color_"))
async def adm_color_sel(c: CallbackQuery, state: FSMContext):
    color = c.data.split("_")[2]
    await state.update_data(color=color, emoji="", act="add_sec_price")
    await edit_or_reply(c, "ابعت السعر الآن:")
    await c.answer()

@router.message(S.wait_val)
async def handle_val(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data(); txt = msg.text.strip() if msg.text else ""
    # حماية: لو الـ state فاضية أو مفيش مفتاح 'act' لسبب ما
    if not d or 'act' not in d:
        await state.clear()
        return
    if d['act'] == "broadcast":
        users = await q("SELECT id FROM users", all=True); s = 0
        status_msg = await msg.answer("⏳ جاري بدء الاذاعة...")
        from aiogram.exceptions import TelegramRetryAfter
        
        for idx, r in enumerate(users):
            uid = r['id']
            try:
                await msg.copy_to(uid)
                s += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.seconds)
                try:
                    await msg.copy_to(uid)
                    s += 1
                except Exception as ex:
                    logging.warning(f"Failed to broadcast to {uid} after retry: {ex}")
            except Exception as e:
                logging.warning(f"Failed to broadcast to {uid}: {e}")
            
            # Rate limit to avoid flood bans (max 20 messages per second)
            await asyncio.sleep(0.05)
            
            # Update progress status every 100 users
            if (idx + 1) % 100 == 0:
                try: await status_msg.edit_text(f"⏳ جاري الاذاعة... ({idx + 1}/{len(users)})\nتم الارسال لـ <b>{s}</b> مستخدم.", parse_mode="HTML")
                except: pass
                    
        await status_msg.edit_text(f"✅ تم الانتهاء من الاذاعة!\n\n👥 تم الارسال لـ <b>{s}</b> مستخدم من أصل <b>{len(users)}</b>.", parse_mode="HTML")
        await state.clear(); return
    elif d['act'] == "set_trust": await ss("trust_channel", txt); await msg.answer("✅ تم تحديث قناة الثقة"); await state.clear()
    elif d['act'] == "set_trust_post_ch":
        val = txt.strip()
        if not val.startswith("@") and not val.lstrip('-').isdigit():
            return await msg.answer("❌ لازم يكون @username أو Channel ID رقمي (مثال: -1001234567890)")
        await ss("trust_channel_id", val)
        saved = await gs("trust_channel_id")
        saved_str = str(saved).strip() if saved else ""
        if saved_str != val:
            await msg.answer(f"⚠️ خطأ في الحفظ! المحفوظ: <code>{repr(saved)}</code>", parse_mode="HTML")
            return
        try:
            cid = int(val) if val.lstrip('-').isdigit() else val
            await bot.send_message(cid, f"✅ <b>تم ربط قناة التسليمات بنجاح!</b>\nسيتم نشر كل تسليم هنا تلقائياً.", parse_mode="HTML")
            await msg.answer(f"✅ تم ضبط قناة التسليمات على <code>{val}</code>\n🧪 تم إرسال رسالة تجريبية للقناة!", parse_mode="HTML")
        except Exception as e:
            await msg.answer(f"⚠️ تم الحفظ لكن فشل الاختبار:\n<code>{e}</code>\nتأكد إن البوت ادمن في القناة.", parse_mode="HTML")
        await state.clear()
    elif d['act'] == "set_support": await ss("support_username", txt); await msg.answer("✅ تم تحديث حساب الدعم"); await state.clear()
    elif d['act'] == "set_welcome": await ss("welcome_message", txt); await msg.answer("✅ تم تحديث رسالة الترحيب"); await state.clear()
    elif d['act'] == "set_photo" and msg.photo: await ss("welcome_photo", msg.photo[-1].file_id); await msg.answer("✅ تم تحديث صورة الترحيب"); await state.clear()
    elif d['act'] == "set_cash": await ss("cash_number", txt); await msg.answer("✅ تم تحديث رقم الكاش العام"); await state.clear()
    elif d['act'] == "add_admin":
        if not txt.isdigit(): return await msg.answer("ارقام فقط!")
        try:
            chat = await bot.get_chat(int(txt))
            await q("INSERT INTO admins(id,username,full_name) VALUES(?,?,?)", (int(txt), chat.username or "", chat.first_name or ""))
            await msg.answer(f"✅ تم اضافة {chat.first_name}")
        except: await msg.answer("❌ فشل (تأكد ان المستخدم بدأ البوت)")
        await state.clear()
    elif d['act'] == "add_force":
        try:
            if msg.forward_from_chat:
                chat = msg.forward_from_chat
                stored_id = str(chat.id)
                chat_url = ""
                try:
                    full_chat = await bot.get_chat(chat.id)
                    if full_chat.username: chat_url = f"https://t.me/{full_chat.username}"
                    elif full_chat.invite_link: chat_url = full_chat.invite_link
                    else: chat_url = await bot.export_chat_invite_link(chat.id)
                except Exception as ex:
                    return await msg.answer(f"❌ فشل توليد الرابط للقناة الخاصة!\nالسبب: <code>{ex}</code>\n\nيرجى إعطاء البوت صلاحية <b>(إضافة مستخدمين / دعوة عبر الرابط)</b> في القناة، ثم المحاولة مرة أخرى.", parse_mode="HTML")
                
                if not chat_url: return await msg.answer("❌ البوت غير قادر على إنشاء رابط دعوة. يرجى التأكد من إعطاء البوت صلاحية دعوة المستخدمين.")
                
                await q("INSERT OR IGNORE INTO force_channels(channel,title,url) VALUES(?,?,?)", (stored_id, chat.title, chat_url))
                safe_title = html.escape(str(chat.title))
                return await msg.answer(f"✅ تم اضافة <b>{safe_title}</b> بنجاح من التوجيه\nالـ ID: <code>{chat.id}</code>\nالرابط: {html.escape(str(chat_url))}\n\n<i>ملاحظة: لتغيير الرابط لرابطك الخاص، احذف القناة وأضفها باستخدام اليوزر أو الرابط العام.</i>", parse_mode="HTML", disable_web_page_preview=True)

            if not txt: return await msg.answer("❌ رجاءً ابعت الرابط أو وجه رسالة من القناة.")
            chat_input = txt.strip(); chat_url = chat_input

            if "+" in chat_input or "joinchat" in chat_input:
                return await msg.answer("❌ روابط القنوات الخاصة لا يمكن للبوت التعرف على الـ ID الخاص بها للتحقق من الاشتراك.\n\n📌 <b>الحل:</b>\nأرسل توجيه (Forward) لرسالة من القناة الخاصة بدلاً من الرابط.")

            if "t.me/" in chat_input:
                chat_input = "@" + chat_input.split("t.me/")[-1].split("/")[0]
                chat_url = chat_url if chat_url.startswith("http") else "https://" + chat_url

            if chat_input.startswith("@"): chat_url = f"https://t.me/{chat_input.lstrip('@')}"
            get_id = int(chat_input) if chat_input.lstrip('-').isdigit() else chat_input
            
            try:
                chat = await bot.get_chat(get_id)
                chat_id = chat.id; chat_title = chat.title
            except Exception:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"https://api.telegram.org/bot{bot.token}/getChat", json={"chat_id": get_id}) as resp:
                        res = await resp.json()
                        if not res.get("ok"): raise Exception(res.get("description", "Unknown error"))
                        chat_id = res["result"]["id"]
                        chat_title = res["result"].get("title", str(get_id))

            stored_id = str(chat_id)
            if not chat_url.startswith("http"):
                if chat_input.startswith("@"): chat_url = f"https://t.me/{chat_input.lstrip('@')}"
                else:
                    try: chat_url = await bot.export_chat_invite_link(chat_id)
                    except Exception as ex: return await msg.answer(f"❌ فشل توليد الرابط!\nالسبب: <code>{str(ex)[:200]}</code>\n\nيرجى إعطاء البوت صلاحية <b>(إضافة مستخدمين)</b>.", parse_mode="HTML")
            
            await q("INSERT OR IGNORE INTO force_channels(channel,title,url) VALUES(?,?,?)", (stored_id, chat_title or chat_input, chat_url))
            safe_title = html.escape(str(chat_title or chat_input))
            await msg.answer(f"✅ تم اضافة <b>{safe_title}</b>\nالـ ID: <code>{chat_id}</code>\nالرابط الذي سيظهر في الزر: {html.escape(str(chat_url))}", parse_mode="HTML", disable_web_page_preview=True)
            await state.clear()
        except Exception as e:
            safe_e = html.escape(str(e))[:300] + "..."
            await msg.answer(f"❌ فشل: <code>{safe_e}</code>\n\n📌 <b>تأكد من التالي:</b>\n1. البوت أدمن في القناة.\n2. تأكد من صحة اليوزر أو الرابط.", parse_mode="HTML")
    elif d['act'] == "add_sec_adm":
        if not txt.isdigit(): return await msg.answer("ارقام فقط!")
        try:
            aid = int(txt); chat = await bot.get_chat(aid)
            await q("INSERT OR IGNORE INTO admins(id,username,full_name) VALUES(?,?,?)", (aid, chat.username or "", chat.first_name or ""))
            await q("INSERT OR IGNORE INTO section_admins(section_id,admin_id) VALUES(?,?)", (d['sid'], aid))
            await msg.answer(f"✅ تم اضافة {chat.first_name} للقسم")
        except:
            await msg.answer("❌ فشل")
        await state.clear()  # يتنفذ دايماً سواء نجح أو فشل
    elif d['act'] == "set_sec_cash":
        await q("INSERT OR REPLACE INTO section_cash(section_id,cash_number) VALUES(?,?)", (d['sid'], txt))
        await msg.answer("✅ تم تحديث كاش القسم"); await state.clear()
    elif d['act'] == "set_sec_price":
        if not txt.isdigit(): return await msg.answer("ارقام فقط!")
        await q("UPDATE sections SET price=? WHERE id=?", (int(txt), d['sid']))
        await msg.answer("✅ تم تحديث السعر"); await state.clear()
    elif d['act'] == "set_sec_name":
        await q("UPDATE sections SET name=? WHERE id=?", (txt, d['sid']))
        await msg.answer("✅ تم تغيير اسم القسم"); await state.clear()
    elif d['act'] == "add_sec_name":
        await state.update_data(name=txt)
        kb = InlineKeyboardBuilder()
        kb.button(text="🔵 أزرق", callback_data="adm_color_primary", style="primary")
        kb.button(text="🔴 أحمر", callback_data="adm_color_danger", style="primary")
        kb.button(text="🟢 أخضر", callback_data="adm_color_success", style="primary")
        kb.adjust(3)
        await msg.answer("اختر لون الزر:", reply_markup=kb.as_markup())
        return
    elif d['act'] == "add_sec_price":
        if not txt.isdigit(): return await msg.answer("ارقام فقط!")
        await q("INSERT INTO sections(name,price,color,emoji) VALUES(?,?,?,?)", (d['name'], int(txt), d['color'], d['emoji']))
        await msg.answer("✅ تم الاضافة"); await state.clear()

# ══════════════════════════════════════
# 📊 الإحصائيات الخلفية التلقائية
# ══════════════════════════════════════
async def daily_task(bot: Bot):
    while True:
        await asyncio.sleep(86400)
        try:
            counts = await q("SELECT (SELECT COUNT(*) FROM users) as u, (SELECT COUNT(*) FROM requests WHERE date(created_at)=date('now')) as rt, (SELECT COUNT(*) FROM requests WHERE status='accepted' AND date(created_at)=date('now')) as ra")
            if not counts: continue
            u_t, r_t, r_a = counts['u'], counts['rt'], counts['ra']
            secs = await q("""
                SELECT s.name,
                    (SELECT COUNT(*) FROM requests WHERE section_id=s.id AND date(created_at)=date('now')) as st,
                    (SELECT COUNT(*) FROM requests WHERE section_id=s.id AND status='accepted' AND date(created_at)=date('now')) as sa,
                    (SELECT COUNT(*) FROM requests WHERE section_id=s.id AND status='pending') as sp,
                    COALESCE(sc.cash_number, (SELECT value FROM settings WHERE key='cash_number')) as cash
                FROM sections s
                LEFT JOIN section_cash sc ON s.id = sc.section_id
            """, all=True)
            s_txt = "".join([f"\n📂 <b>{s['name']}</b>\n   📥 طلبات اليوم: {s['st']}\n   ✅ مكتملة: {s['sa']}\n   ⏳ معلقة (إجمالي): {s['sp']}\n   💸 رقم الكاش: <code>{s['cash']}</code>\n" for s in secs])
            txt = (f"{ce(E['crown'])} <b>📊 الأحصائيات اليومية</b>\n\n👥 إجمالي المستخدمين: <b>{u_t}</b>\n📋 طلبات اليوم: <b>{r_t}</b>\n✅ مكتملة اليوم: <b>{r_a}</b>\n\n━━━━━━━━━━━━━━\n<b>📂 تفصيل الأقسام:</b>{s_txt}")
            await bot.send_message(ADMIN_ID, txt, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Error in daily_task background loop: {e}")

async def on_startup(bot: Bot):
    asyncio.create_task(daily_task(bot))

# ══════════════════════════════════════
# 🏁 نقطة التشغيل الرئيسية للبوت
# ══════════════════════════════════════
async def main():
    global db_lock
    # db_lock already initialized at module level, kept here for safety
    await db_init()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    
    try:
        await bot.set_my_commands(
            [
                types.BotCommand(command="start", description="بدء تشغيل"),
            ],
            scope=types.BotCommandScopeDefault()
        )
        print("Done setting commands!")
        print("Bot is running...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__": 
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
