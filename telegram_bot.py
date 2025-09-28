import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ChatAction
from telegram.helpers import escape_markdown
import tempfile, os
from pathlib import Path

from config import settings
from ai_agent import FirdavsAIAgent
from speech import speech_service, tts_bytes
from utils.user_prefs import get as prefs_get, set as prefs_set
from i18n.tts_support import VOICES_BY_LANG, SUPPORTED_TTS_LANGS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---- user prefs constants ----
SUPPORTED_LANGS = ["ru-RU", "uz-UZ", "en-US"]

def rate_pitch_for_style(style: str) -> dict:
    s = (style or "neutral").lower()
    if s == "cheerful":
        return {"speaking_rate": 1.12, "pitch": 3.0}
    if s == "calm":
        return {"speaking_rate": 0.94, "pitch": -1.0}
    return {"speaking_rate": 0.98, "pitch": 1.0}

# ---- helper: send voice via temp file (safe for PTB v20) ----
async def _send_voice_bytes(bot, chat_id: int, audio_bytes: bytes, filename: str = "reply.ogg"):
    tmp = Path(tempfile.gettempdir()) / filename
    tmp.write_bytes(audio_bytes)
    try:
        await bot.send_voice(chat_id=chat_id, voice=str(tmp))
    finally:
        try:
            os.remove(tmp)
        except:
            pass

async def on_error(update, context):
    import logging as _logging
    _logging.getLogger("telegram_bot").exception("Unhandled", exc_info=context.error)

class FirdavsTelegramBot:
    def __init__(self):
        logger.info("🚀 Инициализация бота...")
        self.ai_agent = FirdavsAIAgent()
        self.app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
        self.app.add_error_handler(on_error)
        self.setup_handlers()
        logger.info("✅ Бот готов к работе!")

    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("contact", self.contact_command))
        self.app.add_handler(CommandHandler("skills", self.skills_command))
        self.app.add_handler(CommandHandler("experience", self.experience_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("debug", self.debug_command))  # Новая команда
        self.app.add_handler(CommandHandler("voices", self.voices_command))
        self.app.add_handler(CommandHandler("lang", self.lang_command))
        self.app.add_handler(CommandHandler("voice", self.voice_command))
        self.app.add_handler(CommandHandler("style", self.style_command))
        self.app.add_handler(CommandHandler("prefs", self.prefs_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Стартовое меню с улучшенными кнопками"""
        keyboard = [
            [InlineKeyboardButton("💼 Опыт работы", callback_data="experience"),
             InlineKeyboardButton("🛠 Навыки", callback_data="skills")],
            [InlineKeyboardButton("🚀 Крутые проекты", callback_data="projects"),
             InlineKeyboardButton("🎓 Образование", callback_data="education")],
            [InlineKeyboardButton("📱 Контакты", callback_data="contacts"),
             InlineKeyboardButton("🤖 Voice AI", callback_data="voice_ai")]
        ]
        await update.message.reply_text(
            self.ai_agent.get_introduction(),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "Краткая помощь:\n\n"
            "- /lang — выбрать язык (ru-RU, uz-UZ, en-US)\n"
            "- /voice — выбрать голос для языка\n"
            "- /style — neutral | calm | cheerful\n"
            "- /prefs — показать мои текущие настройки"
        )
        await update.message.reply_text(help_text)

    async def prefs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        p = prefs_get(uid)
        lang = p.get("lang") or "ru-RU"
        voice = p.get("voice") or "auto"
        style = p.get("style") or "neutral"
        msg = (
            "Текущие настройки:\n"
            f"- Язык: {lang}\n"
            f"- Голос: {voice}\n"
            f"- Стиль: {style}"
        )
        await update.message.reply_text(msg)

    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            self.ai_agent.get_contact_info(),
            parse_mode="Markdown"
        )

    async def skills_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            self.ai_agent.get_skills_overview(),
            parse_mode="Markdown"
        )

    async def experience_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            self.ai_agent.get_experience_overview(),
            parse_mode="Markdown"
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статус системы с диагностикой"""
        mem_status = self.ai_agent.memory.get_diagnostics()
        status_text = (
            "**🔧 Статус системы:**\n\n"
            f"⚙️ Модель: {settings.GEMINI_MODEL}\n"
            f"{mem_status}\n\n"
            "Всё работает! Спрашивай про Фирдавса 😊"
        )
        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def lang_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор языка"""
        keyboard = [[InlineKeyboardButton(code, callback_data=f"set_lang:{code}")] for code in SUPPORTED_LANGS]
        await update.message.reply_text(
            "Выберите язык для распознавания/озвучки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def voice_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор голоса для текущего языка"""
        uid = update.effective_user.id
        prefs = prefs_get(uid)
        lang = prefs.get("lang", "ru-RU")
        voices = VOICES_BY_LANG.get(lang, [])
        if not voices:
            await update.message.reply_text(
                f"Для {lang} родных голосов нет, используем перевод для TTS."
            )
            return
        keyboard = [[InlineKeyboardButton(v, callback_data=f"set_voice:{v}")] for v in voices]
        await update.message.reply_text(
            f"Выберите голос для {lang}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def style_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать выбор стиля озвучки"""
        styles = ["neutral", "calm", "cheerful"]
        keyboard = [[InlineKeyboardButton(s, callback_data=f"set_style:{s}")] for s in styles]
        await update.message.reply_text(
            "Выберите стиль озвучки:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Детальная диагностика для отладки"""
        user_id_int = update.effective_user.id
        user_id_int = update.effective_user.id
        user_id = str(update.effective_user.id)
        
        # Тестовый запрос к контексту
        test_context = self.ai_agent.memory.get_relevant_context(
            "опыт работы навыки проекты", 
            user_id
        )
        
        debug_info = (
            "**🐛 Debug информация:**\n\n"
            f"User ID: {user_id}\n"
            f"Gemini Model: {settings.GEMINI_MODEL}\n"
            f"mem0 status: {self.ai_agent.memory.mem0_kind}\n"
            f"CV chunks: {self.ai_agent.memory.cv_col.count()}\n"
            f"KB chunks: {self.ai_agent.memory.kb_col.count()}\n\n"
            f"**Пример контекста (первые 500 символов):**\n"
            f"```\n{test_context[:500]}\n```"
        )
        
        await update.message.reply_text(debug_info, parse_mode="Markdown")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок с улучшенными запросами"""
        query = update.callback_query
        await query.answer()
        user_id_str = str(query.from_user.id)
        user_id = query.from_user.id

        # Более естественные и детальные запросы
        mapping = {
            "experience": "Расскажи подробно про опыт работы Фирдавса - где работал, "
                         "что делал, какие были интересные задачи и достижения?",
            
            "skills": "Какой технический стек у Фирдавса? В чем он реально крут? "
                     "Какие технологии использует для AI/ML проектов?",
            
            "projects": "Покажи самые впечатляющие проекты Фирдавса - что-то wow-эффектное! "
                       "Особенно интересуют проекты с voice AI и локальными моделями.",
            
            "education": "Какое образование у Фирдавса? Где учился, какие курсы проходил?",
            
            "contacts": "Дай все контакты Фирдавса для связи. Как лучше с ним связаться?",
            
            "voice_ai": "Расскажи про опыт Фирдавса с voice AI и voice cloning. "
                       "Что он умеет делать с голосовыми технологиями?"
        }
        
        data = query.data or ""

        # Обработка выбора языка
        if data.startswith("set_lang:"):
            lang = data.split(":", 1)[1]
            if lang in SUPPORTED_LANGS:
                p = prefs_set(user_id, lang=lang)
                # Если для нового языка нет родных голосов — обнуляем voice
                if lang not in VOICES_BY_LANG:
                    prefs_set(user_id, voice=None)
                if lang == "uz-UZ":
                    await query.edit_message_text(
                        "Язык установлен: uz-UZ.\n"
                        "Текст будет на узбекском. Голос — переведён на русский для лучшей озвучки. "
                        "Можно сменить /voice или /style."
                    )
                else:
                    await query.edit_message_text(
                        f"Язык установлен: {lang}. Теперь выберите голос: /voice"
                    )
            else:
                await query.edit_message_text("Неподдерживаемый язык")
            return

        # Обработка выбора голоса
        if data.startswith("set_voice:"):
            voice = data.split(":", 1)[1]
            prefs_set(user_id, voice=voice)
            await query.edit_message_text(f"Голос установлен: {voice}")
            return

        # Обработка выбора стиля
        if data.startswith("set_style:"):
            style = data.split(":", 1)[1]
            if style not in ("neutral", "calm", "cheerful"):
                await query.edit_message_text("Неподдерживаемый стиль")
                return
            prefs_set(user_id, style=style)
            await query.edit_message_text(f"Готово: стиль = {style}")
            return

        # Озвучить длинный ответ по кнопке
        if data == "speak_text":
            # пытаемся взять последнее сообщение (сам длинный текст), синтезируем и отправляем voice
            chat_id = query.message.chat.id
            text_to_speak = query.message.text or ""
            if not text_to_speak:
                await query.edit_message_text("Нет текста для озвучивания")
                return
            p = prefs_get(user_id)
            rp = rate_pitch_for_style(p.get("style", "neutral"))
            audio_bytes = tts_bytes(
                text_to_speak,
                lang=p.get("lang") or "ru-RU",
                voice_name=p.get("voice"),
                **rp
            )
            await _send_voice_bytes(context.bot, chat_id, audio_bytes)
            await query.answer("Озвучено")
            return

        if data in mapping:
            await context.bot.send_chat_action(
                chat_id=query.message.chat.id, 
                action=ChatAction.TYPING
            )
            
            response = self.ai_agent.generate_response(mapping[data], user_id_str)
            
            # Добавляем кнопку "Назад в меню"
            keyboard = [[InlineKeyboardButton("↩️ Главное меню", callback_data="menu")]]
            
            await query.edit_message_text(
                text=response,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        elif data == "menu":
            # Возврат в главное меню
            keyboard = [
                [InlineKeyboardButton("💼 Опыт работы", callback_data="experience"),
                 InlineKeyboardButton("🛠 Навыки", callback_data="skills")],
                [InlineKeyboardButton("🚀 Крутые проекты", callback_data="projects"),
                 InlineKeyboardButton("🎓 Образование", callback_data="education")],
                [InlineKeyboardButton("📱 Контакты", callback_data="contacts"),
                 InlineKeyboardButton("🤖 Voice AI", callback_data="voice_ai")]
            ]
            
            await query.edit_message_text(
                text=self.ai_agent.get_introduction(),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name
        
        logger.info(f"💬 Сообщение от {user_name} (ID: {user_id}): {update.message.text}")
        
        # Показываем что бот печатает
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action=ChatAction.TYPING
        )
        
        # Генерируем ответ
        response = self.ai_agent.generate_response(update.message.text, user_id)
        
        # Отправляем с поддержкой Markdown
        try:
            await update.message.reply_text(response, parse_mode="Markdown")
        except:
            # Если Markdown сломался, отправляем без форматирования
            await update.message.reply_text(response)
        
        logger.info(f"✅ Ответ отправлен {user_name}")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка голосовых сообщений: STT -> LLM -> TTS (OGG_OPUS voice note)"""
        user_id_int = update.effective_user.id
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.first_name
        voice = update.message.voice

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.RECORD_VOICE
        )

        try:
            file = await context.bot.get_file(voice.file_id)
            ogg_bytes = await file.download_as_bytearray()

            # STT (Google) с языком из prefs и фолбэком для узбекского
            p_stt = prefs_get(user_id_int)
            stt_lang = p_stt.get("lang") or "ru-RU"
            if stt_lang == "uz-UZ":
                stt_lang = "ru-RU"  # TODO: включить Whisper позже
            text = await speech_service.transcribe_ogg_opus(bytes(ogg_bytes), language_code=stt_lang, user_id=user_id_int)
            if not text:
                await update.message.reply_text("Не удалось распознать речь. Попробуй ещё раз ✋")
                return

            # LLM ответ
            response_text = self.ai_agent.generate_response(text, user_id)

            # Если ответ слишком длинный — не озвучиваем автоматически, предлагаем кнопку
            if len(response_text) > 900:
                keyboard = [[InlineKeyboardButton("Озвучить", callback_data="speak_text")]]
                await update.message.reply_text(response_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                # TTS с учетом пользовательских настроек
                p = prefs_get(user_id_int)
                rp = rate_pitch_for_style(p.get("style", "neutral"))
                audio_bytes = tts_bytes(
                    response_text,
                    lang=p.get("lang") or "ru-RU",
                    voice_name=p.get("voice"),
                    **rp
                )

                await _send_voice_bytes(context.bot, update.effective_chat.id, audio_bytes)

            logger.info(f"🎤 Voice processed for {user_name}")
        except Exception:
            logger.exception("Voice handling failed")
            await update.message.reply_text("Упс, не получилось обработать голосовое. Попробуй ещё раз позже.")

    async def voices_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать рекомендованные голоса Google TTS"""
        rec = (
            "Рекомендованные русские голоса Google TTS (качество/естественность):\n\n"
            "- ru-RU-Neural2-D (мужской, естественный)\n"
            "- ru-RU-Wavenet-D (мужской, нейтральный)\n"
            "- ru-RU-Wavenet-C (женский, тёплый)\n"
            "- ru-RU-Standard-A (мужской, базовый)\n\n"
            f"Текущий голос: {settings.GCP_TTS_VOICE_NAME}\n"
            "Можно изменить через переменную окружения GCP_TTS_VOICE_NAME"
        )
        await update.message.reply_text(rec)

    def run(self):
        """Запуск бота"""
        logger.info("🎯 Запускаем polling...")
        self.app.run_polling(drop_pending_updates=True)




