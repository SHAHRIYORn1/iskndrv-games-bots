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

# Render.com bepul Web Service uchun sog'liqni tekshiruvchi (Health-check) server
async def handle_ping(request):
    return web.Response(text="Iskndrv Games Bots are running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server port {port} da ishga tushirildi.")

async def main():
    print("========================================")
    print("Telegram Botlar Tizimi ishga tushmoqda...")
    print("1. Admin Bot: @iskndrAcc_Bot")
    print("2. User Bot:  @IskndrvGames_bot")
    print("========================================")

    # Bazani ishga tushirish
    db.init_db()

    # Webhooklarni tozalash
    try:
        await admin_bot.delete_webhook(drop_pending_updates=True)
        await user_bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning(f"Webhook tozalashda xatolik: {e}")

    # Web serverni ishga tushirish (Render uchun)
    try:
        await start_web_server()
    except Exception as e:
        logging.warning(f"Web server xatosi (local rejimda bu muhim emas): {e}")

    print("Botlar so'rovlarni qabul qilishga tayyor! (Polling boshlandi)")
    
    # Ikkala botni parallel ishga tushirish
    await asyncio.gather(
        admin_dp.start_polling(admin_bot),
        user_dp.start_polling(user_bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBotlar to'xtatildi.")
