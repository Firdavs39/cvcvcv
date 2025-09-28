import logging
import random
from datetime import datetime
import google.generativeai as genai
from config import settings, CV_DATA
from memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class FirdavsAIAgent:
    def __init__(self):
        self.memory = MemoryManager()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        
    def generate_response(self, user_message: str, user_id: str) -> str:
        today = datetime.now().strftime("%d.%m.%Y")
        context = self.memory.get_relevant_context(user_message, user_id)
        
        # Более человечный и вариативный промпт
        SYSTEM_PROMPT = f"""Ты личный AI-ассистент Фирдавса Файзуллаева — опытного AI/ML инженера.
Твоя задача — помогать людям узнать о его навыках, опыте и проектах.

СТИЛЬ ОБЩЕНИЯ:
- Будь дружелюбным и естественным, как будто рассказываешь о талантливом коллеге
- Используй разговорные обороты: 'кстати', 'между прочим', 'вообще', 'на самом деле'
- Показывай энтузиазм когда говоришь о крутых проектах или достижениях
- НЕ начинай каждый ответ с 'Конечно!', 'Отлично!' или других шаблонных фраз
- Варьируй структуру ответов - не всегда делай списки, иногда просто рассказывай
- Можешь использовать эмодзи, но в меру (1-2 на сообщение максимум)

ВАЖНЫЕ ПРАВИЛА:
- Опирайся на факты из контекста CV и базы знаний, но подавай их живо и интересно
- Если чего-то не знаешь — честно скажи и предложи рассказать что-то другое
- Добавляй контекст и объяснения: 'Это особенно впечатляет, потому что...'
- При упоминании технических достижений объясняй, почему это круто для бизнеса
- Упоминай конкретные цифры и метрики из CV когда это уместно
- НЕ придумывай факты, которых нет в контексте

Сегодня: {today}

КОНТЕКСТ О ФИРДАВСЕ:
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{user_message}

ТВОЙ ОТВЕТ (естественный и информативный):"""

        try:
            resp = self.model.generate_content(SYSTEM_PROMPT)
            text = (resp.text or "").strip()
            if not text:
                text = "Хм, что-то пошло не так. Давай я лучше расскажу про опыт Фирдавса в AI?"
        except Exception as e:
            logger.exception("Gemini error")
            text = "Упс, технические неполадки 🤔 Попробуй спросить еще раз?"

        self.memory.add_conversation_memory(user_id, user_message, text)
        return text

    def get_introduction(self) -> str:
        """Вариативные приветствия для естественности"""
        intros = [
            "Привет! Я AI-ассистент Фирдавса Файзуллаева 👋\n\n"
            "Фирдавс — это ML-инженер с 5+ годами опыта, который специализируется на LLM-системах и voice AI. "
            "У него за плечами 15+ production ботов и системы, обрабатывающие 500K+ запросов в день!\n\n"
            "Что тебя интересует? Могу рассказать про его проекты, технический стек или поделиться контактами.",
            
            "Здравствуй! Помогу узнать больше о Фирдавсе Файзуллаеве 🚀\n\n"
            "Он архитектор LLM-систем с глубокой экспертизой в локальных моделях (Llama, Qwen, DeepSeek). "
            "Особенно крут в RAG-системах с персистентной памятью и voice cloning технологиях.\n\n"
            "Спрашивай про опыт работы, крутые проекты или навыки!",
            
            "Приветствую! Я виртуальный помощник Фирдавса — AI/ML инженера из Москвы 🤖\n\n"
            "Кстати, у него дома целая лаборатория с RTX 4090 для экспериментов с локальными моделями! "
            "Благодаря этому он снижает затраты на AI до 80% по сравнению с облачными API.\n\n"
            "Расскажу про его опыт в Voximplant, проекты с voice AI или техстек. С чего начнем?"
        ]
        return random.choice(intros)

    def get_contact_info(self) -> str:
        """Контакты с контекстом"""
        variants = [
            f"📧 Email: {CV_DATA['contacts']['email']}\n"
            f"💬 Telegram: {CV_DATA['contacts']['telegram']}\n\n"
            f"Фирдавс открыт для интересных AI/ML проектов и технического лидерства. "
            f"Готов работать как в Москве, так и удаленно!",
            
            f"Вот как можно связаться с Фирдавсом:\n\n"
            f"📨 {CV_DATA['contacts']['email']}\n"
            f"✈️ {CV_DATA['contacts']['telegram']}\n\n"
            f"Кстати, он сейчас в активном поиске крутых проектов в области AI!"
        ]
        return random.choice(variants)

    def get_skills_overview(self) -> str:
        """Навыки с пояснениями"""
        s = CV_DATA["skills"]
        return (
            "Технический арсенал Фирдавса впечатляет:\n\n"
            f"🤖 **Модели:** {', '.join(s['models'])}\n"
            "Работает как с облачными API, так и крутит модели локально на своей RTX 4090!\n\n"
            f"🛠 **Фреймворки:** {', '.join(s['frameworks'])}\n"
            "Особенно силен в LangGraph для сложных агентских цепочек.\n\n"
            f"☁️ **Инфраструктура:** {', '.join(s['infra'])}\n"
            "Умеет и в облака, и в контейнеры, и в оптимизацию inference!\n\n"
            "💡 Главная фишка — умение снижать затраты на 80% через локальный деплой и fine-tuning!"
        )

    def get_experience_overview(self) -> str:
        """Опыт работы в story-telling стиле"""
        exp_text = "История карьеры Фирдавса — это путь от Data Scientist до архитектора AI-систем:\n\n"
        
        for w in CV_DATA["work_experience"]:
            if w["company"] == "AI Dynamics":
                exp_text += (
                    f"🚀 **{w['company']}** — {w['position']} ({w['period']})\n"
                    f"Тут он развернулся по полной: {', '.join(w['highlights'])}. "
                    f"Самое крутое — построил систему обработки 500K+ запросов в день!\n\n"
                )
            elif w["company"] == "TechForward Solutions":
                exp_text += (
                    f"💼 **{w['company']}** — {w['position']} ({w['period']})\n"
                    f"Фокус на enterprise: {', '.join(w['highlights'])}. "
                    f"Внедрил RAG для финансовых документов — это было сложно, но результат впечатлил клиентов.\n\n"
                )
            else:
                exp_text += (
                    f"📊 **{w['company']}** — {w['position']} ({w['period']})\n"
                    f"Начало пути в ML: {', '.join(w['highlights'])}. "
                    f"Здесь заложил фундамент для работы с большими данными.\n\n"
                )
        
        exp_text += "За эти годы Фирдавс вырос от аналитика до того, кто строит AI-мозги для бизнеса!"
        return exp_text