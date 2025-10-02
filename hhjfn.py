import asyncio
import sqlite3
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot import asyncio_helper
import time

# Инициализация бота
bot = AsyncTeleBot('YOUR_BOT_TOKEN_HERE')

# База данных для хранения данных пользователей
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('clicker.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                score INTEGER DEFAULT 0,
                last_click INTEGER DEFAULT 0,
                click_power INTEGER DEFAULT 1,
                passive_income INTEGER DEFAULT 0,
                last_passive_claim INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            return {
                'user_id': user[0],
                'username': user[1],
                'score': user[2],
                'last_click': user[3],
                'click_power': user[4],
                'passive_income': user[5],
                'last_passive_claim': user[6]
            }
        return None
    
    def create_user(self, user_id, username):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, score, last_click, click_power, passive_income, last_passive_claim)
            VALUES (?, ?, 0, 0, 1, 0, ?)
        ''', (user_id, username, int(time.time())))
        self.conn.commit()
    
    def update_score(self, user_id, score):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET score = ?, last_click = ? WHERE user_id = ?', 
                      (score, int(time.time()), user_id))
        self.conn.commit()
    
    def upgrade_click_power(self, user_id, new_power, cost):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET click_power = ?, score = score - ? WHERE user_id = ?', 
                      (new_power, cost, user_id))
        self.conn.commit()
    
    def upgrade_passive_income(self, user_id, new_income, cost):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET passive_income = ?, score = score - ?, last_passive_claim = ? WHERE user_id = ?', 
                      (new_income, cost, int(time.time()), user_id))
        self.conn.commit()
    
    def claim_passive_income(self, user_id, new_score, current_time):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET score = ?, last_passive_claim = ? WHERE user_id = ?', 
                      (new_score, current_time, user_id))
        self.conn.commit()

db = Database()

# Главное меню
def create_main_keyboard():
    return {
        'keyboard': [
            ['🎯 Кликнуть', '📊 Статистика'],
            ['⚡ Улучшения', '💎 Пассивный доход'],
            ['🔄 Обновить']
        ],
        'resize_keyboard': True
    }

# Клавиатура улучшений
def create_upgrades_keyboard(user):
    return {
        'keyboard': [
            [f'⚡ Улучшить клик (+1) - {calculate_click_upgrade_cost(user["click_power"])} очков'],
            [f'💎 Пассивный доход (+1/сек) - {calculate_passive_upgrade_cost(user["passive_income"])} очков'],
            ['🔙 Назад']
        ],
        'resize_keyboard': True
    }

# Расчет стоимости улучшений
def calculate_click_upgrade_cost(current_power):
    return current_power * 100

def calculate_passive_upgrade_cost(current_income):
    return (current_income + 1) * 100

# Обработчик команды /start
@bot.message_handler(commands=['start'])
async def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    db.create_user(user_id, username)
    
    welcome_text = (
        "🎮 Добро пожаловать в кликер-бот!\n\n"
        "🎯 Нажимайте кнопку 'Кликнуть' для получения очков\n"
        "⚡ Улучшайте силу клика для большего дохода\n"
        "💎 Покупайте пассивный доход\n\n"
        "Начните кликать прямо сейчас!"
    )
    
    await bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=create_main_keyboard()
    )

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
async def handle_messages(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        db.create_user(user_id, message.from_user.username or message.from_user.first_name)
        user = db.get_user(user_id)
    
    # Обработка клика
    if message.text == '🎯 Кликнуть':
        new_score = user['score'] + user['click_power']
        db.update_score(user_id, new_score)
        
        await bot.send_message(
            message.chat.id,
            f"🎯 +{user['click_power']} очков!\n"
            f"💰 Всего очков: {new_score}",
            reply_markup=create_main_keyboard()
        )
    
    # Статистика
    elif message.text == '📊 Статистика':
        await show_statistics(message, user)
    
    # Улучшения
    elif message.text == '⚡ Улучшения':
        await show_upgrades(message, user)
    
    # Пассивный доход
    elif message.text == '💎 Пассивный доход':
        await show_passive_income(message, user)
    
    # Обновить
    elif message.text == '🔄 Обновить':
        await update_passive_income(message, user)
    
    # Назад из улучшений
    elif message.text == '🔙 Назад':
        await bot.send_message(
            message.chat.id,
            "Главное меню:",
            reply_markup=create_main_keyboard()
        )
    
    # Улучшение клика
    elif message.text.startswith('⚡ Улучшить клик'):
        await upgrade_click_power(message, user)
    
    # Улучшение пассивного дохода
    elif message.text.startswith('💎 Пассивный доход'):
        await upgrade_passive_income_handler(message, user)

# Показать статистику
async def show_statistics(message, user):
    stats_text = (
        f"📊 Ваша статистика:\n\n"
        f"💰 Очков: {user['score']}\n"
        f"⚡ Сила клика: {user['click_power']}\n"
        f"💎 Пассивный доход: {user['passive_income']} очков/сек\n"
        f"🕒 Следующее улучшение клика: {calculate_click_upgrade_cost(user['click_power'])} очков\n"
        f"🕒 Следующее улучшение пассивного дохода: {calculate_passive_upgrade_cost(user['passive_income'])} очков"
    )
    
    await bot.send_message(
        message.chat.id,
        stats_text,
        reply_markup=create_main_keyboard()
    )

# Показать улучшения
async def show_upgrades(message, user):
    upgrades_text = (
        f"⚡ Улучшения:\n\n"
        f"💰 Ваши очки: {user['score']}\n\n"
        f"Выберите улучшение:"
    )
    
    await bot.send_message(
        message.chat.id,
        upgrades_text,
        reply_markup=create_upgrades_keyboard(user)
    )

# Показать пассивный доход
async def show_passive_income(message, user):
    current_time = int(time.time())
    time_diff = current_time - user['last_passive_claim']
    passive_earned = time_diff * user['passive_income']
    
    passive_text = (
        f"💎 Пассивный доход:\n\n"
        f"📈 Текущий доход: {user['passive_income']} очков/сек\n"
        f"⏰ Накоплено за время: {passive_earned} очков\n"
        f"🕒 Прошло времени: {time_diff} секунд\n\n"
        f"Нажмите '🔄 Обновить' для получения накопленных очков!"
    )
    
    await bot.send_message(
        message.chat.id,
        passive_text,
        reply_markup=create_main_keyboard()
    )

# Обновить пассивный доход
async def update_passive_income(message, user):
    current_time = int(time.time())
    time_diff = current_time - user['last_passive_claim']
    passive_earned = time_diff * user['passive_income']
    
    if passive_earned > 0:
        new_score = user['score'] + passive_earned
        db.claim_passive_income(user_id=user['user_id'], new_score=new_score, current_time=current_time)
        
        await bot.send_message(
            message.chat.id,
            f"💎 Получено пассивного дохода: +{passive_earned} очков!\n"
            f"💰 Всего очков: {new_score}",
            reply_markup=create_main_keyboard()
        )
    else:
        await bot.send_message(
            message.chat.id,
            "⏰ Пассивный доход еще не накоплен\n"
            "Проверьте позже!",
            reply_markup=create_main_keyboard()
        )

# Улучшить силу клика
async def upgrade_click_power(message, user):
    cost = calculate_click_upgrade_cost(user['click_power'])
    
    if user['score'] >= cost:
        new_power = user['click_power'] + 1
        db.upgrade_click_power(user['user_id'], new_power, cost)
        
        await bot.send_message(
            message.chat.id,
            f"⚡ Улучшение приобретено!\n"
            f"💵 Потрачено: {cost} очков\n"
            f"🎯 Новая сила клика: {new_power}\n"
            f"💰 Осталось очков: {user['score'] - cost}",
            reply_markup=create_upgrades_keyboard(db.get_user(user['user_id']))
        )
    else:
        await bot.send_message(
            message.chat.id,
            f"❌ Недостаточно очков!\n"
            f"💰 Нужно: {cost} очков\n"
            f"💵 У вас: {user['score']} очков",
            reply_markup=create_upgrades_keyboard(user)
        )

# Улучшить пассивный доход
async def upgrade_passive_income_handler(message, user):
    cost = calculate_passive_upgrade_cost(user['passive_income'])
    
    if user['score'] >= cost:
        new_income = user['passive_income'] + 1
        db.upgrade_passive_income(user['user_id'], new_income, cost)
        
        await bot.send_message(
            message.chat.id,
            f"💎 Улучшение пассивного дохода приобретено!\n"
            f"💵 Потрачено: {cost} очков\n"
            f"📈 Новый доход: {new_income} очков/сек\n"
            f"💰 Осталось очков: {user['score'] - cost}",
            reply_markup=create_upgrades_keyboard(db.get_user(user['user_id']))
        )
    else:
        await bot.send_message(
            message.chat.id,
            f"❌ Недостаточно очков!\n"
            f"💰 Нужно: {cost} очков\n"
            f"💵 У вас: {user['score']} очков",
            reply_markup=create_upgrades_keyboard(user)
        )

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    asyncio.run(bot.polling())
