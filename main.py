import subprocess, sys

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--break-system-packages", "-q"])

try:
    import telebot
except:
    install("pyTelegramBotAPI")
    import telebot

import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ══════════════════════════════════════
# ⚙️ إعدادات البوت
# ══════════════════════════════════════
BOT_TOKEN = "8965089120:AAFRc4rjwVqip7mg8zw_X8jgqJq6QfPwoHI"
ADMIN_ID  = 8985528607

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ══════════════════════════════════════
# 🗄️ قاعدة البيانات
# ══════════════════════════════════════
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cur  = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS sections (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT,
    price  INTEGER,
    status TEXT DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    username      TEXT,
    full_name     TEXT,
    section_name  TEXT,
    section_price INTEGER,
    screenshot_id TEXT,
    phone_number  TEXT,
    status        TEXT DEFAULT 'pending',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
    id        INTEGER PRIMARY KEY,
    username  TEXT,
    full_name TEXT,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS force_channels (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT,
    title   TEXT
);
CREATE TABLE IF NOT EXISTS admins (
    id        INTEGER PRIMARY KEY,
    username  TEXT,
    full_name TEXT,
    added_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")

for k, v in {
    "cash_number":      "01000000000",
    "trust_channel":    "@trust_channel",
    "support_username": "@support_admin",
    "welcome_message":  "اهلا بك! اختر القسم المطلوب.",
    "welcome_photo":    "",
}.items():
    cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
conn.commit()

# ══════════════════════════════════════
# 🛠️ دوال مساعدة
# ══════════════════════════════════════
def gs(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = cur.fetchone()
    return r[0] if r else ""

def ss(key, val):
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, val))
    conn.commit()

def is_owner(uid): return uid == ADMIN_ID

def is_admin(uid):
    if uid == ADMIN_ID: return True
    cur.execute("SELECT id FROM admins WHERE id=?", (uid,))
    return cur.fetchone() is not None

states = {}

def ce(eid): return f'<tg-emoji emoji-id="{eid}">⭐</tg-emoji>'

E = {
    "star":    "5355180574313060180",
    "fire":    "5357272206206342962",
    "diamond": "5354797987216265138",
    "crown":   "5357581641420143839",
    "flash":   "5357169569372866445",
    "check":   "5355057446190613905",
    "lock":    "5355023563193619708",
    "arrow":   "5355332431471748210",
    "money":   "5355200176543799124",
    "bell":    "5354973921961611463",
    "heart":   "5215420556089776398",
    "shield":  "5204242830687494041",
    "gift":    "5381975814415866082",
    "key":     "5461128651477111908",
    "rocket":  "5472250091332993630",
    "eye":     "5235794253149394263",
    "moon":    "5462902520215002477",
    "sun":     "5472239203590888751",
    "cloud":   "5400090058030075645",
    "wave":    "5377336227533969892",
    "orange"   "5895462897231861514",
    "vodafone" "5836910054762092234",
    "we"       "5837128389424585193",
    "etisalat"  "5836811137370297987",
    "telegram" "5796189349569637980",
    "verfied"   "5796531907571226531",
}
# ══════════════════════════════════════
# 📣 الاشتراك الإجباري
# ══════════════════════════════════════
def check_subscribe(user_id):
    cur.execute("SELECT channel FROM force_channels")
    channels = cur.fetchall()
    not_joined = []
    for (ch,) in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except:
            not_joined.append(ch)
    return not_joined

def subscribe_markup(not_joined):
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in not_joined:
        try:
            chat  = bot.get_chat(ch)
            title = chat.title or ch
            link  = f"https://t.me/{ch.lstrip('@')}"
            kb.add(InlineKeyboardButton(f"📣 {title}", url=link))
        except:
            kb.add(InlineKeyboardButton(f"📣 {ch}", url=f"https://t.me/{ch.lstrip('@')}"))
    kb.add(InlineKeyboardButton("✅ اشتركت! تحقق", callback_data="check_sub", style="success"))
    return kb

# ══════════════════════════════════════
# 🎛️ لوحة الأدمن الرئيسي (كل الصلاحيات)
# ══════════════════════════════════════
def admin_markup():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ اضافة قسم",         callback_data="adm_add_section", style="primary"),
        InlineKeyboardButton("📋 ادارة الاقسام",      callback_data="adm_sections", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("💸 تغيير رقم الكاش",   callback_data="adm_cash", style="success"),
        InlineKeyboardButton("📢 اذاعة للكل",         callback_data="adm_broadcast", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("✏️ رسالة الترحيب",     callback_data="adm_welcome_msg", style="primary"),
        InlineKeyboardButton("🖼️ صورة الترحيب",      callback_data="adm_welcome_photo", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("🔗 قناة الثقة",         callback_data="adm_trust", style="primary"),
        InlineKeyboardButton("👤 حساب الدعم",         callback_data="adm_support", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("👥 المستخدمين",         callback_data="adm_users", style="success"),
        InlineKeyboardButton("📊 الاحصائيات",         callback_data="adm_stats", style="success"),
    )
    kb.add(
        InlineKeyboardButton("📣 الاشتراك الاجباري",  callback_data="adm_force", style="primary"),
        InlineKeyboardButton("🚨 الطلبات المعلقة",    callback_data="adm_pending", style="danger"),
    )
    kb.add(
        InlineKeyboardButton("👮 ادارة الادمنز",      callback_data="adm_admins", style="primary"),
    )
    return kb

# ══════════════════════════════════════
# 🎛️ لوحة الأدمن الفرعي (بدون تغيير الكاش)
# ══════════════════════════════════════
def subadmin_markup():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ اضافة قسم",         callback_data="adm_add_section", style="primary"),
        InlineKeyboardButton("📋 ادارة الاقسام",      callback_data="adm_sections", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("📢 اذاعة للكل",         callback_data="adm_broadcast", style="primary"),
        InlineKeyboardButton("✏️ رسالة الترحيب",     callback_data="adm_welcome_msg", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("🖼️ صورة الترحيب",      callback_data="adm_welcome_photo", style="primary"),
        InlineKeyboardButton("🔗 قناة الثقة",         callback_data="adm_trust", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("👤 حساب الدعم",         callback_data="adm_support", style="primary"),
        InlineKeyboardButton("👥 المستخدمين",         callback_data="adm_users", style="success"),
    )
    kb.add(
        InlineKeyboardButton("📊 الاحصائيات",         callback_data="adm_stats", style="success"),
        InlineKeyboardButton("📣 الاشتراك الاجباري",  callback_data="adm_force", style="primary"),
    )
    kb.add(
        InlineKeyboardButton("🚨 الطلبات المعلقة",    callback_data="adm_pending", style="danger"),
    )
    return kb

def get_admin_markup(uid):
    return admin_markup() if is_owner(uid) else subadmin_markup()

@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    uid = msg.from_user.id
    if not is_admin(uid): return
    title = f"{ce(E['crown'])} <b>لوحة الادمن</b>" if is_owner(uid) else f"{ce(E['shield'])} <b>لوحة المشرف</b>"
    bot.send_message(msg.chat.id, title,
                     parse_mode="HTML", reply_markup=get_admin_markup(uid))

# ══════════════════════════════════════
# 🏠 الصفحة الرئيسية
# ══════════════════════════════════════
def send_home(chat_id):
    welcome = gs("welcome_message")
    trust   = gs("trust_channel")
    support = gs("support_username")
    photo   = gs("welcome_photo")

    kb = InlineKeyboardMarkup(row_width=2)
    cur.execute("SELECT id, name, price, status FROM sections")
    rows = cur.fetchall()
    btns = []
    for r in rows:
        if r[3] == "open":
            btns.append(InlineKeyboardButton(f"{r[1]}", callback_data=f"sec_{r[0]}", style="primary"))
        else:
            btns.append(InlineKeyboardButton(f"🔒 {r[1]}", callback_data=f"sec_closed_{r[0]}", style="danger"))
    if btns:
        kb.add(*btns)

    kb.add(InlineKeyboardButton("📊 احصائياتي", callback_data="my_stats", style="primary"))
    kb.row(
        InlineKeyboardButton("📣 قناة الثقة",     url=f"https://t.me/{trust.lstrip('@')}",   style="primary"),
        InlineKeyboardButton("💬 تواصل مع الدعم", url=f"https://t.me/{support.lstrip('@')}", style="primary")
    )

    if photo:
        try:
            bot.send_photo(chat_id, photo, caption=welcome, reply_markup=kb, parse_mode="HTML")
            return
        except:
            ss("welcome_photo", "")
    bot.send_message(chat_id, welcome, reply_markup=kb, parse_mode="HTML")

# ══════════════════════════════════════
# /start
# ══════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    u = msg.from_user
    uid = u.id
    cur.execute("SELECT id FROM users WHERE id=?", (uid,))
    is_new = not cur.fetchone()
    if is_new:
        cur.execute("INSERT INTO users(id,username,full_name) VALUES(?,?,?)",
                    (uid, u.username or "", u.first_name or ""))
        conn.commit()

    if is_admin(uid):
        greeting = f"{ce(E['crown'])} <b>اهلا ادمن!</b>" if is_owner(uid) else f"{ce(E['shield'])} <b>اهلا مشرف!</b>"
        bot.send_message(msg.chat.id, greeting,
                         parse_mode="HTML", reply_markup=get_admin_markup(uid))
        return

    # إشعار الأدمن — مرة واحدة بس أول دخول
    if is_new:
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        try:
            bot.send_message(ADMIN_ID,
                             f"{ce(E['bell'])} <b>مستخدم جديد 🆕</b>\n\n"
                             f"👤 {u.first_name} (@{u.username or 'لا يوجد'})\n"
                             f"🆔 <code>{u.id}</code>\n"
                             f"👥 اجمالي المستخدمين: <b>{total}</b>",
                             parse_mode="HTML")
        except: pass

    # فحص الاشتراك الإجباري
    not_joined = check_subscribe(u.id)
    if not_joined:
        bot.send_message(msg.chat.id,
                         f"{ce(E['bell'])} <b>يجب الاشتراك في القنوات التالية اولاً:</b>",
                         parse_mode="HTML", reply_markup=subscribe_markup(not_joined))
        return

    send_home(msg.chat.id)

# ══════════════════════════════════════
# ✅ تحقق من الاشتراك
# ══════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def do_check_sub(call):
    not_joined = check_subscribe(call.from_user.id)
    if not_joined:
        bot.answer_callback_query(call.id, "❌ لسه مش مشترك في كل القنوات!", show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=subscribe_markup(not_joined))
        except: pass
    else:
        bot.answer_callback_query(call.id, "✅ تم التحقق! اهلا بك")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        send_home(call.message.chat.id)

# ══════════════════════════════════════
# 📊 إحصائيات العميل
# ══════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "my_stats")
def my_stats(call):
    uid = call.from_user.id
    cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=?", (uid,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='accepted'", (uid,))
    accepted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='pending'", (uid,))
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM requests WHERE user_id=? AND status='rejected'", (uid,))
    rejected = cur.fetchone()[0]

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="go_home", style="success"))

    text = (f"{ce(E['star'])} <b>احصائياتك</b>\n\n"
            f"📋 اجمالي طلباتك: <b>{total}</b>\n"
            f"✅ مقبولة: <b>{accepted}</b>\n"
            f"⏳ معلقة: <b>{pending}</b>\n"
            f"❌ مرفوضة: <b>{rejected}</b>")

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except:
        bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "go_home")
def go_home(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    send_home(call.message.chat.id)

# ══════════════════════════════════════
# 📂 قسم مغلق
# ══════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("sec_closed_"))
def sec_closed(call):
    sec_id = int(call.data.split("_")[2])
    cur.execute("SELECT name FROM sections WHERE id=?", (sec_id,))
    r = cur.fetchone()
    bot.answer_callback_query(call.id, f"🔒 قسم {r[0] if r else ''} مغلق حالياً!", show_alert=True)

# ══════════════════════════════════════
# 📂 قسم مفتوح
# ══════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("sec_") and not c.data.startswith("sec_closed_"))
def sec_selected(call):
    not_joined = check_subscribe(call.from_user.id)
    if not_joined:
        bot.answer_callback_query(call.id, "❌ يجب الاشتراك اولاً!", show_alert=True)
        return

    sec_id = int(call.data.split("_")[1])
    cur.execute("SELECT name, price, status FROM sections WHERE id=?", (sec_id,))
    row = cur.fetchone()
    if not row:
        bot.answer_callback_query(call.id, "القسم مش موجود!"); return
    if row[2] != "open":
        bot.answer_callback_query(call.id, "🔒 القسم مغلق!", show_alert=True); return

    name, price = row[0], row[1]
    cash = gs("cash_number")
    states[call.from_user.id] = {
        "step": "wait_screenshot",
        "sec_id": sec_id, "sec_name": name, "sec_price": price
    }

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ الغاء", callback_data="cancel", style="danger"))

    text = (f"{ce(E['fire'])} <b>اخترت:</b> {name}\n\n"
            f"{ce(E['money'])} <b>السعر:</b> {price} جنيه\n\n"
            f"{ce(E['flash'])} حول المبلغ على رقم الكاش:\n<code>{cash}</code>\n\n"
            f"{ce(E['arrow'])} بعد التحويل ابعت <b>سكرين الايصال</b> هنا 👇")

    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except:
        bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "cancel")
def do_cancel(call):
    states.pop(call.from_user.id, None)
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    send_home(call.message.chat.id)

# ══════════════════════════════════════
# 📸 استقبال الصور
# ══════════════════════════════════════
@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    uid   = msg.from_user.id
    state = states.get(uid, {})
    step  = state.get("step")

    # أدمن: تغيير صورة الترحيب
    if is_admin(uid) and step == "set_photo":
        ss("welcome_photo", msg.photo[-1].file_id)
        states.pop(uid, None)
        bot.send_message(uid, f"{ce(E['check'])} <b>تم تغيير صورة الترحيب!</b>",
                         parse_mode="HTML", reply_markup=get_admin_markup(uid))
        return

    # أدمن: رد بصورة على عميل
    if is_admin(uid) and step == "admin_reply":
        req_id = state.get("req_id")
        cur.execute("SELECT user_id FROM requests WHERE id=?", (req_id,))
        r = cur.fetchone()
        if r:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("✅ تم الاستلام", callback_data=f"cli_confirm_{req_id}", style="success"),
                InlineKeyboardButton("❌ في مشكلة",    callback_data=f"cli_issue_{req_id}", style="danger")
            )
            bot.send_photo(r[0], msg.photo[-1].file_id,
                           caption=f"{ce(E['bell'])} <b>رد من الادارة على طلبك:</b>",
                           parse_mode="HTML", reply_markup=kb)
            bot.send_message(uid, f"{ce(E['check'])} <b>تم ارسال الرد للعميل.</b>",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))
        states.pop(uid, None)
        return

    # عميل: سكرين التحويل
    if step == "wait_screenshot":
        state["screenshot"] = msg.photo[-1].file_id
        state["step"]       = "wait_phone"
        states[uid]         = state
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ الغاء", callback_data="cancel", style="danger"))
        bot.send_message(uid,
                         f"{ce(E['check'])} <b>استلمنا السكرين!</b>\n\n"
                         f"{ce(E['arrow'])} دلوقتي ابعت <b>الرقم اللي حولت منه</b>:",
                         parse_mode="HTML", reply_markup=kb)
        return

# ══════════════════════════════════════
# 💬 استقبال النصوص
# ══════════════════════════════════════
@bot.message_handler(content_types=["text"])
def handle_text(msg):
    uid   = msg.from_user.id
    text  = msg.text.strip()
    state = states.get(uid, {})
    step  = state.get("step")

    # أدمن: رد نصي على عميل
    if is_admin(uid) and step == "admin_reply":
        req_id = state.get("req_id")
        cur.execute("SELECT user_id FROM requests WHERE id=?", (req_id,))
        r = cur.fetchone()
        if r:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("✅ تم الاستلام", callback_data=f"cli_confirm_{req_id}", style="success"),
                InlineKeyboardButton("❌ في مشكلة",    callback_data=f"cli_issue_{req_id}", style="danger")
            )
            bot.send_message(r[0], f"{ce(E['bell'])} <b>رد من الادارة:</b>\n\n{text}",
                             parse_mode="HTML", reply_markup=kb)
            bot.send_message(uid, f"{ce(E['check'])} <b>تم ارسال الرد للعميل.</b>",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))
        states.pop(uid, None)
        return

    # أدمن: إعدادات
    if is_admin(uid) and step:
        if step == "set_cash":
            ss("cash_number", text)
            states.pop(uid, None)
            bot.send_message(uid, f"{ce(E['money'])} <b>رقم الكاش:</b> <code>{text}</code>",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))

        elif step == "set_trust":
            ss("trust_channel", text)
            states.pop(uid, None)
            bot.send_message(uid, f"{ce(E['check'])} <b>قناة الثقة:</b> {text}",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))

        elif step == "set_support":
            ss("support_username", text)
            states.pop(uid, None)
            bot.send_message(uid, f"{ce(E['check'])} <b>حساب الدعم:</b> {text}",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))

        elif step == "set_welcome_msg":
            ss("welcome_message", text)
            states.pop(uid, None)
            bot.send_message(uid, f"{ce(E['check'])} <b>تم تغيير رسالة الترحيب.</b>",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))

        elif step == "add_sec_name":
            state["sec_name"] = text
            state["step"]     = "add_sec_price"
            states[uid]       = state
            bot.send_message(uid,
                             f"{ce(E['star'])} <b>اسم القسم:</b> {text}\n\nدلوقتي ابعت <b>السعر</b> (ارقام فقط):",
                             parse_mode="HTML")

        elif step == "add_sec_price":
            if not text.isdigit():
                bot.send_message(uid, "❌ ابعت رقم صحيح!"); return
            name  = state["sec_name"]
            price = int(text)
            cur.execute("INSERT INTO sections(name,price) VALUES(?,?)", (name, price))
            conn.commit()
            states.pop(uid, None)
            bot.send_message(uid,
                             f"{ce(E['check'])} <b>تم اضافة القسم:</b>\n📂 {name} — {price} جنيه",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))

        elif step == "broadcast":
            cur.execute("SELECT id FROM users")
            users = cur.fetchall()
            sent  = 0
            for (u_id,) in users:
                try:
                    bot.send_message(u_id, f"{ce(E['bell'])} <b>اذاعة من الادارة:</b>\n\n{text}",
                                     parse_mode="HTML")
                    sent += 1
                except: pass
            states.pop(uid, None)
            bot.send_message(uid, f"{ce(E['check'])} <b>تم الارسال لـ {sent} مستخدم.</b>",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))

        elif step == "add_force_channel":
            channel = text if text.startswith("@") else f"@{text}"
            try:
                chat  = bot.get_chat(channel)
                title = chat.title or channel
                cur.execute("INSERT INTO force_channels(channel,title) VALUES(?,?)", (channel, title))
                conn.commit()
                states.pop(uid, None)
                bot.send_message(uid,
                                 f"{ce(E['check'])} <b>تم اضافة قناة الاشتراك الاجباري:</b>\n{title}",
                                 parse_mode="HTML", reply_markup=get_admin_markup(uid))
            except Exception as e:
                bot.send_message(uid, f"❌ تاكد ان البوت ادمن في القناة!\nالخطأ: {e}")

        elif step == "add_admin":
            if not is_owner(uid):
                states.pop(uid, None); return
            if not text.isdigit():
                bot.send_message(uid, "❌ ابعت رقم ID صحيح (ارقام فقط)!"); return
            new_admin_id = int(text)
            if new_admin_id == ADMIN_ID:
                bot.send_message(uid, "❌ ده انت نفسك يا اسطى 😄"); return
            # جيب بيانات اليوزر من تيليجرام
            try:
                chat = bot.get_chat(new_admin_id)
                uname = chat.username or ""
                fname = chat.first_name or ""
            except:
                uname, fname = "", ""
            cur.execute("INSERT OR IGNORE INTO admins(id,username,full_name) VALUES(?,?,?)",
                        (new_admin_id, uname, fname))
            conn.commit()
            states.pop(uid, None)
            display = fname or uname or str(new_admin_id)
            bot.send_message(uid,
                             f"{ce(E['check'])} <b>تم اضافة الادمن:</b>\n"
                             f"👤 {display}\n🆔 <code>{new_admin_id}</code>",
                             parse_mode="HTML", reply_markup=get_admin_markup(uid))
            # اشعر الادمن الجديد
            try:
                bot.send_message(new_admin_id,
                                 f"{ce(E['shield'])} <b>اهلا! تم تعيينك مشرف في البوت.</b>\n\n"
                                 f"استخدم /admin للوصول للوحة التحكم.",
                                 parse_mode="HTML")
            except: pass
        return

    # عميل: رقم التحويل
    if step == "wait_phone":
        state["phone"] = text
        state["step"]  = "wait_target"
        states[uid]    = state
        sec_name = state["sec_name"]
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ الغاء", callback_data="cancel", style="danger"))
        bot.send_message(uid,
                         f"{ce(E['check'])} <b>استلمنا الرقم!</b>\n\n"
                         f"{ce(E['arrow'])} دلوقتي ابعت <b>الرقم اللي عايز تسحب عليه {sec_name}</b>:",
                         parse_mode="HTML", reply_markup=kb)
        return

    # عميل: الرقم التارجت
    if step == "wait_target":
        target_number = text
        phone         = state.get("phone", "")
        sec_name      = state["sec_name"]
        sec_price     = state["sec_price"]
        screenshot    = state.get("screenshot", "")
        u             = msg.from_user

        cur.execute(
            "INSERT INTO requests(user_id,username,full_name,section_name,section_price,screenshot_id,phone_number)"
            " VALUES(?,?,?,?,?,?,?)",
            (uid, u.username or "", u.first_name or "", sec_name, sec_price, screenshot, f"{phone}|{target_number}")
        )
        conn.commit()
        req_id = cur.lastrowid
        states.pop(uid, None)

        bot.send_message(uid,
                         f"{ce(E['check'])} <b>تم ارسال طلبك للمشرفين!</b>\n\n"
                         f"{ce(E['rocket'])} سيتم الرد عليك قريباً",
                         parse_mode="HTML")

        admin_text = (
            f"{ce(E['bell'])} <b>طلب جديد #{req_id}</b>\n\n"
            f"{ce(E['star'])} <b>المستخدم:</b> {u.first_name} (@{u.username or 'لا يوجد'})\n"
            f"🆔 <code>{uid}</code>\n"
            f"📂 <b>القسم:</b> {sec_name}\n"
            f"{ce(E['money'])} <b>المبلغ:</b> {sec_price} جنيه\n"
            f"📞 <b>رقم التحويل:</b> <code>{phone}</code>\n"
            f"🎯 <b>الرقم التارجت:</b> <code>{target_number}</code>"
        )

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ قبول + ارسال البيانات", callback_data=f"adm_accept_{req_id}", style="success"),
        )
        kb.add(
            InlineKeyboardButton("❌ رفض", callback_data=f"adm_reject_{req_id}", style="danger"),
        )

        if screenshot:
            bot.send_photo(ADMIN_ID, screenshot, caption=admin_text, parse_mode="HTML", reply_markup=kb)
        else:
            bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=kb)

# ══════════════════════════════════════
# 🎛️ كولباك الأدمن
# ══════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def adm_cb(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ مش ادمن!"); return

    d   = call.data
    uid = call.from_user.id
    cid = call.message.chat.id
    mid = call.message.message_id

    if d == "adm_cash":
        if not is_owner(uid):
            bot.answer_callback_query(call.id, "❌ الأدمن الرئيسي بس اللي يقدر يغير رقم الكاش!", show_alert=True)
            return
        states[uid] = {"step": "set_cash"}
        bot.edit_message_text(f"{ce(E['money'])} ابعت رقم الكاش الجديد:",
                              cid, mid, parse_mode="HTML")

    # ── إدارة الأدمنز (أدمن رئيسي فقط) ──
    elif d == "adm_admins":
        if not is_owner(uid):
            bot.answer_callback_query(call.id, "❌ مش مسموح!", show_alert=True); return
        cur.execute("SELECT id, username, full_name FROM admins")
        rows = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            name_display = r[2] or r[1] or str(r[0])
            kb.add(InlineKeyboardButton(f"🗑️ حذف: {name_display}", callback_data=f"adm_deladmin_{r[0]}", style="danger"))
        kb.add(InlineKeyboardButton("➕ اضافة ادمن", callback_data="adm_addadmin", style="success"))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(
            f"{ce(E['crown'])} <b>ادارة الادمنز</b>\n\n"
            f"عدد الادمنز الفرعيين: <b>{len(rows)}</b>\n\n"
            "⚠️ الادمن الفرعي يقدر يعمل كل حاجه ما عدا تغيير رقم الكاش وادارة الادمنز.",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif d == "adm_addadmin":
        if not is_owner(uid):
            bot.answer_callback_query(call.id, "❌ مش مسموح!", show_alert=True); return
        states[uid] = {"step": "add_admin"}
        bot.edit_message_text(
            f"{ce(E['arrow'])} ابعت الـ ID بتاع الادمن الجديد:\n\n"
            "يقدر يجيبه من @userinfobot",
            cid, mid, parse_mode="HTML"
        )

    elif d.startswith("adm_deladmin_"):
        if not is_owner(uid):
            bot.answer_callback_query(call.id, "❌ مش مسموح!", show_alert=True); return
        del_id = int(d.split("_")[2])
        cur.execute("DELETE FROM admins WHERE id=?", (del_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "🗑️ تم حذف الادمن!")
        # refresh list
        cur.execute("SELECT id, username, full_name FROM admins")
        rows = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            name_display = r[2] or r[1] or str(r[0])
            kb.add(InlineKeyboardButton(f"🗑️ حذف: {name_display}", callback_data=f"adm_deladmin_{r[0]}", style="danger"))
        kb.add(InlineKeyboardButton("➕ اضافة ادمن", callback_data="adm_addadmin", style="success"))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(
            f"{ce(E['crown'])} <b>ادارة الادمنز</b>\n\nعدد الادمنز الفرعيين: <b>{len(rows)}</b>",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif d == "adm_trust":
        states[uid] = {"step": "set_trust"}
        bot.edit_message_text(f"{ce(E['star'])} ابعت يوزرنيم قناة الثقة (مثال: @channel):",
                              cid, mid, parse_mode="HTML")

    elif d == "adm_support":
        states[uid] = {"step": "set_support"}
        bot.edit_message_text(f"{ce(E['shield'])} ابعت يوزرنيم الدعم (مثال: @support):",
                              cid, mid, parse_mode="HTML")

    elif d == "adm_welcome_msg":
        states[uid] = {"step": "set_welcome_msg"}
        bot.edit_message_text(f"{ce(E['wave'])} ابعت رسالة الترحيب الجديدة:",
                              cid, mid, parse_mode="HTML")

    elif d == "adm_welcome_photo":
        states[uid] = {"step": "set_photo"}
        bot.edit_message_text(f"{ce(E['eye'])} ابعت صورة الترحيب:",
                              cid, mid, parse_mode="HTML")

    elif d == "adm_add_section":
        states[uid] = {"step": "add_sec_name"}
        bot.edit_message_text(f"{ce(E['fire'])} ابعت اسم القسم الجديد:",
                              cid, mid, parse_mode="HTML")

    elif d == "adm_broadcast":
        states[uid] = {"step": "broadcast"}
        bot.edit_message_text(f"{ce(E['bell'])} ابعت رسالة الاذاعة:",
                              cid, mid, parse_mode="HTML")

    elif d == "adm_users":
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        bot.answer_callback_query(call.id, f"👥 اجمالي المستخدمين: {count}", show_alert=True)

    elif d == "adm_stats":
        cur.execute("SELECT COUNT(*) FROM requests")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM requests WHERE status='pending'")
        pending = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM requests WHERE status='accepted'")
        accepted = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]
        cash = gs("cash_number")
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(
            f"{ce(E['crown'])} <b>الاحصائيات</b>\n\n"
            f"👥 المستخدمين: <b>{users}</b>\n"
            f"📋 الطلبات الكلية: <b>{total}</b>\n"
            f"⏳ معلقة: <b>{pending}</b>\n"
            f"✅ مقبولة: <b>{accepted}</b>\n"
            f"{ce(E['money'])} رقم الكاش: <code>{cash}</code>",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    # ── الاشتراك الإجباري ──
    elif d == "adm_force":
        cur.execute("SELECT id, title, channel FROM force_channels")
        rows = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            kb.add(InlineKeyboardButton(f"🗑️ حذف: {r[1]}", callback_data=f"adm_delf_{r[0]}", style="danger"))
        kb.add(InlineKeyboardButton("➕ اضافة قناة/جروب", callback_data="adm_addf"))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(
            f"{ce(E['lock'])} <b>الاشتراك الاجباري</b>\n\n"
            f"القنوات الحالية: <b>{len(rows)}</b>\n\n"
            "تاكد ان البوت ادمن في القناة قبل الاضافة!",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif d == "adm_addf":
        states[uid] = {"step": "add_force_channel"}
        bot.edit_message_text(
            f"{ce(E['arrow'])} ابعت يوزرنيم القناة او الجروب:\n(مثال: @mychannel)",
            cid, mid, parse_mode="HTML"
        )

    elif d.startswith("adm_delf_"):
        fid = int(d.split("_")[2])
        cur.execute("DELETE FROM force_channels WHERE id=?", (fid,))
        conn.commit()
        bot.answer_callback_query(call.id, "🗑️ تم الحذف!")
        # تحديث القائمة
        cur.execute("SELECT id, title, channel FROM force_channels")
        rows = cur.fetchall()
        kb = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            kb.add(InlineKeyboardButton(f"🗑️ حذف: {r[1]}", callback_data=f"adm_delf_{r[0]}", style="danger"))
        kb.add(InlineKeyboardButton("➕ اضافة قناة/جروب", callback_data="adm_addf"))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(
            f"{ce(E['lock'])} <b>الاشتراك الاجباري</b>\n\nالقنوات الحالية: <b>{len(rows)}</b>",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    # ── الطلبات المعلقة ──
    elif d == "adm_pending":
        cur.execute("SELECT id, full_name, section_name, section_price FROM requests WHERE status='pending' LIMIT 15")
        rows = cur.fetchall()
        if not rows:
            bot.answer_callback_query(call.id, "✅ مفيش طلبات معلقة!", show_alert=True); return
        kb = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            kb.add(InlineKeyboardButton(
                f"#{r[0]} ┃ {r[1]} ┃ {r[2]} — {r[3]}ج",
                callback_data=f"adm_view_{r[0]}"
            ))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(f"{ce(E['bell'])} <b>الطلبات المعلقة:</b>",
                              cid, mid, parse_mode="HTML", reply_markup=kb)

    elif d.startswith("adm_view_"):
        req_id = int(d.split("_")[2])
        cur.execute("SELECT * FROM requests WHERE id=?", (req_id,))
        r = cur.fetchone()
        if not r: return
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ قبول + ارسال البيانات", callback_data=f"adm_accept_{req_id}", style="success"))
        kb.add(InlineKeyboardButton("❌ رفض",                   callback_data=f"adm_reject_{req_id}", style="danger"))
        kb.add(InlineKeyboardButton("🔙 رجوع",                  callback_data="adm_pending", style="danger"))
        phone_raw = r[7] or ""
        if "|" in phone_raw:
            ph_transfer, ph_target = phone_raw.split("|", 1)
            phone_display = f"📞 <b>رقم التحويل:</b> <code>{ph_transfer}</code>\n🎯 <b>الرقم التارجت:</b> <code>{ph_target}</code>"
        else:
            phone_display = f"📞 <code>{phone_raw}</code>"
        text = (
            f"{ce(E['star'])} <b>تفاصيل طلب #{req_id}</b>\n\n"
            f"👤 {r[3]} (@{r[2] or 'لا يوجد'})\n"
            f"🆔 <code>{r[1]}</code>\n"
            f"📂 {r[4]}\n"
            f"{ce(E['money'])} {r[5]} جنيه\n"
            f"{phone_display}\n"
            f"📌 الحالة: {r[8]}"
        )
        if r[6]:
            bot.send_photo(cid, r[6], caption=text, parse_mode="HTML", reply_markup=kb)
        else:
            bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=kb)

    # ── قبول الطلب ──
    elif d.startswith("adm_accept_"):
        req_id = int(d.split("_")[2])
        cur.execute("UPDATE requests SET status='accepted' WHERE id=?", (req_id,))
        conn.commit()
        cur.execute("SELECT user_id FROM requests WHERE id=?", (req_id,))
        r = cur.fetchone()
        if r:
            bot.send_message(r[0],
                             f"{ce(E['check'])} <b>تم قبول طلبك!</b>\n\n"
                             f"{ce(E['rocket'])} استنى.. البيانات هتوصلك دلوقتي",
                             parse_mode="HTML")
        states[uid] = {"step": "admin_reply", "req_id": req_id}
        bot.answer_callback_query(call.id, "✅ تم القبول! ابعت البيانات دلوقتي.")
        try: bot.edit_message_reply_markup(cid, mid, reply_markup=None)
        except: pass
        bot.send_message(uid,
                         f"{ce(E['arrow'])} <b>ابعت البيانات للعميل</b> (نص او صورة) — طلب #{req_id}:",
                         parse_mode="HTML")

    # ── رفض الطلب ──
    elif d.startswith("adm_reject_"):
        req_id = int(d.split("_")[2])
        cur.execute("UPDATE requests SET status='rejected' WHERE id=?", (req_id,))
        conn.commit()
        cur.execute("SELECT user_id FROM requests WHERE id=?", (req_id,))
        r = cur.fetchone()
        if r:
            support = gs("support_username")
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("💬 تواصل مع الدعم",
                                          url=f"https://t.me/{support.lstrip('@')}"))
            bot.send_message(r[0],
                             f"{ce(E['shield'])} <b>تم رفض طلبك.</b>\n\nللاستفسار تواصل مع الدعم.",
                             parse_mode="HTML", reply_markup=kb2)
        bot.answer_callback_query(call.id, "❌ تم رفض الطلب!")
        try: bot.edit_message_reply_markup(cid, mid, reply_markup=None)
        except: pass

    # ── إدارة الأقسام ──
    elif d == "adm_sections":
        cur.execute("SELECT id, name, price, status FROM sections")
        rows = cur.fetchall()
        if not rows:
            bot.answer_callback_query(call.id, "مفيش اقسام بعد!"); return
        kb = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            icon = "🟢" if r[3] == "open" else "🔴"
            kb.add(InlineKeyboardButton(f"{icon} {r[1]} — {r[2]} جنيه",
                                         callback_data=f"adm_secmng_{r[0]}"))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(f"{ce(E['key'])} <b>ادارة الاقسام:</b>",
                              cid, mid, parse_mode="HTML", reply_markup=kb)

    elif d.startswith("adm_secmng_"):
        sec_id  = int(d.split("_")[2])
        cur.execute("SELECT name, price, status FROM sections WHERE id=?", (sec_id,))
        r = cur.fetchone()
        if not r: return
        is_open     = r[2] == "open"
        toggle_text = "🔴 اغلاق القسم" if is_open else "🟢 فتح القسم"
        toggle_val  = "close" if is_open else "open"
        status_text = "🟢 مفتوح" if is_open else "🔴 مغلق"
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(toggle_text, callback_data=f"adm_sectog_{sec_id}_{toggle_val}", style="primary"),
            InlineKeyboardButton("🗑️ حذف",   callback_data=f"adm_secdel_{sec_id}", style="danger")
        )
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_sections", style="danger"))
        bot.edit_message_text(
            f"{ce(E['lock'])} <b>ادارة القسم</b>\n\n"
            f"📂 الاسم: {r[0]}\n"
            f"{ce(E['money'])} السعر: {r[1]} جنيه\n"
            f"📌 الحالة: {status_text}",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif d.startswith("adm_sectog_"):
        parts      = d.split("_")
        sec_id     = int(parts[2])
        new_status = parts[3]
        cur.execute("UPDATE sections SET status=? WHERE id=?", (new_status, sec_id))
        conn.commit()
        label = "فتح" if new_status == "open" else "اغلاق"
        bot.answer_callback_query(call.id, f"✅ تم {label} القسم!")
        cur.execute("SELECT name, price, status FROM sections WHERE id=?", (sec_id,))
        r = cur.fetchone()
        if not r: return
        is_open     = r[2] == "open"
        toggle_text = "🔴 اغلاق القسم" if is_open else "🟢 فتح القسم"
        toggle_val  = "close" if is_open else "open"
        status_text = "🟢 مفتوح" if is_open else "🔴 مغلق"
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton(toggle_text, callback_data=f"adm_sectog_{sec_id}_{toggle_val}", style="primary"),
            InlineKeyboardButton("🗑️ حذف",   callback_data=f"adm_secdel_{sec_id}", style="danger")
        )
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_sections", style="danger"))
        bot.edit_message_text(
            f"{ce(E['lock'])} <b>ادارة القسم</b>\n\n"
            f"📂 الاسم: {r[0]}\n"
            f"{ce(E['money'])} السعر: {r[1]} جنيه\n"
            f"📌 الحالة: {status_text}",
            cid, mid, parse_mode="HTML", reply_markup=kb
        )

    elif d.startswith("adm_secdel_"):
        sec_id = int(d.split("_")[2])
        cur.execute("DELETE FROM sections WHERE id=?", (sec_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "🗑️ تم حذف القسم!")
        cur.execute("SELECT id, name, price, status FROM sections")
        rows = cur.fetchall()
        kb   = InlineKeyboardMarkup(row_width=1)
        for r in rows:
            icon = "🟢" if r[3] == "open" else "🔴"
            kb.add(InlineKeyboardButton(f"{icon} {r[1]} — {r[2]} جنيه",
                                         callback_data=f"adm_secmng_{r[0]}"))
        kb.add(InlineKeyboardButton("🔙 رجوع", callback_data="adm_back", style="danger"))
        bot.edit_message_text(f"{ce(E['key'])} <b>ادارة الاقسام:</b>",
                              cid, mid, parse_mode="HTML", reply_markup=kb)

    elif d == "adm_back":
        title = f"{ce(E['crown'])} <b>لوحة الادمن</b>" if is_owner(uid) else f"{ce(E['shield'])} <b>لوحة المشرف</b>"
        bot.edit_message_text(title, cid, mid, parse_mode="HTML", reply_markup=get_admin_markup(uid))

# ══════════════════════════════════════
# ✅ كولباك العميل - تم الاستلام / مشكلة
# ══════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("cli_confirm_"))
def cli_confirm(call):
    req_id = int(call.data.split("_")[2])

    # العميل يأكد الاستلام
    txt = f"{ce(E['check'])} <b>تم تاكيد الاستلام! شكراً لتعاملك معنا.</b>"
    try:
        bot.edit_message_caption(caption=txt, chat_id=call.message.chat.id,
                                  message_id=call.message.message_id, parse_mode="HTML")
    except:
        try:
            bot.edit_message_text(txt, call.message.chat.id,
                                   call.message.message_id, parse_mode="HTML")
        except: pass

    # إشعار الأدمن + زرار "الرد بالبيانات"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📤 الرد بالبيانات", callback_data=f"adm_accept_{req_id}", style="success"))
    bot.send_message(ADMIN_ID,
                     f"{ce(E['check'])} <b>العميل اكد استلام طلب #{req_id}</b>\n\n"
                     f"اضغط الزرار لو عايز ترد بالبيانات:",
                     parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cli_issue_"))
def cli_issue(call):
    req_id  = int(call.data.split("_")[2])
    support = gs("support_username")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💬 تواصل مع الدعم",
                                 url=f"https://t.me/{support.lstrip('@')}"))
    txt = f"{ce(E['shield'])} <b>ناسف على المشكلة! تواصل مع الدعم.</b>"
    try:
        bot.edit_message_caption(caption=txt, chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  parse_mode="HTML", reply_markup=kb)
    except:
        try:
            bot.edit_message_text(txt, call.message.chat.id,
                                   call.message.message_id,
                                   parse_mode="HTML", reply_markup=kb)
        except: pass
    bot.send_message(ADMIN_ID,
                     f"⚠️ <b>العميل ابلغ عن مشكلة في طلب #{req_id}</b>",
                     parse_mode="HTML")

# ══════════════════════════════════════
# 🚀 تشغيل
# ══════════════════════════════════════
print("✅ البوت شغال!")
bot.infinity_polling(timeout=30, long_polling_timeout=20)
