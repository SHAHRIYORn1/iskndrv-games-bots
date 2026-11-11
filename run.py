import asyncio
import logging
import os
import sys
from aiohttp import web
from admin_bot import admin_bot, admin_dp
from user_bot import user_bot, user_dp
import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)

# Render.com sog'liqni tekshiruvchi (Health-check) server
async def handle_ping(request):
    return web.Response(text="Iskndrv Games Bots are running 24/7!", status=200)

async def keep_awake_pinger():
    """Render bepul serverini 15 daqiqadan so'ng uxlab qolishini oldini olish uchun har 8 daqiqada o'zini ping qiladi"""
    await asyncio.sleep(60) # 1 daqiqa kutib boshlaydi
    app_url = os.environ.get("RENDER_EXTERNAL_URL", "https://iskndrv-games-bots.onrender.com")
    health_url = f"{app_url}/health"
    
    while True:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=10) as resp:
                    logging.info(f"Keep-awake ping yuborildi: {health_url} (Status: {resp.status})")
        except Exception as e:
            logging.warning(f"Keep-awake ping ogohlantirishi: {e}")
        # Har 8 daqiqada (480 soniya) qaytariladi
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
    logging.info(f"Web server 0.0.0.0:{port} manzilida ishga tushirildi.")

async def run_admin_bot():
    while True:
        try:
            logging.info("Admin bot polling boshlanmoqda...")
            await admin_dp.start_polling(admin_bot, handle_signals=False)
        except Exception as e:
            logging.error(f"Admin Bot xatosi: {e}. 5 soniyadan so'ng qayta uriniladi...")
            await asyncio.sleep(5)

async def run_user_bot():
    while True:
        try:
            logging.info("User bot polling boshlanmoqda...")
            await user_dp.start_polling(user_bot, handle_signals=False)
        except Exception as e:
            logging.error(f"User Bot xatosi: {e}. 5 soniyadan so'ng qayta uriniladi...")
            await asyncio.sleep(5)

async def main():
    print("========================================")
    print("Telegram Botlar Tizimi ishga tushmoqda...")
    print("1. Admin Bot: @iskndrAcc_Bot")
    print("2. User Bot:  @IskndrvGames_bot")
    print("========================================")

    # 1. Bazani ishga tushirish
    db.init_db()

    # 2. Web serverni Render uchun darhol ishga tushirish (Health check muvaffaqiyatli o'tishi uchun)
    try:
        await start_web_server()
    except Exception as e:
        logging.warning(f"Web server xatosi: {e}")

    # 3. Webhooklarni tozalash
    try:
        await admin_bot.delete_webhook(drop_pending_updates=True)
        await user_bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning(f"Webhook tozalash ogohlantirishi: {e}")

    # 4. Ikkala botni va doimiy uyg'oq tutuvchi tizimni parallel yurgazish
    await asyncio.gather(
        run_admin_bot(),
        run_user_bot(),
        keep_awake_pinger()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBotlar to'xtatildi.")
