import asyncio
import json
import os
import random
import string
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import CommandStart


# ====== CONFIG ======
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 1056116070  # ТВОЙ Telegram ID (числом)

if not TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не задана в Railway (Variables).")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ====== STORAGE FILES ======
USERS_FILE = "users.json"
PROMOCODES_FILE = "promocodes.json"
ADMINS_FILE = "admins.json"


def load_data(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


users = load_data(USERS_FILE, {})                 # { "user_id": {"balance": int, "last_luck": str|None} }
promocodes = load_data(PROMOCODES_FILE, {})       # { "CODE": {"value":int,"uses":int,"max_uses":int,"created_by":int} }
admins = load_data(ADMINS_FILE, [OWNER_ID])       # [int, int, ...]
admin_states = {}                                 # { admin_id(int): "state" }


def is_admin(user_id: int) -> bool:
    return user_id in admins


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def generate_promo_code(length=6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Мини-игра", callback_data="game")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="🎁 Удача", callback_data="luck")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="rules")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promo")],
    ])
    if is_admin(user_id):
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin")]
        )
    return keyboard


def ensure_user(user_id_str: str):
    if user_id_str not in users:
        users[user_id_str] = {"balance": 0, "last_luck": None}
        save_data(USERS_FILE, users)


# ====== START ======
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    user_id_str = str(user_id)

    ensure_user(user_id_str)

    await message.answer(
        "🏹 Добро пожаловать на турнир WG!\n\n"
        f"💰 Твой баланс: {users[user_id_str]['balance']} монет\n\n"
        "Ивент уже запущен.\n"
        "Готов испытать удачу?",
        reply_markup=main_menu_kb(user_id)
    )


# ====== LUCK FLOW ======
@dp.callback_query(lambda c: c.data == "luck")
async def process_luck(callback: CallbackQuery):
    luck_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎲 Удача")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await callback.message.answer(
        "👇 Нажми на большую кнопку, чтобы испытать удачу!\n"
        "Доступно **1 раз в 24 часа**",
        reply_markup=luck_keyboard
    )
    await callback.answer()


@dp.message(lambda message: message.text == "🎲 Удача")
async def give_luck(message: Message):
    user_id_str = str(message.from_user.id)
    ensure_user(user_id_str)

    now = datetime.now()

    last = users[user_id_str].get("last_luck")
    if last:
        last_used = datetime.fromisoformat(last)
        time_diff = now - last_used
        if time_diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - time_diff
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await message.answer(f"⏳ Подожди ещё {hours} ч {minutes} мин до следующей попытки!")
            return

    coins = random.randint(0, 1000)
    users[user_id_str]["balance"] += coins
    users[user_id_str]["last_luck"] = now.isoformat()
    save_data(USERS_FILE, users)

    await message.answer(
        f"🎲 Тебе выпало: {coins} монет!\n"
        f"💰 Текущий баланс: {users[user_id_str]['balance']}"
    )


# ====== PROMO FLOW ======
@dp.callback_query(lambda c: c.data == "promo")
async def promo_button(callback: CallbackQuery):
    await callback.message.answer(
        "🎟 Введи промокод в чат:\n"
        "Например: ABC123"
    )
    await callback.answer()


async def handle_promo_logic(message: Message):
    # игнорируем команды
    if not message.text or message.text.startswith("/"):
        return

    code = message.text.strip().upper()
    user_id_str = str(message.from_user.id)
    ensure_user(user_id_str)

    if code not in promocodes:
        return  # просто не отвечаем, если это не промокод

    promo = promocodes[code]

    if promo["uses"] >= promo["max_uses"]:
        await message.answer("❌ Этот промокод уже использован максимальное количество раз!")
        return

    users[user_id_str]["balance"] += promo["value"]
    promo["uses"] += 1

    save_data(USERS_FILE, users)
    save_data(PROMOCODES_FILE, promocodes)

    await message.answer(
        f"✅ Промокод активирован!\n"
        f"💰 Ты получил {promo['value']} монет\n"
        f"💳 Текущий баланс: {users[user_id_str]['balance']}"
    )

    # уведомление создателю промо
    try:
        await bot.send_message(
            int(promo["created_by"]),
            f"🎟 Промокод {code} активирован!\n"
            f"Пользователь: {message.from_user.full_name} (ID: {user_id_str})\n"
            f"Осталось использований: {promo['max_uses'] - promo['uses']}"
        )
    except:
        pass


# ====== ADMIN PANEL ======
@dp.callback_query(lambda c: c.data == "admin")
async def admin_panel(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("❌ У тебя нет прав администратора!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="💰 Начислить монеты", callback_data="admin_give")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
    ])

    if is_owner(user_id):
        keyboard.inline_keyboard.insert(0, [
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add"),
            InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_remove")
        ])

    await callback.message.edit_text("⚙️ Админ-панель\n\nВыбери действие:", reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_id_str = str(user_id)
    ensure_user(user_id_str)

    await callback.message.edit_text(
        "🏹 Добро пожаловать на турнир WG!\n\n"
        f"💰 Твой баланс: {users[user_id_str]['balance']} монет\n\n"
        "Ивент уже запущен.\n"
        "Готов испытать удачу?",
        reply_markup=main_menu_kb(user_id)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_add")
async def add_admin_start(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Только владелец!", show_alert=True)
        return

    admin_states[callback.from_user.id] = "adding_admin"
    await callback.message.answer(
        "➕ Добавление администратора\n\n"
        "Введи ID пользователя (только цифры):\n"
        "Пример: `123456789`",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_remove")
async def remove_admin_start(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("❌ Только владелец!", show_alert=True)
        return

    admin_states[callback.from_user.id] = "removing_admin"
    await callback.message.answer(
        "➖ Удаление администратора\n\n"
        "Введи ID пользователя (только цифры):\n"
        "Пример: `123456789`",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_create_promo")
async def create_promo_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав!", show_alert=True)
        return

    admin_states[callback.from_user.id] = "creating_promo"
    await callback.message.answer(
        "🎟 Создание промокода\n\n"
        "Введи данные в формате:\n"
        "`сумма лимит`\n\n"
        "Пример: `500 3` — промокод на 500 монет, 3 использования\n\n"
        "Или:\n"
        "`сумма лимит КОД` — если хочешь свой код\n"
        "Пример: `1000 1 WIN2025`",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_give")
async def give_money_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав!", show_alert=True)
        return

    admin_states[callback.from_user.id] = "giving_money"
    await callback.message.answer(
        "💰 Начисление монет\n\n"
        "Введи данные в формате:\n"
        "`user_id сумма`\n\n"
        "Пример: `123456789 500`",
        parse_mode="Markdown"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "admin_list_promos")
async def list_promos(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав!", show_alert=True)
        return

    if not promocodes:
        await callback.message.answer("📭 Нет активных промокодов")
        await callback.answer()
        return

    text = "📋 Список промокодов:\n\n"
    for code, data in promocodes.items():
        text += f"• {code}: {data['value']} монет, использовано {data['uses']}/{data['max_uses']}\n"

    await callback.message.answer(text)
    await callback.answer()


# ====== GAME / SHOP / RULES ======
@dp.callback_query(lambda c: c.data == "game")
async def game(callback: CallbackQuery):
    await callback.message.answer("🎮 Мини-игра пока в разработке!")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "shop")
async def shop(callback: CallbackQuery):
    await callback.message.answer("🛒 Магазин пока в разработке!")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "rules")
async def rules(callback: CallbackQuery):
    await callback.message.answer(
        "📜 Правила ивента:\n\n"
        "1. Каждый день можно получить удачу (0–1000 монет)\n"
        "2. Промокоды дают дополнительные монеты\n"
        "3. В магазине можно купить разные бонусы\n"
        "4. Следи за обновлениями!"
    )
    await callback.answer()


# ====== SINGLE ADMIN/PROMO MESSAGE HANDLER ======
@dp.message()
async def handle_text_messages(message: Message):
    user_id = message.from_user.id

    # если админ в режиме ввода
    if user_id in admin_states:
        state = admin_states[user_id]
        text = (message.text or "").strip()

        # добавление админа
        if state == "adding_admin" and is_owner(user_id):
            try:
                new_admin_id = int(text)
                if new_admin_id not in admins:
                    admins.append(new_admin_id)
                    save_data(ADMINS_FILE, admins)
                    await message.answer(f"✅ Пользователь {new_admin_id} добавлен в администраторы")
                else:
                    await message.answer("⚠️ Этот пользователь уже администратор")
            except ValueError:
                await message.answer("❌ Ошибка! Введи только цифры ID")

            admin_states.pop(user_id, None)
            return

        # удаление админа
        if state == "removing_admin" and is_owner(user_id):
            try:
                admin_id = int(text)
                if admin_id == OWNER_ID:
                    await message.answer("❌ Нельзя удалить владельца!")
                elif admin_id in admins:
                    admins.remove(admin_id)
                    save_data(ADMINS_FILE, admins)
                    await message.answer(f"✅ Администратор {admin_id} удалён")
                else:
                    await message.answer("⚠️ Этот пользователь не является администратором")
            except ValueError:
                await message.answer("❌ Ошибка! Введи только цифры ID")

            admin_states.pop(user_id, None)
            return

        # создание промокода
        if state == "creating_promo" and is_admin(user_id):
            parts = text.split()
            try:
                if len(parts) == 2:
                    value = int(parts[0])
                    max_uses = int(parts[1])
                    code = generate_promo_code()
                elif len(parts) == 3:
                    value = int(parts[0])
                    max_uses = int(parts[1])
                    code = parts[2].upper()
                else:
                    await message.answer("❌ Неправильный формат! Используй: сумма лимит или сумма лимит КОД")
                    admin_states.pop(user_id, None)
                    return

                if code in promocodes:
                    await message.answer(f"❌ Промокод {code} уже существует!")
                    admin_states.pop(user_id, None)
                    return

                promocodes[code] = {
                    "value": value,
                    "uses": 0,
                    "max_uses": max_uses,
                    "created_by": user_id
                }
                save_data(PROMOCODES_FILE, promocodes)

                await message.answer(
                    "✅ Промокод создан!\n\n"
                    f"📌 Код: `{code}`\n"
                    f"💰 Сумма: {value} монет\n"
                    f"👥 Лимит: {max_uses} использований\n\n"
                    "Отправь этот код игрокам!",
                    parse_mode="Markdown"
                )
            except ValueError:
                await message.answer("❌ Ошибка! Введи число и лимит правильно")

            admin_states.pop(user_id, None)
            return

        # начисление монет
        if state == "giving_money" and is_admin(user_id):
            parts = text.split()
            try:
                if len(parts) != 2:
                    await message.answer("❌ Используй формат: user_id сумма")
                    admin_states.pop(user_id, None)
                    return

                target_id = str(int(parts[0]))  # нормализуем
                amount = int(parts[1])

                ensure_user(target_id)
                users[target_id]["balance"] += amount
                save_data(USERS_FILE, users)

                await message.answer(f"✅ Начислено {amount} монет пользователю {target_id}")

                try:
                    await bot.send_message(
                        int(target_id),
                        f"💰 Тебе начислено {amount} монет!\n"
                        f"Текущий баланс: {users[target_id]['balance']}"
                    )
                except:
                    await message.answer("⚠️ Не удалось уведомить пользователя")
            except ValueError:
                await message.answer("❌ Ошибка! Введи ID и сумму правильно")

            admin_states.pop(user_id, None)
            return

        # если состояние какое-то неизвестное
        admin_states.pop(user_id, None)
        return

    # иначе — проверяем промокоды
    await handle_promo_logic(message)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
