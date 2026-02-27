import asyncio
import json
import os
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.filters import CommandStart


# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 1056116870  # <-- твой Telegram ID

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в переменных окружения Railway")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ================= FILES =================

USERS_FILE = "users.json"


def load_data(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


users = load_data(USERS_FILE, {})


# ================= KEYBOARDS =================

def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Играть")],
            [KeyboardButton(text="💰 Баланс")],
        ],
        resize_keyboard=True
    )
    return keyboard


def game_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="1"),
                InlineKeyboardButton(text="2", callback_data="2"),
                InlineKeyboardButton(text="3", callback_data="3"),
            ]
        ]
    )


# ================= START =================

@dp.message(CommandStart())
async def start(message: Message):
    user_id = str(message.from_user.id)

    if user_id not in users:
        users[user_id] = {
            "balance": 100,
            "last_bonus": None
        }
        save_data(USERS_FILE, users)

    await message.answer(
        "Добро пожаловать в мини-игру 🎮",
        reply_markup=main_menu()
    )


# ================= BALANCE =================

@dp.message(lambda message: message.text == "💰 Баланс")
async def balance(message: Message):
    user_id = str(message.from_user.id)
    bal = users.get(user_id, {}).get("balance", 0)
    await message.answer(f"💰 Ваш баланс: {bal} монет")


# ================= GAME =================

@dp.message(lambda message: message.text == "🎮 Играть")
async def play(message: Message):
    await message.answer("Выбери число от 1 до 3:", reply_markup=game_keyboard())


@dp.callback_query(lambda c: c.data in ["1", "2", "3"])
async def process_game(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    choice = int(callback.data)
    win_number = random.randint(1, 3)

    if choice == win_number:
        users[user_id]["balance"] += 50
        result = "🎉 Ты выиграл 50 монет!"
    else:
        users[user_id]["balance"] -= 10
        result = f"❌ Ты проиграл. Было число {win_number}"

    save_data(USERS_FILE, users)

    await callback.message.edit_text(result)
    await callback.answer()


# ================= RUN =================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
