from telegram_bot import FirdavsTelegramBot

# При локальном запуске продолжаем использовать polling.
# На Vercel будет использоваться FastAPI вебхук из файла api/telegram-webhook.py
if __name__ == "__main__":
    FirdavsTelegramBot().run()
