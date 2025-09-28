import os
import json
import asyncio
from typing import Any, Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
import google.generativeai as genai

# Загружаем .env (если он включен в сборку)
try:
    load_dotenv()
except Exception:
    pass

# Мини-настройки (можно задать через .env или env)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "REPLACE_TELEGRAM_BOT_TOKEN"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "REPLACE_GOOGLE_API_KEY"
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.0-flash-001"

from utils.user_prefs import get as prefs_get, set as prefs_set


app = FastAPI()

# Инициализируем Gemini один раз на холодный старт
try:
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("REPLACE_"):
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    else:
        _gemini_model = None
except Exception:
    _gemini_model = None


def _get_bot_token() -> str:
    token = TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN not set")
    return token


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_get_bot_token()}/{method}"


async def _tg(method: str, data: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_api_url(method), json=data)
        r.raise_for_status()
        return r.json()


async def _send_action(chat_id: int, action: str) -> None:
    try:
        await _tg("sendChatAction", {"chat_id": chat_id, "action": action})
    except Exception:
        pass


async def _send_message(chat_id: int, text: str, reply_markup: Dict[str, Any] | None = None) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        await _tg("sendMessage", payload)
    except Exception:
        # Fallback without Markdown if formatting error
        await _tg("sendMessage", {"chat_id": chat_id, "text": text})


async def _send_voice_bytes(chat_id: int, audio_bytes: bytes, filename: str = "reply.ogg") -> None:
    # Telegram needs multipart/form-data for voice; use URL upload via httpx
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"voice": (filename, audio_bytes, "audio/ogg")}
        data = {"chat_id": str(chat_id)}
        r = await client.post(_api_url("sendVoice"), data=data, files=files)
        r.raise_for_status()


def _check_secret_header(request: Request) -> None:
    secret_expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not secret_expected:
        return  # no check configured
    secret_got = request.headers.get("x-telegram-bot-api-secret-token")
    if not secret_got or secret_got != secret_expected:
        raise HTTPException(status_code=401, detail="Invalid secret token")


async def _download_file(file_id: str) -> bytes:
    # 1) getFile
    async with httpx.AsyncClient(timeout=60) as client:
        r1 = await client.post(_api_url("getFile"), json={"file_id": file_id})
        r1.raise_for_status()
        info = r1.json()
        file_path = info.get("result", {}).get("file_path")
        if not file_path:
            raise RuntimeError("No file_path from getFile")
        # 2) download
        url = f"https://api.telegram.org/file/bot{_get_bot_token()}/{file_path}"
        r2 = await client.get(url)
        r2.raise_for_status()
        return r2.content


@app.post("/")
async def telegram_webhook(request: Request):
    _check_secret_header(request)
    update = await request.json()

    # Basic fields
    message = update.get("message") or update.get("edited_message")
    callback_query = update.get("callback_query")

    # Handle callback buttons
    if callback_query:
        qdata = callback_query.get("data") or ""
        from_user = callback_query.get("from", {})
        chat = callback_query.get("message", {}).get("chat", {})
        chat_id = chat.get("id")
        user_id = from_user.get("id")

        if not chat_id:
            return {"ok": True}

        # Preferences
        if qdata.startswith("set_lang:"):
            lang = qdata.split(":", 1)[1]
            prefs_set(int(user_id), lang=lang)
            await _send_message(chat_id, f"Язык установлен: {lang}")
            return {"ok": True}
        if qdata.startswith("set_voice:"):
            voice = qdata.split(":", 1)[1]
            prefs_set(int(user_id), voice=voice)
            await _send_message(chat_id, f"Голос установлен: {voice}")
            return {"ok": True}
        if qdata.startswith("set_style:"):
            style = qdata.split(":", 1)[1]
            prefs_set(int(user_id), style=style)
            await _send_message(chat_id, f"Стиль установлен: {style}")
            return {"ok": True}

        # Fallback: простое меню/подсказка
        await _send_message(chat_id, "Пришлите текстовый вопрос — отвечу.")
        return {"ok": True}

    # Handle text and voice
    if message:
        chat_id = message.get("chat", {}).get("id")
        from_user = message.get("from", {})
        user_id = str(from_user.get("id"))

        if "text" in message:
            text = message["text"]
            await _send_action(chat_id, "typing")
            response = _gen_answer(text, user_id)
            await _send_message(chat_id, response)
            return {"ok": True}

        if "voice" in message:
            # Упрощение: пока не обрабатываем голос в serverless (уменьшаем вес функции)
            await _send_message(chat_id, "Пока поддерживаю только текстовые сообщения в облаке. Отправь текст ✍️")
            return {"ok": True}

    # Unknown update type
    return {"ok": True}


@app.get("/setup")
async def setup_webhook(request: Request):
    # Устанавливаем вебхук автоматически, используя текущий хост
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not host:
        raise HTTPException(status_code=400, detail="No host header")
    scheme = "https"
    url = f"{scheme}://{host}/api/telegram-webhook"
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or ""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"https://api.telegram.org/bot{_get_bot_token()}/setWebhook",
                params={"url": url, "secret_token": secret} if secret else {"url": url},
            )
            r.raise_for_status()
            return {"ok": True, "url": url, "telegram": r.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Дополнительные маршруты на случай, если Vercel не обрезает префикс пути
@app.post("/api/telegram-webhook")
async def telegram_webhook_fullpath(request: Request):
    return await telegram_webhook(request)


@app.get("/api/telegram-webhook/setup")
async def setup_webhook_fullpath(request: Request):
    return await setup_webhook(request)


# Catch-all для любых POST путей (на случай отличий префикса)
@app.post("/{_any:path}")
async def telegram_webhook_catch_all(request: Request, _any: str):
    return await telegram_webhook(request)


def _gen_answer(user_message: str, user_id: str) -> str:
    """Простой ответ через Gemini без внешних зависимостей."""
    if not _gemini_model:
        return "Сервис временно не сконфигурирован. Нужен GEMINI_API_KEY."
    prompt = (
        "Ты дружелюбный ассистент. Отвечай коротко и по делу, на русском.\n\n"
        f"Вопрос: {user_message}\n\nОтвет:"
    )
    try:
        resp = _gemini_model.generate_content(prompt)
        text = (getattr(resp, "text", "") or "").strip()
        return text or "Не удалось сгенерировать ответ."
    except Exception:
        return "Упс, не получилось ответить сейчас."


