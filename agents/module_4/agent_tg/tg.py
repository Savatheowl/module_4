import asyncio                          # для asyncio.run()
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command     # фильтр для команд типа /start


# Токен вашего бота (лучше хранить в переменной окружения)
BOT_TOKEN = "8268073901:AAEdaQLHQfFqZbQA4Cs-fH4vYWFXXWHsBdo"   # замените на реальный

# Создаём объект бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # message — объект сообщения, из него берём метод answer
    await message.answer("Привет! Я простой бот. Напиши мне что-нибудь.")

# Обработчик любого текстового сообщения (не команды)
@dp.message()
async def echo(message: types.Message):
    # Отправляем обратно текст пользователя
    await message.answer(f"Вы сказали: {message.text}")
    
async def on_shutdown():
    await bot.close()

# Точка входа
async def start_bot():
    # Запускаем длительный опрос серверов Telegram (long polling)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(start_bot())