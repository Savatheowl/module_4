import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = "8268073901:AAEdaQLHQfFqZbQA4Cs-fH4vYWFXXWHsBdo"

API_BASE = "http://127.0.0.1:1234"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_sessions = {}


async def api_get(endpoint: str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}{endpoint}") as resp:
            if resp.status == 404:
                return None
            return await resp.json()


async def api_post(endpoint: str, data: dict):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_BASE}{endpoint}", json=data) as resp:
            return await resp.json()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать! Я бот для изучения материалов.\n\n"
        "Доступные команды:\n"
        "/materials - показать доступные материалы\n"
        "/trajectory - построить траекторию обучения\n"
        "/time <id> - оценить время изучения материала\n"
        "/level <id> - определить сложность материала\n"
        "/sequential - проверить последовательность изучения"
    )


@dp.message(Command("materials"))
async def cmd_materials(message: types.Message):
    mats = await api_get("/materials")
    if not mats:
        await message.answer("Материалы не найдены.")
        return
    
    result = "Доступные материалы:\n\n"
    for m in mats[:10]:
        result += f"ID: {m['id']} | {m['subject']} | {m['topic']}\n"
        if m.get("complexity_level"):
            result += f"   Сложность: {m['complexity_level']}\n"
        if m.get("estimated_time_hours"):
            result += f"   Время: {m['estimated_time_hours']} ч.\n"
        result += "\n"
    
    await message.answer(result)


@dp.message(Command("trajectory"))
async def cmd_trajectory(message: types.Message):
    await message.answer(
        "Построение траектории обучения.\n"
        "Укажите предмет (дисциплину):"
    )
    user_sessions[message.from_user.id] = {"state": "waiting_subject"}


@dp.message(Command("time"))
async def cmd_time(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Укажите ID материала: /time <id>")
        return
    
    try:
        material_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный ID.")
        return
    
    result = await api_get(f"/time/{material_id}")
    if result is None:
        await message.answer("Материал не найден.")
        return
    
    await message.answer(
        f"Оценка времени для материала ID {material_id}:\n"
        f"Примерное время: {result['estimated_hours']} ч.\n"
        f"Уверенность: {result['confidence']:.1%}"
    )


@dp.message(Command("level"))
async def cmd_level(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Укажите ID материала: /level <id>")
        return
    
    try:
        material_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный ID.")
        return
    
    m = await api_get(f"/materials/{material_id}")
    if m is None:
        await message.answer("Материал не найден.")
        return
    
    level = m.get("complexity_level", "не определено")
    await message.answer(
        f"Уровень сложности материала ID {material_id}: {level}"
    )


@dp.message(Command("sequential"))
async def cmd_sequential(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Укажите ID кластера: /sequential <cluster_id>")
        return
    
    try:
        cluster_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный ID кластера.")
        return
    
    mats = await api_get(f"/clusters/sequential?cluster_id={cluster_id}")
    if not mats:
        await message.answer("Материалы не найдены.")
        return
    
    result = f"Последовательность изучения (кластер {cluster_id}):\n\n"
    for m in mats:
        result += f"{m['id']}. {m['topic']}\n"
    
    await message.answer(result)


@dp.message()
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions:
        await message.answer("Используйте команды, например /trajectory")
        return
    
    session = user_sessions[user_id]
    state = session.get("state")
    
    if state == "waiting_subject":
        session["subject"] = message.text
        session["state"] = "waiting_goal"
        await message.answer(
            f"Предмет: {message.text}\n"
            "Теперь укажите цель обучения (или пропустите):"
        )
    elif state == "waiting_goal":
        session["goal"] = message.text if message.text.strip() else ""
        session["state"] = "waiting_hours"
        await message.answer(
            "Теперь укажите доступное время (часы в неделю):"
        )
    elif state == "waiting_hours":
        try:
            hours = float(message.text) if message.text.strip() else 0.0
        except ValueError:
            await message.answer("Введите число.")
            return
        
        session["available_hours"] = hours
        session["state"] = "waiting_complexity"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Легкий", callback_data="complexity_easy")],
            [InlineKeyboardButton(text="Средний", callback_data="complexity_medium")],
            [InlineKeyboardButton(text="Сложный", callback_data="complexity_hard")],
        ])
        await message.answer("Выберите предпочитаемую сложность:", reply_markup=keyboard)
    else:
        await message.answer("Начните заново с /trajectory")
        user_sessions.pop(user_id, None)


@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_sessions:
        await callback.answer()
        return
    
    session = user_sessions[user_id]
    data = callback.data
    
    if data.startswith("complexity_"):
        session["preferred_complexity"] = data.split("_")[1]
        
        await callback.answer()
        await callback.message.answer("Строю траекторию...")
        
        try:
            result = await api_post("/trajectory", {
                "subject": session.get("subject", ""),
                "goal": session.get("goal", ""),
                "available_hours": session.get("available_hours", 0.0),
                "preferred_complexity": session.get("preferred_complexity", "medium"),
            })
            
            desc = "Построена траектория обучения:\n\n"
            if result.get("materials"):
                for m in result["materials"]:
                    desc += f"- {m['topic']} ({m.get('complexity_level', '?')})\n"
                desc += f"\nОбщее время: {result.get('total_hours', 0):.1f} ч."
            else:
                desc = "Материалы не найдены."
            
            await callback.message.answer(desc)
        except Exception as e:
            await callback.message.answer(f"Ошибка: {e}")
        
        user_sessions.pop(user_id, None)


async def on_shutdown():
    await bot.close()


async def start_bot():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_bot())