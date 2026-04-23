import asyncio
import uvicorn
from agents.module_4.agent_tg.tg import bot, dp, on_shutdown
from agents.module_4.agent_api.app import app

async def main():
    # Настройка uvicorn-сервера
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=1234,
        loop="asyncio",
        log_level="info"
    )
    server = uvicorn.Server(config)

    bot_task = asyncio.create_task(dp.start_polling(bot))
    server_task = asyncio.create_task(server.serve())

    try:
        await asyncio.gather(bot_task, server_task)
    except asyncio.CancelledError:
        await on_shutdown()
        await server.shutdown()

if __name__ == "__main__":
    asyncio.run(main())