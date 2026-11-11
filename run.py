import asyncio
import logging
import os
import sys
from aiohttp import web
from bot import bot, dp
import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)

# Render.com sog'liqni tekshiruvchi (Health-check) server
async def handle_ping(request):
    return web.Response(text="Iskndrv Games Unified Bot is running 24/7!", status=200)

async def keep_awake_pinger():
    """Render bepul serverini uxlab qolishini oldini olish uchun har 8 daqiqada o'zini ping qiladi"""
    await asyncio.sleep(60)
    app_url = os.environ.get("RENDER_EXTERNAL_URL", "https://iskndrv-games-bots.onrender.com")
    health_url = f"{app_url}/health"
    
    while True:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=10) as resp:
                    logging.info(f"Keep-awake ping: {health_url} (Status: {resp.status})")
        except Exception as e:
            logging.warning(f"Keep-awake ping ogohlantirishi: {e}")
        await asyncio.sleep(480)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server 0.0.0.0:{port} da ishga tushirildi.")

async def run_bot():
    while True:
        try:
            logging.info("Iskndrv Games bot polling boshlanmoqda...")
            await dp.start_polling(bot, handle_signals=False)
        except Exception as e:
            logging.error(f"Bot polling xatosi: {e}. 5 soniyadan so'ng qayta uriniladi...")
            await asyncio.sleep(5)

async def main():
    print("========================================")
    print("Iskndrv Games Yagona Boti ishga tushmoqda...")
    print("Bot: @IskndrvGames_bot")
    print("========================================")

    # 1. Bazani ishga tushirish
    db.init_db()

    # 2. Web serverni Render uchun ishga tushirish
    try:
        await start_web_server()
    except Exception as e:
        logging.warning(f"Web server xatosi: {e}")

    # 3. Webhookni tozalash
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning(f"Webhook tozalash: {e}")

    # 4. Bot va Keep-awake pinger'ni yurgazish
    await asyncio.gather(
        run_bot(),
        keep_awake_pinger()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot to'xtatildi.")
