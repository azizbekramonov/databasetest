import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiohttp import web
import asyncpg
from dotenv import load_dotenv

# .env faylini yuklash (Lokal ishlab chiqish uchun)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", 8080))

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

# Global o'zgaruvchilar
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_pool = None


# ----------------------------------------------------
# 1. DATABASE SETUP (Supabase PostgreSQL)
# ----------------------------------------------------
async def init_db():
  global db_pool
  try:
    # Supabase PostgreSQL ga ulanish hovuzi (pool) yaratish
    db_pool = await asyncpg.create_pool(
        dsn=DATABASE_URL, min_size=1, max_size=5
    )
    logging.info("Supabase PostgreSQL bazasiga muvaffaqiyatli ulandi!")

    # Test jadvalini yaratish (agar mavjud bo'lmasa)
    async with db_pool.acquire() as connection:
      await connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
  except Exception as e:
    logging.error(f"Baza bilan ulanishda xatolik: {e}")


# ----------------------------------------------------
# 2. BOT HANDLERS
# ----------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
  user_id = message.from_user.id
  username = message.from_user.username
  first_name = message.from_user.first_name

  # Foydalanuvchini Supabase bazasiga saqlash
  if db_pool:
    async with db_pool.acquire() as conn:
      await conn.execute(
          """
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE 
                SET username = EXCLUDED.username, first_name = EXCLUDED.first_name
            """,
          user_id,
          username,
          first_name,
      )

  await message.answer(
      f"Salom, {first_name}! 👋\nSizning ma'lumotlaringiz Supabase bazasiga saqlandi."
  )


# ----------------------------------------------------
# 3. HTTP SERVER FOR UPTIMEROBOT & RENDER
# ----------------------------------------------------
async def handle_ping(request):
  """UptimeRobot har 5 minutda shu manzillarga so'rov yuboradi"""
  return web.Response(text="Bot is running active!", status=200)


async def start_web_server():
  app = web.Application()
  app.router.add_get("/", handle_ping)
  app.router.add_get("/health", handle_ping)

  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, "0.0.0.0", PORT)
  await site.start()
  logging.info(f"Web server {PORT}-portda ishga tushdi.")


# ----------------------------------------------------
# 4. MAIN RUNNER
# ----------------------------------------------------
async def main():
  # 1. Baza bilan ulanish
  await init_db()

  # 2. Web serverni ishga tushirish (Render & UptimeRobot uchun)
  await start_web_server()

  # 3. Telegram Polling'ni boshlash
  logging.info("Bot polling rejida ishga tushmoqda...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())