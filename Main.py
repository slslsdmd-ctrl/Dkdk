import os
import json
import time
import logging
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ========== ТОКЕН ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ ТОКЕН НЕ НАЙДЕН! Добавьте BOT_TOKEN в переменные окружения Bothost")

# ========== КОНФИГ ==========
ADMIN_ID = 8039111975
CASINO_NAME = "AZTEC BET"
TON_WALLET = "UQCvOIAt2X1PHfquND-LxzVYg0Gl3a_IExORwwPjowI3Nkb8"
MIN_WITHDRAW = 1

# ========== WEBAPP URL (GitHub Pages) ==========
WEBAPP_URL = "https://slslsdmd-ctrl.github.io/Dkdk/"

# ========== ЛОГИ ==========
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ДАННЫЕ ==========
users = {}
withdraw_requests = {}
DATA_FILE = "aztec_bet_data.json"
REQUESTS_FILE = "aztec_bet_requests.json"

def round_ton(amount):
    return round(amount, 4)

def load_data():
    global users, withdraw_requests
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                users = json.load(f)
                for uid in users:
                    users[uid]['balance'] = float(users[uid].get('balance', 0))
        if os.path.exists(REQUESTS_FILE):
            with open(REQUESTS_FILE, "r") as f:
                withdraw_requests = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(users, f, indent=2)
        with open(REQUESTS_FILE, "w") as f:
            json.dump(withdraw_requests, f, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

load_data()

async def ensure_user_exists(uid):
    if uid not in users:
        users[uid] = {"balance": 0}
        save_data()

# ========== ПОПОЛНЕНИЕ ==========
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "💎 **ПОПОЛНЕНИЕ** 💎\n\n"
            "Команда: `/deposit [СУММА]`\n"
            "Пример: `/deposit 10`\n\n"
            "Минимальная сумма: 0.1 TON",
            parse_mode="Markdown"
        )
        return
    
    try:
        amount = float(args[0])
        if amount < 0.1:
            await update.message.reply_text("❌ Минимальная сумма: 0.1 TON")
            return
    except:
        await update.message.reply_text("❌ Введите число")
        return
    
    deposit_id = f"{uid}_{int(time.time())}"
    await update.message.reply_text(
        f"💎 **ЗАЯВКА НА ПОПОЛНЕНИЕ** 💎\n\n"
        f"💰 Сумма: {amount} TON\n"
        f"📦 Кошелёк:\n`{TON_WALLET}`\n\n"
        f"📝 **В КОММЕНТАРИИ УКАЖИТЕ КОД:**\n`{deposit_id}`\n\n"
        f"✅ После перевода нажмите `/check_deposit {deposit_id}`",
        parse_mode="Markdown"
    )

async def check_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ /check_deposit [ID]")
        return
    
    await update.message.reply_text(
        "🔄 **ПРОВЕРКА ПЛАТЕЖА** 🔄\n\n"
        "Администратор проверит перевод и зачислит средства.\n"
        "Обычно это занимает до 24 часов.\n\n"
        "📞 По вопросам: @aztec_bet_support",
        parse_mode="Markdown"
    )

# ========== ВЫВОД СРЕДСТВ ==========
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "💸 **ВЫВОД СРЕДСТВ** 💸\n\n"
            "Команда: `/withdraw [СУММА] [АДРЕС]`\n"
            "Пример: `/withdraw 10 UQCvOIAt2X1PHfquND-LxzVYg0Gl3a_IExORwwPjowI3Nkb8`\n\n"
            "💰 Минимальная сумма: 1 TON\n"
            "⏱ Время вывода: до 72 часов",
            parse_mode="Markdown"
        )
        return
    
    try:
        amount = float(args[0])
        wallet = args[1]
        
        if amount < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ Минимальная сумма: {MIN_WITHDRAW} TON")
            return
        
        if len(wallet) != 48 or not wallet.startswith("UQ"):
            await update.message.reply_text("❌ Неверный адрес кошелька")
            return
        
        if users[uid]["balance"] < amount:
            await update.message.reply_text(f"❌ Недостаточно средств! Баланс: {round_ton(users[uid]['balance'])} TON")
            return
        
        users[uid]["balance"] -= amount
        rid = f"{uid}_{int(time.time())}"
        
        withdraw_requests[rid] = {
            "user_id": uid,
            "amount": amount,
            "wallet": wallet,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        save_data()
        
        await update.message.reply_text(
            f"✅ **ЗАЯВКА №{rid} ПРИНЯТА** ✅\n\n"
            f"💰 Сумма: {amount} TON\n"
            f"📦 Адрес: `{wallet}`\n"
            f"⏱ Время вывода: до 72 часов",
            parse_mode="Markdown"
        )
        
        await context.bot.send_message(
            ADMIN_ID,
            f"📝 **НОВАЯ ЗАЯВКА НА ВЫВОД**\n\n"
            f"🆔 ID: {rid}\n"
            f"👤 Пользователь: {uid}\n"
            f"💰 Сумма: {amount} TON\n"
            f"📦 Кошелёк: `{wallet}`",
            parse_mode="Markdown"
        )
        
    except:
        await update.message.reply_text("❌ Ошибка! Проверьте команду")

# ========== АДМИН КОМАНДЫ ==========
async def add_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("❌ /add_deposit [ID] [СУММА]")
        return
    uid, amount = args[0], float(args[1])
    await ensure_user_exists(uid)
    users[uid]["balance"] += amount
    save_data()
    await update.message.reply_text(f"✅ +{amount} TON пользователю {uid}")
    try:
        await context.bot.send_message(uid, f"✅ Пополнение {amount} TON зачислено!")
    except:
        pass

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        return
    rid = context.args[0]
    if rid in withdraw_requests and withdraw_requests[rid]["status"] == "pending":
        withdraw_requests[rid]["status"] = "approved"
        save_data()
        await update.message.reply_text(f"✅ {rid} ОДОБРЕНА")
        try:
            await context.bot.send_message(withdraw_requests[rid]["user_id"], f"✅ Заявка на вывод {withdraw_requests[rid]['amount']} TON одобрена!")
        except:
            pass

async def decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) != 1:
        return
    rid = context.args[0]
    if rid in withdraw_requests and withdraw_requests[rid]["status"] == "pending":
        uid = withdraw_requests[rid]["user_id"]
        amount = withdraw_requests[rid]["amount"]
        users[uid]["balance"] += amount
        withdraw_requests[rid]["status"] = "declined"
        save_data()
        await update.message.reply_text(f"❌ {rid} ОТКЛОНЕНА")
        try:
            await context.bot.send_message(uid, f"❌ Заявка на вывод {amount} TON отклонена. Средства возвращены.")
        except:
            pass

async def requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    pending = [rid for rid, req in withdraw_requests.items() if req.get("status") == "pending"]
    if not pending:
        await update.message.reply_text("📭 Нет активных заявок")
        return
    for rid in pending[:10]:
        req = withdraw_requests[rid]
        await update.message.reply_text(f"📝 {rid}\n👤 {req['user_id']}\n💰 {req['amount']} TON\n✅ /approve {rid}\n❌ /decline {rid}")

# ========== БАЛАНС ==========
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    await update.message.reply_text(f"💰 Баланс: {round_ton(users[uid]['balance'])} TON")

# ========== ГЛАВНОЕ МЕНЮ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    web_app = WebAppInfo(url=WEBAPP_URL)
    keyboard = [[KeyboardButton("🎮 ОТКРЫТЬ AZTEC BET", web_app=web_app)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🎰 **{CASINO_NAME}** 🎰\n\n"
        f"💰 Баланс: `{round_ton(users[uid]['balance'])} TON`\n\n"
        f"📋 **Команды:**\n"
        f"💎 `/deposit [СУММА]` - пополнить баланс\n"
        f"💸 `/withdraw [СУММА] [АДРЕС]` - вывести средства\n"
        f"💰 `/balance` - проверить баланс\n\n"
        f"👇 **Нажми на кнопку, чтобы открыть казино** 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ========== ОБРАБОТКА МИНИ-АПП ==========
async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.message.web_app_data.data)
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    if data['action'] == 'check_balance':
        await update.message.reply_text(f"💰 Баланс: {round_ton(users[uid]['balance'])} TON")
    
    elif data['action'] == 'game_result':
        amount = data['amount']
        users[uid]["balance"] += amount
        save_data()
        await update.message.reply_text(f"🎮 Результат игры: {'+' if amount > 0 else ''}{amount} TON\n💰 Новый баланс: {round_ton(users[uid]['balance'])} TON")
    
    elif data['action'] == 'deposit':
        await update.message.reply_text(
            f"💎 **ПОПОЛНЕНИЕ**\n\n"
            f"Отправьте TON на кошелёк:\n`{TON_WALLET}`\n\n"
            f"В комментарии укажите ваш ID: `{uid}`\n\n"
            f"После перевода администратор зачислит средства.",
            parse_mode="Markdown"
        )
    
    elif data['action'] == 'withdraw':
        await update.message.reply_text(
            f"💸 **ВЫВОД СРЕДСТВ**\n\n"
            f"Используйте команду: `/withdraw [СУММА] [АДРЕС]`",
            parse_mode="Markdown"
        )
    
    elif data['action'] == 'connect_wallet':
        await update.message.reply_text(
            f"🔗 **ПРИВЯЗКА КОШЕЛЬКА**\n\n"
            f"Ваш ID: `{uid}`\n"
            f"Кошелёк казино: `{TON_WALLET}`\n\n"
            f"Для пополнения отправьте TON на этот адрес.",
            parse_mode="Markdown"
        )

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("deposit", deposit))
    app.add_handler(CommandHandler("check_deposit", check_deposit))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("add_deposit", add_deposit))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("decline", decline))
    app.add_handler(CommandHandler("requests", requests))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))
    
    logger.info(f"✅ {CASINO_NAME} ЗАПУЩЕН!")
    app.run_polling()

if __name__ == "__main__":
    main()