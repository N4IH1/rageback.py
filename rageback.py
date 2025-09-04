import os
import json
import logging
from collections import deque
from typing import Dict, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ==============================
# إعدادات
# ==============================
BOT_TOKEN = "8427539133:AAHnKvFM-ZyU9BBd5XAM65WPotREdVfFezA"
ADMIN_CHAT_ID = 6005239475   # أول شخص يعمل /start يصبح الأدمن
CHANNEL_ID = "@RAGEBACKESPORT"
MAX_TEAMS = 23   # = عدد الفرق (من slot 3 إلى 25)

DATA_FILE = "bot_data.json"

# ==============================
# ذاكرة
# ==============================
teams: List[Dict[str, Any]] = []
collecting: Dict[str, Dict[str, Any]] = {}   # طلبات في الانتظار
is_open: bool = False
ROOM_TIME: str = ""
ROOM_CODE: str = ""

SEEN_CALLBACK_IDS = deque(maxlen=2000)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# حفظ / تحميل
# ==============================
def save_all():
    try:
        data = {
            "teams": teams,
            "collecting": collecting,
            "is_open": is_open,
            "ROOM_TIME": ROOM_TIME,
            "ROOM_CODE": ROOM_CODE,
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("save_all failed")

def load_all():
    global teams, collecting, is_open, ROOM_TIME, ROOM_CODE
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        teams = data.get("teams", [])
        collecting = data.get("collecting", {})
        is_open = data.get("is_open", False)
        ROOM_TIME = data.get("ROOM_TIME", "")
        ROOM_CODE = data.get("ROOM_CODE", "")
    except Exception:
        logger.exception("load_all failed")

# ==============================
# أزرار
# ==============================
def kb_player_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 القوانين", callback_data="player:rules")],
        [InlineKeyboardButton("📝 التسجيل", callback_data="player:register")],
        [InlineKeyboardButton("📢 قناة الفاينل", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")]
    ])

def kb_admin_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 فتح التسجيل", callback_data="admin:open"),
         InlineKeyboardButton("🔴 إغلاق التسجيل", callback_data="admin:close")],
        [InlineKeyboardButton("📋 عرض اللستة", callback_data="admin:view_teams")],
        [InlineKeyboardButton("📣 نشر اللستة الآن", callback_data="admin:publish")]
    ])

def admin_action_buttons(user_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ قبول", callback_data=f"admin:accept:{user_id}"),
         InlineKeyboardButton("❌ رفض", callback_data=f"admin:reject:{user_id}")]
    ])

# زر ثابت للاستارت
main_keyboard = ReplyKeyboardMarkup(
    [["/start"]],
    resize_keyboard=True
)

# ==============================
# نصوص
# ==============================
WELCOME_PLAYER = (
    "🔥 *أهلًا بك في RAGEBACK ESPORT — Finals Manager* 🔥\n\n"
    "اضغط على زر التسجيل لإدخال بيانات فريقك."
)

WELCOME_ADMIN = (
    "🛠️ *لوحة تحكم الأدمن — RAGEBACK ESPORT*\n\n"
    "من هنا تستطيع فتح/إغلاق التسجيل، مراجعة الطلبات، ونشر اللستة."
)

RULES_TEXT = (
    "📜 *قوانين الفاينلات:*\n\n"
    "• الحد الأدنى لمستوى الحساب: *50*\n"
    "• الاحترام واجب — لا سب أو شتم\n"
    "• الحد الأدنى لحجم الفريق: *3 لاعبين*\n"
    f"• الحد الأقصى: *{MAX_TEAMS}* فريق (من 3 إلى 25)\n"
)

def build_list_text() -> str:
    if not teams:
        return "لا توجد فرق مسجلة بعد."
    lines = []
    for e in teams:
        if 3 <= e['slot'] <= 25:   # يبدأ من 3 وينتهي عند 25
            lines.append(f"{e['slot']}. {e['clan']} | {e['tag']} | {e['country']}")
    if not lines:
        return "⚠️ لم يصل التسجيل بعد إلى الرقم 3."
    return "📋 *قائمة الفرق المسجلة :*\n\n" + "\n".join(lines)

# ==============================
# أوامر
# ==============================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_CHAT_ID
    user = update.effective_user
    if ADMIN_CHAT_ID == 0:  # أول مستخدم يعمل /start يصبح الأدمن
        ADMIN_CHAT_ID = user.id
    is_admin = (user and user.id == ADMIN_CHAT_ID)
    if update.message:
        await update.message.reply_text(
            WELCOME_ADMIN if is_admin else WELCOME_PLAYER,
            parse_mode="Markdown",
            reply_markup=kb_admin_home() if is_admin else kb_player_home(),
        )
        # إضافة زر الاستارت الدائم
        await update.message.reply_text("📌 اضغط الزر بالأسفل لإعادة تشغيل البوت:", reply_markup=main_keyboard)

# ==============================
# Callbacks
# ==============================
def seen_callback_already(callback_id: str) -> bool:
    if not callback_id:
        return False
    if callback_id in SEEN_CALLBACK_IDS:
        return True
    SEEN_CALLBACK_IDS.append(callback_id)
    return False

async def player_rules_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if seen_callback_already(q.id): return
    await q.answer()
    await q.edit_message_text(RULES_TEXT, parse_mode="Markdown")

async def player_register_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if seen_callback_already(q.id): return
    await q.answer()
    global is_open
    if not is_open:
        await q.edit_message_text("⚠️ التسجيل مغلق الآن.", reply_markup=kb_player_home())
        return
    if len(teams) >= MAX_TEAMS:
        await q.edit_message_text("🚫 اكتمل عدد الفرق! لا يمكن التسجيل الآن.", reply_markup=kb_player_home())
        return
    collecting[str(q.from_user.id)] = {"stage": "clan"}
    save_all()
    await q.edit_message_text("🏷️ أرسل الآن *اسم الكلان مثال : rageback*.", parse_mode="Markdown")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if seen_callback_already(q.id): return
    await q.answer()
    global is_open, ROOM_TIME, ROOM_CODE
    if q.from_user.id != ADMIN_CHAT_ID:
        await q.edit_message_text("❌ هذا الزر للأدمن فقط.")
        return

    data = q.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "open":
        await q.edit_message_text("⏰ أرسل موعد نزول الـ ID:")
        context.user_data["waiting_room_time"] = True
        return

    if action == "close":
        is_open = False
        save_all()
        await q.edit_message_text("🔴 تم إغلاق التسجيل.", reply_markup=kb_admin_home())
        return

    if action == "publish":
        text = build_list_text()
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
        await q.edit_message_text("✅ تم نشر اللستة.", reply_markup=kb_admin_home())
        return

    if action == "view_teams":
        text = build_list_text()
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb_admin_home())
        return

    if action == "accept" and len(parts) > 2:
        user_id = parts[2]
        if user_id in collecting:
            slot = len(teams) + 3   # يبدأ من 3 بدل 1
            if slot > 25:   # تأكد أنه ما يتجاوز 25
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="🚫 وصلت للحد الأقصى (25). ما تقدر تقبل فرق زيادة.")
                return
            team = {
                "slot": slot,
                "user_id": user_id,
                "clan": collecting[user_id]["clan"],
                "tag": collecting[user_id]["tag"],
                "country": collecting[user_id]["country"],
            }
            teams.append(team)
            del collecting[user_id]
            save_all()
            await context.bot.send_message(
                chat_id=user_id,
                text=(f"✅ تم قبول فريقك من قبل الإدارة!\n\n"
                      f"⏰ الموعد: *{ROOM_TIME}*\n"
                      f"🎟 الكود: `{ROOM_CODE}`"),
                parse_mode="Markdown"
            )
        await q.edit_message_text("✅ تم قبول الفريق.", reply_markup=kb_admin_home())
        return

    if action == "reject" and len(parts) > 2:
        user_id = parts[2]
        if user_id in collecting:
            del collecting[user_id]
            save_all()
        await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلب تسجيل فريقك من قبل الإدارة.")
        await q.edit_message_text("❌ تم رفض الفريق.", reply_markup=kb_admin_home())
        return

# ==============================
# جمع بيانات الفريق (للاعبين)
# ==============================
async def collect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_open
    user = update.effective_user
    uid = str(user.id)
    if uid not in collecting: return

    stage = collecting[uid]["stage"]

    if stage == "clan":
        collecting[uid]["clan"] = update.message.text.strip()
        collecting[uid]["stage"] = "tag"
        save_all()
        await update.message.reply_text("✳️ تم حفظ الاسم.\nأرسل *التوحيد مثال: reb*.", parse_mode="Markdown")
        return

    if stage == "tag":
        collecting[uid]["tag"] = update.message.text.strip()
        collecting[uid]["stage"] = "country"
        save_all()
        await update.message.reply_text("✳️ تم حفظ التاك.\nأرسل *إيموجي العلم مثال : 🇮🇶*.", parse_mode="Markdown")
        return

    if stage == "country":
        if len(teams) >= MAX_TEAMS:
            is_open = False
            save_all()
            await update.message.reply_text("🚫 اكتمل عدد الفرق، لا يمكن إضافة المزيد.")
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="⚠️ اكتمل عدد الفرق، تم إغلاق التسجيل تلقائيًا.")
            return

        collecting[uid]["country"] = update.message.text.strip()
        collecting[uid]["stage"] = "pending"
        save_all()
        await update.message.reply_text("✅ تم إرسال بياناتك. بانتظار موافقة الإدارة.", parse_mode="Markdown")

        # إرسال الطلب للأدمن للمراجعة
        text = (
            f"📥 *طلب تسجيل جديد:*\n\n"
            f"🏷️ الكلان: {collecting[uid]['clan']}\n"
            f"🔖 التوحيد: {collecting[uid]['tag']}\n"
            f"🏳️ الدولة: {collecting[uid]['country']}\n\n"
            "هل ترغب بالموافقة؟"
        )
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown",
            reply_markup=admin_action_buttons(uid)
        )

# ==============================
# إدخال الأدمن (موعد/كود الروم)
# ==============================
async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ROOM_TIME, ROOM_CODE, is_open
    if update.effective_user.id != ADMIN_CHAT_ID: return

    text = (update.message.text or "").strip()

    if context.user_data.get("waiting_room_time"):
        ROOM_TIME = text
        context.user_data.pop("waiting_room_time")
        context.user_data["waiting_room_code"] = True
        await update.message.reply_text("📌 الآن أرسل رمز الدخول للروم.")
        return

    if context.user_data.get("waiting_room_code"):
        ROOM_CODE = text
        context.user_data.pop("waiting_room_code")
        is_open = True
        save_all()
        await update.message.reply_text(
            f"🟢 تم فتح التسجيل.\n⏰ الموعد: *{ROOM_TIME}*\n🎟 الكود: `{ROOM_CODE}`",
            parse_mode="Markdown"
        )

# ==============================
# معالج موحد للرسائل النصية
# ==============================
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_CHAT_ID:
        await admin_input_handler(update, context)
    else:
        await collect_handler(update, context)

# ==============================
# تشغيل البوت
# ==============================
def main():
    load_all()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(player_rules_cb, pattern="^player:rules$"))
    app.add_handler(CallbackQueryHandler(player_register_cb, pattern="^player:register$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("✅ Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
