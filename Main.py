import random
import json
import os
import time
import logging
import asyncio
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pytonconnect import TonConnect

# ========== ТОКЕН ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ ТОКЕН НЕ НАЙДЕН! Добавьте BOT_TOKEN в переменные окружения Bothost")

# ========== КОНФИГ ==========
ADMIN_ID = int(os.getenv("ADMIN_ID", 8039111975))
SUPPORT = "@aztec_bet_support"
CASINO_NAME = "AZTEC BET"
CHANNEL = "Aztec_wins"
CHANNEL_LINK = "https://t.me/Aztec_wins"
TON_WALLET = os.getenv("TON_WALLET", "UQCvOIAt2X1PHfquND-LxzVYg0Gl3a_IExORwwPjowI3Nkb8")
MIN_BET = 0.1
MIN_DEPOSIT = 0.1
MIN_WITHDRAW = 1
REFERRAL_DEPOSIT_PERCENT = 0.05

# ========== TON CONNECT ==========
MANIFEST_URL = "https://raw.githubusercontent.com/slslsdmd-ctrl/Dkdk/main/tonconnect-manifest.json"

class UserStorage:
    def __init__(self, user_id: str):
        self.file_path = f"wallet_{user_id}.json"

    async def set_item(self, key: str, value: str):
        with open(self.file_path, "w") as f:
            json.dump({key: value}, f)

    async def get_item(self, key: str, default=None):
        if not os.path.exists(self.file_path):
            return default
        with open(self.file_path, "r") as f:
            data = json.load(f)
        return data.get(key, default)

    async def remove_item(self, key: str):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

# ========== АЧИВКИ ==========
ACHIEVEMENTS = {
    "first_win": {"name": "🏆 ПЕРВАЯ ПОБЕДА", "desc": "Выиграть свою первую ставку"},
    "lucky_10": {"name": "🍀 ВЕЗУНЧИК", "desc": "Выиграть 10 раз подряд"},
    "slot_master": {"name": "🎰 МАСТЕР СЛОТОВ", "desc": "Сделать 1000 вращений в слотах"},
    "king_ref": {"name": "👑 КОРОЛЬ РЕФЕРАЛОВ", "desc": "Привести 50 друзей"},
    "millionaire": {"name": "💰 МИЛЛИОНЕР", "desc": "Накопить 100 TON на балансе"},
    "high_roller": {"name": "💎 ХАЙРОЛЛЕР", "desc": "Сделать ставку 100 TON за раз"},
    "all_games": {"name": "🎮 ПРОФЕССИОНАЛ", "desc": "Сыграть во все игры"},
}

# ========== ЛОГИ ==========
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ДАННЫЕ ==========
users = {}
withdraw_requests = {}
pending_deposits = {}
DATA_FILE = "aztec_bet_data.json"
REQUESTS_FILE = "aztec_bet_requests.json"
PENDING_FILE = "pending_deposits.json"

def round_ton(amount):
    return round(amount, 4)

def load_data():
    global users, withdraw_requests, pending_deposits
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                users = json.load(f)
                for uid in users:
                    users[uid]['balance'] = float(users[uid].get('balance', 0))
                    users[uid]['total_bet'] = float(users[uid].get('total_bet', 0))
                    users[uid]['total_win'] = float(users[uid].get('total_win', 0))
                    users[uid]['lang'] = users[uid].get('lang', 'ru')
                    users[uid]['stats'] = users[uid].get('stats', {
                        'coin': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
                        'number': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
                        'dice_sum': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
                        'dice_over': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
                        'dice_even': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
                        'slot': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0, 'spins': 0},
                        'roulette': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
                        'rps': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0, 'draws': 0},
                    })
                    users[uid]['achievements'] = users[uid].get('achievements', [])
                    users[uid]['win_streak'] = users[uid].get('win_streak', 0)
                    users[uid]['best_streak'] = users[uid].get('best_streak', 0)
                    users[uid]['last_reminder'] = users[uid].get('last_reminder')
        if os.path.exists(REQUESTS_FILE):
            with open(REQUESTS_FILE, "r") as f:
                withdraw_requests = json.load(f)
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "r") as f:
                pending_deposits = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(users, f, indent=2)
        with open(REQUESTS_FILE, "w") as f:
            json.dump(withdraw_requests, f, indent=2)
        with open(PENDING_FILE, "w") as f:
            json.dump(pending_deposits, f, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

load_data()

# ========== ПРОВЕРКА АЧИВОК ==========
async def check_achievements(uid):
    user = users[uid]
    new_achievements = []
    
    if user['total_win'] > 0 and "first_win" not in user['achievements']:
        user['achievements'].append("first_win")
        new_achievements.append("first_win")
    
    if user.get('win_streak', 0) >= 10 and "lucky_10" not in user['achievements']:
        user['achievements'].append("lucky_10")
        new_achievements.append("lucky_10")
    
    if user['stats']['slot']['spins'] >= 1000 and "slot_master" not in user['achievements']:
        user['achievements'].append("slot_master")
        new_achievements.append("slot_master")
    
    if len(user.get('referrals', [])) >= 50 and "king_ref" not in user['achievements']:
        user['achievements'].append("king_ref")
        new_achievements.append("king_ref")
    
    if user['balance'] >= 100 and "millionaire" not in user['achievements']:
        user['achievements'].append("millionaire")
        new_achievements.append("millionaire")
    
    games_played = sum(1 for g in user['stats'] if user['stats'][g]['total_bet'] > 0)
    if games_played >= 8 and "all_games" not in user['achievements']:
        user['achievements'].append("all_games")
        new_achievements.append("all_games")
    
    if new_achievements:
        save_data()
    
    return new_achievements

# ========== ОБНОВЛЕНИЕ СТАТИСТИКИ ==========
def update_game_stats(uid, game, won, bet, win_amount=0):
    user = users[uid]
    stats = user['stats'][game]
    stats['total_bet'] += bet
    if won:
        stats['wins'] += 1
        stats['total_win'] += win_amount
        user['win_streak'] += 1
        if user['win_streak'] > user['best_streak']:
            user['best_streak'] = user['win_streak']
    else:
        stats['losses'] += 1
        user['win_streak'] = 0
    if game == 'slot':
        stats['spins'] += 1
    if game == 'rps' and win_amount == 0:
        stats['draws'] = stats.get('draws', 0) + 1
    save_data()

# ========== НАПОМИНАНИЕ ==========
async def check_reminders(app):
    while True:
        await asyncio.sleep(43200)
        for uid, user in users.items():
            last_reminder = user.get('last_reminder')
            if last_reminder:
                last = datetime.fromisoformat(last_reminder)
                if datetime.now() - last < timedelta(hours=12):
                    continue
            try:
                await app.bot.send_message(
                    int(uid),
                    "🎰 **НАПОМИНАНИЕ!** 🎰\n\n"
                    "Ты давно не заходил в **AZTEC BET**!\n"
                    "Заходи и забирай свой выигрыш!\n\n"
                    "👉 @Aztec_wins_bot",
                    parse_mode="Markdown"
                )
                users[uid]['last_reminder'] = datetime.now().isoformat()
                save_data()
            except:
                pass

# ========== TON CONNECT ==========
async def connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    connector = TonConnect(manifest_url=MANIFEST_URL, storage=UserStorage(uid))
    await connector.restore_connection()
    
    if connector.connected:
        await update.message.reply_text(f"✅ Кошелёк уже подключён: `{connector.account.address}`", parse_mode="Markdown")
        return
    
    wallets = connector.get_wallets()
    if not wallets:
        await update.message.reply_text("❌ Установите Tonkeeper или другой TON кошелёк")
        return
    
    connect_url = await connector.connect(wallets[0])
    keyboard = [[InlineKeyboardButton("🔗 Подключить кошелёк", url=connect_url)]]
    await update.message.reply_text(
        "💎 **ПОДКЛЮЧЕНИЕ КОШЕЛЬКА** 💎\n\n"
        "Нажми на кнопку и подтверди в кошельке",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def pay_from_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ /pay [СУММА]\nПример: `/pay 10`", parse_mode="Markdown")
        return
    
    try:
        amount = float(args[0])
        if amount < 0.1:
            await update.message.reply_text("❌ Минимум 0.1 TON")
            return
    except:
        await update.message.reply_text("❌ Введите число")
        return
    
    connector = TonConnect(manifest_url=MANIFEST_URL, storage=UserStorage(uid))
    
    if not await connector.restore_connection():
        await update.message.reply_text("❌ Сначала подключи кошелёк: /connect")
        return
    
    transaction = {
        "valid_until": int(time.time() + 600),
        "messages": [{
            "address": TON_WALLET,
            "amount": str(int(amount * 1e9))
        }]
    }
    
    try:
        await connector.send_transaction(transaction)
        users[uid]["balance"] += amount
        users[uid]["total_deposit"] = users[uid].get("total_deposit", 0) + amount
        save_data()
        await update.message.reply_text(
            f"✅ +{amount} TON зачислено!\n💰 Новый баланс: {round_ton(users[uid]['balance'])} TON",
            reply_markup=main_menu(uid)
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ========== ПРОСТОЙ ПЕРЕВОД ==========
async def deposit_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "💎 **ПОПОЛНЕНИЕ ЧЕРЕЗ ПЕРЕВОД** 💎\n\n"
            "Команда: `/deposit [СУММА]`\n"
            "Пример: `/deposit 5.5`\n\n"
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
        await update.message.reply_text("❌ Введите число (например: 5.5)")
        return
    
    deposit_id = f"{uid}_{int(time.time())}"
    
    pending_deposits[deposit_id] = {
        "user_id": uid,
        "amount": amount,
        "timestamp": time.time(),
        "address": TON_WALLET,
        "status": "pending"
    }
    save_data()
    
    await update.message.reply_text(
        f"💎 **ЗАЯВКА НА ПОПОЛНЕНИЕ** 💎\n\n"
        f"💰 Сумма: {amount} TON\n"
        f"📦 Кошелёк:\n`{TON_WALLET}`\n\n"
        f"📝 **В КОММЕНТАРИИ УКАЖИТЕ КОД:**\n`{deposit_id}`\n\n"
        f"⏱ После перевода нажмите `/check_deposit {deposit_id}`\n\n"
        f"✅ После подтверждения средства зачислятся автоматически!",
        parse_mode="Markdown",
        reply_markup=main_menu(uid)
    )

async def check_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ /check_deposit [ID_ЗАЯВКИ]")
        return
    
    deposit_id = args[0]
    
    if deposit_id not in pending_deposits:
        await update.message.reply_text("❌ Заявка не найдена")
        return
    
    deposit = pending_deposits[deposit_id]
    if deposit["user_id"] != uid:
        await update.message.reply_text("❌ Это не ваша заявка")
        return
    
    if deposit["status"] == "completed":
        await update.message.reply_text("✅ Этот платёж уже зачислен!")
        return
    
    amount = deposit["amount"]
    users[uid]["balance"] += amount
    users[uid]["total_deposit"] = users[uid].get("total_deposit", 0) + amount
    deposit["status"] = "completed"
    save_data()
    
    await update.message.reply_text(
        f"✅ **ПЛАТЁЖ ПОДТВЕРЖДЁН!**\n\n"
        f"💰 +{amount} TON зачислено!\n"
        f"💎 Новый баланс: {round_ton(users[uid]['balance'])} TON",
        reply_markup=main_menu(uid),
        parse_mode="Markdown"
    )

# ========== ПЕРЕВОДЫ ==========
TEXTS = {
    'ru': {
        'welcome': "🎰 ДОБРО ПОЖАЛОВАТЬ В {}\n\nПРИВЕТ, {}!\n💰 БАЛАНС: {} TON\n📢 КАНАЛ: {}",
        'balance': "💰 БАЛАНС: {} TON",
        'stats': "📊 СТАТИСТИКА\n\nСТАВОК: {}\nПОСТАВЛЕНО: {} TON\nВЫИГРАНО: {} TON\n🔥 ЛУЧШАЯ СЕРИЯ: {}",
        'deposit': "💎 ПОПОЛНЕНИЕ\n\n/deposit [СУММА]\n/connect - подключить кошелёк\n/pay [СУММА] - оплата из кошелька",
        'withdraw': "💸 ВЫВОД\n\n/withdraw [СУММА] [АДРЕС]",
        'support': "📞 ПОДДЕРЖКА: {}",
        'referral': "🤝 РЕФЕРАЛЫ\n\nПРИГЛАШЁННЫХ: {}\nЗАРАБОТАНО: {} TON\n\nССЫЛКА: t.me/{}?start={}",
        'min_bet_error': "❌ МИНИМУМ {} TON",
        'no_money': "❌ НЕДОСТАТОЧНО СРЕДСТВ",
        'win': "🎉 ПОБЕДА! +{} TON",
        'lose': "😢 ПРОИГРЫШ! -{} TON",
        'draw': "😐 НИЧЬЯ",
        'choose_bet': "ВЫБЕРИТЕ СТАВКУ:",
        'choose_side': "ВЫБЕРИТЕ СТОРОНУ:",
        'choose_number': "ВЫБЕРИТЕ ЧИСЛО (1-10):",
        'choose_sum': "ВЫБЕРИТЕ СУММУ (2-12):",
        'enter_custom_bet': "💎 ВВЕДИТЕ СУММУ СТАВКИ:",
        'coin': "🪙 МОНЕТКА (x2)",
        'number': "🔢 УГАДАЙ ЧИСЛО (x3)",
        'dice_sum': "🎲 КОСТИ (СУММА) (x3)",
        'dice_over': "🎲 КОСТИ (БОЛЬШЕ/МЕНЬШЕ 7) (x2)",
        'dice_even': "🎲 КОСТИ (ЧЁТ/НЕЧЕТ) (x2)",
        'slot': "🎰 СЛОТЫ (x5 max)",
        'roulette': "🎡 РУЛЕТКА",
        'rps': "✂️ КАМЕНЬ-НОЖНИЦЫ-БУМАГА (x2)",
        'back': "⬅️ Назад",
        'games': "🎮 ИГРЫ",
        'demo': "🎮 ДЕМО-РЕЖИМ",
        'heads': "🪨 ОРЕЛ",
        'tails': "📄 РЕШКА",
        'rock': "🪨 КАМЕНЬ",
        'scissors': "✂️ НОЖНИЦЫ",
        'paper': "📄 БУМАГА",
        'red': "🔴 КРАСНОЕ (x2)",
        'black': "⚫ ЧЁРНОЕ (x2)",
        'number_bet': "🔢 ЧИСЛО (x36)",
        'slot_result': "🎰 СЛОТЫ\n\n{} {} {}\n{}",
        'dice_result': "🎲 КОСТИ\n\n{} + {} = {}\n{}",
        'rps_result': "✂️ КНБ\n\nВЫ: {}  БОТ: {}\n{}",
        'roulette_result': "🎡 РУЛЕТКА\n\nВЫПАЛО: {}\n{}",
        'top': "🏆 ТОП-{} ЛИДЕРОВ 🏆\n\n{}",
        'my_stats': "📊 МОЯ СТАТИСТИКА 📊\n\n{}",
        'achievements': "🏅 АЧИВКИ 🏅\n\n{}",
        'channel': "📢 КАНАЛ\n\n{}",
    },
    'en': {
        'welcome': "🎰 WELCOME TO {}\n\nHELLO, {}!\n💰 BALANCE: {} TON\n📢 CHANNEL: {}",
        'balance': "💰 BALANCE: {} TON",
        'stats': "📊 STATISTICS\n\nBETS: {}\nBETTED: {} TON\nWON: {} TON\n🔥 BEST STREAK: {}",
        'deposit': "💎 DEPOSIT\n\n/deposit [AMOUNT]\n/connect - connect wallet\n/pay [AMOUNT]",
        'withdraw': "💸 WITHDRAW\n\n/withdraw [AMOUNT] [ADDRESS]",
        'support': "📞 SUPPORT: {}",
        'referral': "🤝 REFERRALS\n\nREFERRALS: {}\nEARNED: {} TON\n\nLINK: t.me/{}?start={}",
        'min_bet_error': "❌ MINIMUM {} TON",
        'no_money': "❌ INSUFFICIENT FUNDS",
        'win': "🎉 WIN! +{} TON",
        'lose': "😢 LOSS! -{} TON",
        'draw': "😐 DRAW",
        'choose_bet': "CHOOSE BET:",
        'choose_side': "CHOOSE SIDE:",
        'choose_number': "CHOOSE NUMBER (1-10):",
        'choose_sum': "CHOOSE SUM (2-12):",
        'enter_custom_bet': "💎 ENTER BET AMOUNT:",
        'coin': "🪙 COIN FLIP (x2)",
        'number': "🔢 GUESS NUMBER (x3)",
        'dice_sum': "🎲 DICE (SUM) (x3)",
        'dice_over': "🎲 DICE (OVER/UNDER 7) (x2)",
        'dice_even': "🎲 DICE (EVEN/ODD) (x2)",
        'slot': "🎰 SLOTS (x5 max)",
        'roulette': "🎡 ROULETTE",
        'rps': "✂️ RPS (x2)",
        'back': "⬅️ Back",
        'games': "🎮 GAMES",
        'demo': "🎮 DEMO MODE",
        'heads': "🪨 HEADS",
        'tails': "📄 TAILS",
        'rock': "🪨 ROCK",
        'scissors': "✂️ SCISSORS",
        'paper': "📄 PAPER",
        'red': "🔴 RED (x2)",
        'black': "⚫ BLACK (x2)",
        'number_bet': "🔢 NUMBER (x36)",
        'slot_result': "🎰 SLOTS\n\n{} {} {}\n{}",
        'dice_result': "🎲 DICE\n\n{} + {} = {}\n{}",
        'rps_result': "✂️ RPS\n\nYOU: {}  BOT: {}\n{}",
        'roulette_result': "🎡 ROULETTE\n\nRESULT: {}\n{}",
        'top': "🏆 TOP-{} LEADERS 🏆\n\n{}",
        'my_stats': "📊 MY STATISTICS 📊\n\n{}",
        'achievements': "🏅 ACHIEVEMENTS 🏅\n\n{}",
        'channel': "📢 CHANNEL\n\n{}",
    }
}

def get_text(uid, key, *args):
    lang = users.get(uid, {}).get('lang', 'ru')
    text = TEXTS.get(lang, TEXTS['ru']).get(key, key)
    if args:
        return text.format(*args)
    return text

# ========== КНОПКИ ==========
def get_bet_buttons(uid):
    return [
        [InlineKeyboardButton("0.1 TON", callback_data="bet_0.1")],
        [InlineKeyboardButton("1 TON", callback_data="bet_1")],
        [InlineKeyboardButton("5 TON", callback_data="bet_5")],
        [InlineKeyboardButton("10 TON", callback_data="bet_10")],
        [InlineKeyboardButton("✏️ ДРУГАЯ", callback_data="bet_custom")],
        [InlineKeyboardButton(get_text(uid, 'back'), callback_data="back")]
    ]

def main_menu(uid):
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("🏆 Топ лидеров", callback_data="top")],
        [InlineKeyboardButton("🏅 Ачивки", callback_data="achievements")],
        [InlineKeyboardButton("📈 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton("💎 Пополнить", callback_data="deposit_menu")],
        [InlineKeyboardButton("🎰 Игры", callback_data="games_menu")],
        [InlineKeyboardButton("💸 Вывести", callback_data="withdraw_menu")],
        [InlineKeyboardButton("🔗 TON Connect", callback_data="wallet_menu")],
        [InlineKeyboardButton("🎁 Демо", callback_data="demo_mode")],
        [InlineKeyboardButton("🤝 Рефералы", callback_data="referral")],
        [InlineKeyboardButton("📢 Канал", callback_data="channel")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton("🌐 English / Русский", callback_data="change_lang")]
    ]
    return InlineKeyboardMarkup(keyboard)

def deposit_menu(uid):
    keyboard = [
        [InlineKeyboardButton("💎 Обычный перевод", callback_data="deposit_simple")],
        [InlineKeyboardButton("🔗 TON Connect", callback_data="deposit_connect")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def wallet_menu(uid):
    keyboard = [
        [InlineKeyboardButton("🔗 Подключить кошелёк", callback_data="connect_wallet")],
        [InlineKeyboardButton("💰 Оплатить", callback_data="pay_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def games_menu(uid):
    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data="game_coin")],
        [InlineKeyboardButton("🔢 Угадай число", callback_data="game_number")],
        [InlineKeyboardButton("🎲 Сумма костей", callback_data="game_dice_sum")],
        [InlineKeyboardButton("🎲 Больше/Меньше 7", callback_data="game_dice_over")],
        [InlineKeyboardButton("🎲 Чёт/Нечет", callback_data="game_dice_even")],
        [InlineKeyboardButton("🎰 Слоты", callback_data="game_slot")],
        [InlineKeyboardButton("🎡 Рулетка", callback_data="game_roulette")],
        [InlineKeyboardButton("✂️ КНБ", callback_data="game_rps")],
        [InlineKeyboardButton(get_text(uid, 'back'), callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def demo_menu(uid):
    keyboard = [
        [InlineKeyboardButton("🪙 Монетка", callback_data="demo_coin")],
        [InlineKeyboardButton("🔢 Угадай число", callback_data="demo_number")],
        [InlineKeyboardButton("🎲 Сумма костей", callback_data="demo_dice_sum")],
        [InlineKeyboardButton("🎲 Больше/Меньше", callback_data="demo_dice_over")],
        [InlineKeyboardButton("🎲 Чёт/Нечет", callback_data="demo_dice_even")],
        [InlineKeyboardButton(get_text(uid, 'back'), callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def roulette_menu(uid):
    keyboard = [
        [InlineKeyboardButton("🔴 КРАСНОЕ (x2)", callback_data="roulette_red")],
        [InlineKeyboardButton("⚫ ЧЁРНОЕ (x2)", callback_data="roulette_black")],
        [InlineKeyboardButton("🔢 ЧИСЛО (x36)", callback_data="roulette_number")],
        [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
async def ensure_user_exists(uid):
    if uid not in users:
        users[uid] = {"balance": 0, "total_bet": 0, "total_win": 0, "spins": 0, "referrer": None, "referrals": [], "total_ref_earnings": 0, "total_deposit": 0, "lang": "ru", "win_streak": 0, "best_streak": 0, "last_reminder": None, "achievements": [], "stats": {
            'coin': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
            'number': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
            'dice_sum': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
            'dice_over': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
            'dice_even': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
            'slot': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0, 'spins': 0},
            'roulette': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0},
            'rps': {'wins': 0, 'losses': 0, 'total_bet': 0, 'total_win': 0, 'draws': 0},
        }}
        save_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    name = update.effective_user.first_name or "Player"
    ref = context.args[0] if context.args else None
    await ensure_user_exists(uid)
    
    if ref and ref != uid and ref in users and not users[uid].get("referrer"):
        users[uid]["referrer"] = ref
        if "referrals" not in users[ref]:
            users[ref]["referrals"] = []
        if uid not in users[ref]["referrals"]:
            users[ref]["referrals"].append(uid)
            users[ref]["balance"] += 0.1
            users[ref]["total_ref_earnings"] = users[ref].get("total_ref_earnings", 0) + 0.1
            save_data()
            try:
                await context.bot.send_message(ref, f"🎉 +0.1 TON! {name} перешёл по твоей ссылке!")
            except:
                pass
    
    await update.message.reply_text(get_text(uid, 'welcome', CASINO_NAME, name, round_ton(users[uid]['balance']), CHANNEL_LINK), reply_markup=main_menu(uid))

async def lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        uid = str(query.from_user.id)
        message = query.message
    else:
        uid = str(update.effective_user.id)
        message = update.message
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await message.reply_text("🌐 ВЫБЕРИТЕ ЯЗЫК / CHOOSE LANGUAGE:", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    lang = query.data.split("_")[1]
    await ensure_user_exists(uid)
    users[uid]['lang'] = lang
    save_data()
    await query.message.edit_text(get_text(uid, 'welcome', CASINO_NAME, query.from_user.first_name, round_ton(users[uid]['balance']), CHANNEL_LINK), reply_markup=main_menu(uid))

async def top_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('total_win', 0), reverse=True)[:100]
    
    message_text = ""
    for i, (user_id, data) in enumerate(sorted_users[:100], 1):
        try:
            user = await context.bot.get_chat(int(user_id))
            name = user.first_name or "Player"
        except:
            name = user_id[:8]
        
        medal = ""
        if i == 1:
            medal = "👑 "
        elif i == 2:
            medal = "🥈 "
        elif i == 3:
            medal = "🥉 "
        
        message_text += f"{medal}{i}. {name[:15]} — {round_ton(data.get('total_win', 0))} TON\n"
    
    await update.message.reply_text(get_text(uid, 'top', 100, message_text), reply_markup=main_menu(uid))

async def my_game_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    stats = users[uid]['stats']
    stats_text = ""
    games_names = {
        'coin': '🪙 Монетка',
        'number': '🔢 Угадай число',
        'dice_sum': '🎲 Сумма костей',
        'dice_over': '🎲 Больше/Меньше 7',
        'dice_even': '🎲 Чёт/Нечет',
        'slot': '🎰 Слоты',
        'roulette': '🎡 Рулетка',
        'rps': '✂️ КНБ',
    }
    
    for game, name in games_names.items():
        data = stats[game]
        total = data['wins'] + data['losses'] + data.get('draws', 0)
        if total > 0:
            win_rate = (data['wins'] / total * 100) if total > 0 else 0
            stats_text += f"\n{name}:\n   🎯 Игр: {total}\n   🏆 Побед: {data['wins']}\n   📉 Поражений: {data['losses']}\n   📈 WinRate: {win_rate:.1f}%\n"
    
    if not stats_text:
        stats_text = "📭 НЕТ ДАННЫХ"
    
    await update.message.reply_text(get_text(uid, 'my_stats', stats_text), reply_markup=main_menu(uid))

async def achievements_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    
    user_achievements = users[uid].get('achievements', [])
    text = ""
    for ach_id, ach in ACHIEVEMENTS.items():
        status = "✅" if ach_id in user_achievements else "❌"
        text += f"{status} {ach['name']}\n   → {ach['desc']}\n\n"
    
    await update.message.reply_text(get_text(uid, 'achievements', text), reply_markup=main_menu(uid))

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    await update.message.reply_text(get_text(uid, 'balance', round_ton(users[uid]['balance'])), reply_markup=main_menu(uid))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    await update.message.reply_text(get_text(uid, 'stats', users[uid]['spins'], round_ton(users[uid]['total_bet']), round_ton(users[uid]['total_win']), users[uid].get('best_streak', 0)), reply_markup=main_menu(uid))

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    await update.message.reply_text(get_text(uid, 'support', SUPPORT), reply_markup=main_menu(uid))

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    bot = (await context.bot.get_me()).username
    await update.message.reply_text(get_text(uid, 'referral', len(users[uid].get('referrals', [])), round_ton(users[uid].get('total_ref_earnings', 0)), bot, uid), reply_markup=main_menu(uid))

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(get_text(uid, 'withdraw'))
        return
    try:
        amount = float(args[0])
        wallet = args[1]
        if amount < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ МИНИМУМ {MIN_WITHDRAW} TON")
            return
        if len(wallet) != 48 or not wallet.startswith("UQ"):
            await update.message.reply_text("❌ НЕВЕРНЫЙ АДРЕС")
            return
        if users[uid]["balance"] < amount:
            await update.message.reply_text(get_text(uid, 'no_money'))
            return
        users[uid]["balance"] -= amount
        rid = f"{uid}_{int(time.time())}"
        withdraw_requests[rid] = {"user_id": uid, "amount": amount, "wallet": wallet, "status": "pending"}
        save_data()
        await update.message.reply_text(f"✅ ЗАЯВКА {rid} ПРИНЯТА\n⏱ ДО 72 ЧАСОВ", reply_markup=main_menu(uid))
        await context.bot.send_message(ADMIN_ID, f"📝 ЗАЯВКА {rid}\n👤 {uid}\n💰 {amount} TON\n✅ /approve {rid}\n❌ /decline {rid}")
    except:
        await update.message.reply_text("❌ ОШИБКА")

async def channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await ensure_user_exists(uid)
    await update.message.reply_text(get_text(uid, 'channel', CHANNEL_LINK), reply_markup=main_menu(uid))

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
    users[uid]["total_deposit"] = users[uid].get("total_deposit", 0) + amount
    save_data()
    await update.message.reply_text(f"✅ +{amount} TON {uid}")
    await context.bot.send_message(uid, f"✅ ПОПОЛНЕНИЕ {amount} TON")
    ref = users[uid].get("referrer")
    if ref and ref in users:
        bonus = amount * REFERRAL_DEPOSIT_PERCENT
        users[ref]["balance"] += bonus
        users[ref]["total_ref_earnings"] = users[ref].get("total_ref_earnings", 0) + bonus
        save_data()
        await context.bot.send_message(ref, f"🎉 РЕФЕРАЛ ПОПОЛНИЛ {amount} TON\n+{bonus} TON")

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

# ========== ИГРЫ МЕНЮ ==========
async def game_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'coin'
    await query.message.edit_text(get_text(uid, 'coin'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

async def game_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'number'
    await query.message.edit_text(get_text(uid, 'number'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

async def game_dice_sum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'dice_sum'
    await query.message.edit_text(get_text(uid, 'dice_sum'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

async def game_dice_over(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'dice_over'
    await query.message.edit_text(get_text(uid, 'dice_over'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

async def game_dice_even(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'dice_even'
    await query.message.edit_text(get_text(uid, 'dice_even'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

async def game_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'slot'
    await query.message.edit_text(get_text(uid, 'slot'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

async def game_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    await query.message.edit_text(get_text(uid, 'roulette'), reply_markup=roulette_menu(uid))

async def game_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    context.user_data['current_game'] = 'rps'
    await query.message.edit_text(get_text(uid, 'rps'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))

# ========== ОБРАБОТКА СТАВОК ==========
async def handle_bet_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    data = query.data
    game = context.user_data.get('current_game')
    
    bet_map = {"bet_0.1": 0.1, "bet_1": 1, "bet_5": 5, "bet_10": 10}
    
    if data in bet_map:
        bet = bet_map[data]
    elif data == "bet_custom":
        context.user_data['awaiting_bet'] = game
        await query.message.edit_text(get_text(uid, 'enter_custom_bet'), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_text(uid, 'back'), callback_data="back")]]))
        return
    else:
        return
    
    if bet < MIN_BET:
        await query.message.edit_text(get_text(uid, 'min_bet_error', MIN_BET))
        return
    if users[uid]["balance"] < bet:
        await query.message.edit_text(get_text(uid, 'no_money'))
        return
    
    context.user_data['bet_amount'] = bet
    
    if game == 'coin':
        keyboard = [[InlineKeyboardButton("🪨 ОРЕЛ", callback_data="coin_heads"), InlineKeyboardButton("📄 РЕШКА", callback_data="coin_tails")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
        await query.message.edit_text(f"{get_text(uid, 'coin')}\n\n{get_text(uid, 'choose_side')}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif game == 'number':
        keyboard = []
        row = []
        for i in range(1, 11):
            row.append(InlineKeyboardButton(str(i), callback_data=f"num_{i}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")])
        await query.message.edit_text(f"{get_text(uid, 'number')}\n\n{get_text(uid, 'choose_number')}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif game == 'dice_sum':
        keyboard = []
        row = []
        for i in range(2, 13):
            row.append(InlineKeyboardButton(str(i), callback_data=f"dice_sum_{i}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")])
        await query.message.edit_text(f"{get_text(uid, 'dice_sum')}\n\n{get_text(uid, 'choose_sum')}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif game == 'dice_over':
        keyboard = [[InlineKeyboardButton("📈 БОЛЬШЕ 7", callback_data="dice_over_more"), InlineKeyboardButton("📉 МЕНЬШЕ 7", callback_data="dice_over_less")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
        await query.message.edit_text(f"{get_text(uid, 'dice_over')}\n\n{get_text(uid, 'choose_choice')}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif game == 'dice_even':
        keyboard = [[InlineKeyboardButton("✅ ЧЁТ", callback_data="dice_even_even"), InlineKeyboardButton("❌ НЕЧЕТ", callback_data="dice_even_odd")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
        await query.message.edit_text(f"{get_text(uid, 'dice_even')}\n\n{get_text(uid, 'choose_choice')}", reply_markup=InlineKeyboardMarkup(keyboard))
    elif game == 'slot':
        await play_slot(update, context, bet)
    elif game == 'rps':
        keyboard = [[InlineKeyboardButton("🪨 КАМЕНЬ", callback_data="rps_rock"), InlineKeyboardButton("✂️ НОЖНИЦЫ", callback_data="rps_scissors"), InlineKeyboardButton("📄 БУМАГА", callback_data="rps_paper")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
        await query.message.edit_text(f"{get_text(uid, 'rps')}\n\n{get_text(uid, 'choose_choice')}", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_custom_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    game = context.user_data.get('awaiting_bet')
    if not game:
        return
    try:
        bet = float(update.message.text)
        if bet < MIN_BET:
            await update.message.reply_text(f"❌ МИНИМУМ {MIN_BET} TON")
            return
        if users[uid]["balance"] < bet:
            await update.message.reply_text(get_text(uid, 'no_money'))
            return
        context.user_data['bet_amount'] = bet
        context.user_data['awaiting_bet'] = None
        if game == 'coin':
            keyboard = [[InlineKeyboardButton("🪨 ОРЕЛ", callback_data="coin_heads"), InlineKeyboardButton("📄 РЕШКА", callback_data="coin_tails")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
            await update.message.reply_text(f"{get_text(uid, 'coin')}\n\n{get_text(uid, 'choose_side')}", reply_markup=InlineKeyboardMarkup(keyboard))
        elif game == 'number':
            keyboard = []
            row = []
            for i in range(1, 11):
                row.append(InlineKeyboardButton(str(i), callback_data=f"num_{i}"))
                if len(row) == 5:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")])
            await update.message.reply_text(f"{get_text(uid, 'number')}\n\n{get_text(uid, 'choose_number')}", reply_markup=InlineKeyboardMarkup(keyboard))
        elif game == 'dice_sum':
            keyboard = []
            row = []
            for i in range(2, 13):
                row.append(InlineKeyboardButton(str(i), callback_data=f"dice_sum_{i}"))
                if len(row) == 4:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")])
            await update.message.reply_text(f"{get_text(uid, 'dice_sum')}\n\n{get_text(uid, 'choose_sum')}", reply_markup=InlineKeyboardMarkup(keyboard))
        elif game == 'dice_over':
            keyboard = [[InlineKeyboardButton("📈 БОЛЬШЕ 7", callback_data="dice_over_more"), InlineKeyboardButton("📉 МЕНЬШЕ 7", callback_data="dice_over_less")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
            await update.message.reply_text(f"{get_text(uid, 'dice_over')}\n\n{get_text(uid, 'choose_choice')}", reply_markup=InlineKeyboardMarkup(keyboard))
        elif game == 'dice_even':
            keyboard = [[InlineKeyboardButton("✅ ЧЁТ", callback_data="dice_even_even"), InlineKeyboardButton("❌ НЕЧЕТ", callback_data="dice_even_odd")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
            await update.message.reply_text(f"{get_text(uid, 'dice_even')}\n\n{get_text(uid, 'choose_choice')}", reply_markup=InlineKeyboardMarkup(keyboard))
        elif game == 'slot':
            await play_slot(update, context, bet)
        elif game == 'rps':
            keyboard = [[InlineKeyboardButton("🪨 КАМЕНЬ", callback_data="rps_rock"), InlineKeyboardButton("✂️ НОЖНИЦЫ", callback_data="rps_scissors"), InlineKeyboardButton("📄 БУМАГА", callback_data="rps_paper")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="games_menu")]]
            await update.message.reply_text(f"{get_text(uid, 'rps')}\n\n{get_text(uid, 'choose_choice')}", reply_markup=InlineKeyboardMarkup(keyboard))
    except:
        await update.message.reply_text(f"❌ ВВЕДИТЕ ЧИСЛО (минимум {MIN_BET})")

# ========== ИГРЫ ==========
async def play_coin(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    result = random.choice(["орел", "решка"])
    won = choice == result
    if won:
        win = bet * 2
        msg = get_text(uid, 'win', round_ton(win))
    else:
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'coin', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(f"{get_text(uid, 'coin')}\n\nВАШ ВЫБОР: {choice}\nВЫПАЛО: {result}\n{msg}{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_number(update: Update, context: ContextTypes.DEFAULT_TYPE, guess):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    number = random.randint(1, 10)
    won = guess == number
    if won:
        win = bet * 3
        msg = get_text(uid, 'win', round_ton(win))
    else:
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'number', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(f"{get_text(uid, 'number')}\n\nВАШЕ ЧИСЛО: {guess}\nВЫПАЛО: {number}\n{msg}{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_dice_sum(update: Update, context: ContextTypes.DEFAULT_TYPE, guess):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    d1, d2 = random.randint(1,6), random.randint(1,6)
    total = d1 + d2
    won = guess == total
    if won:
        win = bet * 3
        msg = get_text(uid, 'win', round_ton(win))
    else:
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'dice_sum', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(get_text(uid, 'dice_result', d1, d2, total, msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_dice_over(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    d1, d2 = random.randint(1,6), random.randint(1,6)
    total = d1 + d2
    if (choice == "more" and total > 7) or (choice == "less" and total < 7):
        won = True
        win = bet * 2
        msg = get_text(uid, 'win', round_ton(win))
    elif total == 7:
        won = False
        win = 0
        msg = get_text(uid, 'draw')
    else:
        won = False
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'dice_over', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(get_text(uid, 'dice_result', d1, d2, total, msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_dice_even(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    d1, d2 = random.randint(1,6), random.randint(1,6)
    total = d1 + d2
    is_even = total % 2 == 0
    won = (choice == "even" and is_even) or (choice == "odd" and not is_even)
    if won:
        win = bet * 2
        msg = get_text(uid, 'win', round_ton(win))
    else:
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'dice_even', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(get_text(uid, 'dice_result', d1, d2, total, msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_slot(update, context, bet):
    query = update.callback_query if hasattr(update, 'callback_query') else None
    if query:
        uid = str(query.from_user.id)
        msg_func = query.message.edit_text
    else:
        uid = str(update.effective_user.id)
        msg_func = update.message.reply_text
    
    symbols = ["🍒", "🍋", "🍊", "🍉", "💎", "7️⃣", "⭐", "🎰"]
    s1, s2, s3 = random.choice(symbols), random.choice(symbols), random.choice(symbols)
    mult = 0
    if s1 == s2 == s3:
        if s1 in ["7️⃣", "💎", "🎰"]:
            mult = 5
        elif s1 == "🍉":
            mult = 4
        elif s1 in ["🍒", "🍋", "🍊"]:
            mult = 3
        elif s1 == "⭐":
            mult = 2
    if mult > 0:
        win = bet * mult
        msg = f"🎉 ВЫИГРЫШ +{round_ton(win)} TON (x{mult})"
        won = True
    else:
        win = -bet
        msg = f"😢 ПРОИГРЫШ -{round_ton(bet)} TON"
        won = False
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'slot', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await msg_func(get_text(uid, 'slot_result', s1, s2, s3, msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_rps(update: Update, context: ContextTypes.DEFAULT_TYPE, player):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    choices = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
    names = {"rock": "КАМЕНЬ", "scissors": "НОЖНИЦЫ", "paper": "БУМАГА"}
    bot = random.choice(["rock", "scissors", "paper"])
    if player == bot:
        won = False
        win = 0
        msg = get_text(uid, 'draw')
    elif (player == "rock" and bot == "scissors") or (player == "scissors" and bot == "paper") or (player == "paper" and bot == "rock"):
        won = True
        win = bet * 2
        msg = get_text(uid, 'win', round_ton(win))
    else:
        won = False
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'rps', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(get_text(uid, 'rps_result', names[player], names[bot], msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_roulette_color(update: Update, context: ContextTypes.DEFAULT_TYPE, user_choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    red = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    black = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
    
    if random.random() < 0.33:
        if user_choice == "red":
            num = random.choice(red)
            win = bet * 2
            msg = get_text(uid, 'win', round_ton(win))
            won = True
        else:
            num = random.choice(black)
            win = bet * 2
            msg = get_text(uid, 'win', round_ton(win))
            won = True
    else:
        if random.random() < 0.1:
            num = 0
        else:
            num = random.choice(black if user_choice == "red" else red)
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
        won = False
    
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'roulette', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(get_text(uid, 'roulette_result', num, msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

async def play_roulette_number(update: Update, context: ContextTypes.DEFAULT_TYPE, guess):
    query = update.callback_query
    uid = str(query.from_user.id)
    bet = context.user_data.get('bet_amount', 0)
    num = random.randint(0, 36)
    if guess == num:
        win = bet * 36
        msg = f"🎉 ДЖЕКПОТ! +{round_ton(win)} TON"
        won = True
    else:
        win = -bet
        msg = get_text(uid, 'lose', round_ton(bet))
        won = False
    
    users[uid]["balance"] += win
    users[uid]["total_bet"] += bet
    if win > 0:
        users[uid]["total_win"] += win
    users[uid]["spins"] += 1
    update_game_stats(uid, 'roulette', won, bet, win if win > 0 else 0)
    save_data()
    
    new_achievements = await check_achievements(uid)
    ach_msg = ""
    for ach in new_achievements:
        ach_msg += f"\n\n{ACHIEVEMENTS[ach]['name']}"
    
    await query.message.edit_text(get_text(uid, 'roulette_result', num, msg) + f"{ach_msg}\n\n💰 {get_text(uid, 'balance', round_ton(users[uid]['balance']))}", reply_markup=main_menu(uid))

# ========== ДЕМО ИГРЫ ==========
async def demo_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    keyboard = [[InlineKeyboardButton("🪨 ОРЕЛ", callback_data="demo_coin_heads"), InlineKeyboardButton("📄 РЕШКА", callback_data="demo_coin_tails")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="demo_mode")]]
    await query.message.edit_text("🪙 ДЕМО МОНЕТКА\n\nВЫБЕРИТЕ СТОРОНУ:", reply_markup=InlineKeyboardMarkup(keyboard))

async def demo_play_coin(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    result = random.choice(["орел", "решка"])
    msg = "🎉 ПОБЕДА!" if choice == result else "😢 ПРОИГРЫШ!"
    await query.message.edit_text(f"🪙 ДЕМО МОНЕТКА\n\nВАШ ВЫБОР: {choice}\nВЫПАЛО: {result}\n{msg}\n\n💎 ДЕМО-РЕЖИМ: БАЛАНС НЕ ИЗМЕНЯЕТСЯ", reply_markup=demo_menu(uid))

async def demo_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    keyboard = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"demo_num_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_text(uid, 'back'), callback_data="demo_mode")])
    await query.message.edit_text("🔢 ДЕМО УГАДАЙ ЧИСЛО\n\nВЫБЕРИТЕ ЧИСЛО (1-10):", reply_markup=InlineKeyboardMarkup(keyboard))

async def demo_play_number(update: Update, context: ContextTypes.DEFAULT_TYPE, guess):
    query = update.callback_query
    uid = str(query.from_user.id)
    number = random.randint(1, 10)
    msg = "🎉 ПОБЕДА!" if guess == number else "😢 ПРОИГРЫШ!"
    await query.message.edit_text(f"🔢 ДЕМО УГАДАЙ ЧИСЛО\n\nВАШЕ ЧИСЛО: {guess}\nВЫПАЛО: {number}\n{msg}\n\n💎 ДЕМО-РЕЖИМ: БАЛАНС НЕ ИЗМЕНЯЕТСЯ", reply_markup=demo_menu(uid))

async def demo_dice_sum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    keyboard = []
    row = []
    for i in range(2, 13):
        row.append(InlineKeyboardButton(str(i), callback_data=f"demo_dice_sum_{i}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_text(uid, 'back'), callback_data="demo_mode")])
    await query.message.edit_text("🎲 ДЕМО КОСТИ (СУММА)\n\nВЫБЕРИТЕ СУММУ (2-12):", reply_markup=InlineKeyboardMarkup(keyboard))

async def demo_play_dice_sum(update: Update, context: ContextTypes.DEFAULT_TYPE, guess):
    query = update.callback_query
    uid = str(query.from_user.id)
    d1, d2 = random.randint(1,6), random.randint(1,6)
    total = d1 + d2
    msg = "🎉 ПОБЕДА!" if guess == total else "😢 ПРОИГРЫШ!"
    await query.message.edit_text(f"🎲 ДЕМО КОСТИ\n\n{d1} + {d2} = {total}\n{msg}\n\n💎 ДЕМО-РЕЖИМ: БАЛАНС НЕ ИЗМЕНЯЕТСЯ", reply_markup=demo_menu(uid))

async def demo_dice_over(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    keyboard = [[InlineKeyboardButton("📈 БОЛЬШЕ 7", callback_data="demo_dice_over_more"), InlineKeyboardButton("📉 МЕНЬШЕ 7", callback_data="demo_dice_over_less")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="demo_mode")]]
    await query.message.edit_text("🎲 ДЕМО КОСТИ (БОЛЬШЕ/МЕНЬШЕ 7)\n\nВЫБЕРИТЕ:", reply_markup=InlineKeyboardMarkup(keyboard))

async def demo_play_dice_over(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    d1, d2 = random.randint(1,6), random.randint(1,6)
    total = d1 + d2
    if (choice == "more" and total > 7) or (choice == "less" and total < 7):
        msg = "🎉 ПОБЕДА!"
    elif total == 7:
        msg = "😐 НИЧЬЯ!"
    else:
        msg = "😢 ПРОИГРЫШ!"
    await query.message.edit_text(f"🎲 ДЕМО КОСТИ\n\n{d1} + {d2} = {total}\n{msg}\n\n💎 ДЕМО-РЕЖИМ: БАЛАНС НЕ ИЗМЕНЯЕТСЯ", reply_markup=demo_menu(uid))

async def demo_dice_even(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    keyboard = [[InlineKeyboardButton("✅ ЧЁТ", callback_data="demo_dice_even_even"), InlineKeyboardButton("❌ НЕЧЕТ", callback_data="demo_dice_even_odd")], [InlineKeyboardButton(get_text(uid, 'back'), callback_data="demo_mode")]]
    await query.message.edit_text("🎲 ДЕМО КОСТИ (ЧЁТ/НЕЧЕТ)\n\nВЫБЕРИТЕ:", reply_markup=InlineKeyboardMarkup(keyboard))

async def demo_play_dice_even(update: Update, context: ContextTypes.DEFAULT_TYPE, choice):
    query = update.callback_query
    uid = str(query.from_user.id)
    d1, d2 = random.randint(1,6), random.randint(1,6)
    total = d1 + d2
    is_even = total % 2 == 0
    if (choice == "even" and is_even) or (choice == "odd" and not is_even):
        msg = "🎉 ПОБЕДА!"
    else:
        msg = "😢 ПРОИГРЫШ!"
    await query.message.edit_text(f"🎲 ДЕМО КОСТИ\n\n{d1} + {d2} = {total}\n{msg}\n\n💎 ДЕМО-РЕЖИМ: БАЛАНС НЕ ИЗМЕНЯЕТСЯ", reply_markup=demo_menu(uid))

# ========== CALLBACK ==========
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "change_lang":
        await lang_choice(update, context)
    elif data.startswith("lang_"):
        await set_language(update, context)
    elif data.startswith("bet_"):
        await handle_bet_selection(update, context)
    elif data == "back":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'games'), reply_markup=games_menu(uid))
    elif data == "games_menu":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'games'), reply_markup=games_menu(uid))
    elif data == "demo_mode":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'demo'), reply_markup=demo_menu(uid))
    elif data == "balance":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'balance', round_ton(users[uid]['balance'])), reply_markup=main_menu(uid))
    elif data == "stats":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'stats', users[uid]['spins'], round_ton(users[uid]['total_bet']), round_ton(users[uid]['total_win']), users[uid].get('best_streak', 0)), reply_markup=main_menu(uid))
    elif data == "top":
        await top_leaderboard(update, context)
    elif data == "my_stats":
        await my_game_stats(update, context)
    elif data == "achievements":
        await achievements_menu(update, context)
    elif data == "channel":
        await channel(update, context)
    elif data == "deposit_menu":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'deposit'), reply_markup=deposit_menu(uid))
    elif data == "deposit_simple":
        uid = str(query.from_user.id)
        await query.message.edit_text(
            "💎 **ПОПОЛНЕНИЕ ЧЕРЕЗ ПЕРЕВОД** 💎\n\n"
            "Команда: `/deposit [СУММА]`\n"
            "Пример: `/deposit 10`",
            reply_markup=main_menu(uid),
            parse_mode="Markdown"
        )
    elif data == "deposit_connect":
        uid = str(query.from_user.id)
        await query.message.edit_text(
            "🔗 **TON CONNECT** 🔗\n\n"
            "/connect - подключить кошелёк\n"
            "/pay [СУММА] - оплатить",
            reply_markup=main_menu(uid),
            parse_mode="Markdown"
        )
    elif data == "wallet_menu":
        uid = str(query.from_user.id)
        await query.message.edit_text("🔗 КОШЕЛЁК", reply_markup=wallet_menu(uid))
    elif data == "connect_wallet":
        await connect_wallet(update, context)
    elif data == "pay_menu":
        uid = str(query.from_user.id)
        await query.message.edit_text(
            "💰 **ОПЛАТА ИЗ КОШЕЛЬКА** 💰\n\n"
            "/pay [СУММА]\n\nПример: `/pay 10`",
            reply_markup=main_menu(uid),
            parse_mode="Markdown"
        )
    elif data == "withdraw_menu":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'withdraw'), reply_markup=main_menu(uid))
    elif data == "support":
        uid = str(query.from_user.id)
        await query.message.edit_text(get_text(uid, 'support', SUPPORT), reply_markup=main_menu(uid))
    elif data == "referral":
        uid = str(query.from_user.id)
        bot = (await context.bot.get_me()).username
        await query.message.edit_text(get_text(uid, 'referral', len(users[uid].get('referrals', [])), round_ton(users[uid].get('total_ref_earnings', 0)), bot, uid), reply_markup=main_menu(uid))
    elif data == "game_coin":
        await game_coin(update, context)
    elif data == "game_number":
        await game_number(update, context)
    elif data == "game_dice_sum":
        await game_dice_sum(update, context)
    elif data == "game_dice_over":
        await game_dice_over(update, context)
    elif data == "game_dice_even":
        await game_dice_even(update, context)
    elif data == "game_slot":
        await game_slot(update, context)
    elif data == "game_roulette":
        await game_roulette(update, context)
    elif data == "game_rps":
        await game_rps(update, context)
    elif data == "roulette_red":
        uid = str(query.from_user.id)
        context.user_data['current_game'] = 'roulette_color'
        context.user_data['roulette_choice'] = 'red'
        await query.message.edit_text(get_text(uid, 'roulette'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))
    elif data == "roulette_black":
        uid = str(query.from_user.id)
        context.user_data['current_game'] = 'roulette_color'
        context.user_data['roulette_choice'] = 'black'
        await query.message.edit_text(get_text(uid, 'roulette'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))
    elif data == "roulette_number":
        uid = str(query.from_user.id)
        context.user_data['current_game'] = 'roulette_number'
        await query.message.edit_text(get_text(uid, 'roulette'), reply_markup=InlineKeyboardMarkup(get_bet_buttons(uid)))
    elif data.startswith("coin_"):
        choice = "орел" if "heads" in data else "решка"
        await play_coin(update, context, choice)
    elif data.startswith("num_"):
        guess = int(data.split("_")[1])
        await play_number(update, context, guess)
    elif data.startswith("dice_sum_"):
        guess = int(data.split("_")[2])
        await play_dice_sum(update, context, guess)
    elif data.startswith("dice_over_"):
        choice = "more" if "more" in data else "less"
        await play_dice_over(update, context, choice)
    elif data.startswith("dice_even_"):
        choice = "even" if "even" in data else "odd"
        await play_dice_even(update, context, choice)
    elif data.startswith("rps_"):
        player = data.split("_")[1]
        await play_rps(update, context, player)
    elif data.startswith("roulette_color_"):
        choice = data.split("_")[2]
        await play_roulette_color(update, context, choice)
    elif data.startswith("roulette_number_"):
        guess = int(data.split("_")[2])
        await play_roulette_number(update, context, guess)
    elif data.startswith("demo_"):
        if data == "demo_coin":
            await demo_coin(update, context)
        elif data == "demo_number":
            await demo_number(update, context)
        elif data == "demo_dice_sum":
            await demo_dice_sum(update, context)
        elif data == "demo_dice_over":
            await demo_dice_over(update, context)
        elif data == "demo_dice_even":
            await demo_dice_even(update, context)
        elif data.startswith("demo_coin_"):
            choice = "орел" if "heads" in data else "решка"
            await demo_play_coin(update, context, choice)
        elif data.startswith("demo_num_"):
            guess = int(data.split("_")[2])
            await demo_play_number(update, context, guess)
        elif data.startswith("demo_dice_sum_"):
            guess = int(data.split("_")[3])
            await demo_play_dice_sum(update, context, guess)
        elif data.startswith("demo_dice_over_"):
            choice = "more" if "more" in data else "less"
            await demo_play_dice_over(update, context, choice)
        elif data.startswith("demo_dice_even_"):
            choice = "even" if "even" in data else "odd"
            await demo_play_dice_even(update, context, choice)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}")

# ========== ЗАПУСК ==========
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("deposit", deposit_simple))
    app.add_handler(CommandHandler("check_deposit", check_deposit))
    app.add_handler(CommandHandler("connect", connect_wallet))
    app.add_handler(CommandHandler("pay", pay_from_wallet))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("ref", referral))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("top", top_leaderboard))
    app.add_handler(CommandHandler("mystats", my_game_stats))
    app.add_handler(CommandHandler("achievements", achievements_menu))
    app.add_handler(CommandHandler("channel", channel))
    
    app.add_handler(CommandHandler("add_deposit", add_deposit))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("decline", decline))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_bet))
    app.add_error_handler(error_handler)
    
    logger.info(f"✅ {CASINO_NAME} ЗАПУЩЕН!")
    
    asyncio.create_task(check_reminders(app))
    
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())