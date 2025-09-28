from typing import Optional, Dict, Any
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # TG
    telegram_bot_token: str = Field(
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN")
    )

    # LLM
    gemini_api_key: str = Field(
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )

    # GCP / Voice
    google_application_credentials: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS", "GCP_CREDENTIALS"),
    )
    stt_language: str = Field(default="ru-RU", validation_alias=AliasChoices("STT_LANGUAGE"))
    gcp_tts_voice_name: str = Field(
        default="ru-RU-Neural2-D",
        validation_alias=AliasChoices("GCP_TTS_VOICE_NAME", "TTS_VOICE"),
    )
    enable_stt: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_STT"))
    enable_tts: bool = Field(default=True, validation_alias=AliasChoices("ENABLE_TTS"))

    # Дополнительные поля для совместимости с существующим кодом
    gemini_model: str = Field(
        default="gemini-2.0-flash-001", validation_alias=AliasChoices("GEMINI_MODEL")
    )
    gcp_tts_speaking_rate: float = Field(
        default=1.0, validation_alias=AliasChoices("GCP_TTS_SPEAKING_RATE")
    )
    gcp_tts_pitch: float = Field(
        default=0.0, validation_alias=AliasChoices("GCP_TTS_PITCH")
    )
    gcp_tts_encoding: str = Field(
        default="OGG_OPUS", validation_alias=AliasChoices("GCP_TTS_ENCODING")
    )
    openai_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    mem0_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("MEM0_API_KEY")
    )
    mem0_org_id: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("MEM0_ORG_ID")
    )
    mem0_project_id: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("MEM0_PROJECT_ID")
    )

    # общие настройки .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="cp1251",
        extra="ignore",        # игнорируем лишние ключи, чтобы не падать
        case_sensitive=False,  # переменные можно писать в любом регистре
    )

    # Совместимость со старым обращением к атрибутам (верхний регистр)
    @property
    def TELEGRAM_TOKEN(self) -> str:
        return self.telegram_bot_token

    @property
    def GEMINI_API_KEY(self) -> str:
        return self.gemini_api_key

    @property
    def GEMINI_MODEL(self) -> str:
        return self.gemini_model

    @property
    def GOOGLE_APPLICATION_CREDENTIALS(self) -> Optional[str]:
        return self.google_application_credentials

    @property
    def GCP_TTS_VOICE_NAME(self) -> str:
        return self.gcp_tts_voice_name

    @property
    def GCP_TTS_SPEAKING_RATE(self) -> float:
        return self.gcp_tts_speaking_rate

    @property
    def GCP_TTS_PITCH(self) -> float:
        return self.gcp_tts_pitch

    @property
    def GCP_TTS_ENCODING(self) -> str:
        return self.gcp_tts_encoding

    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        return self.openai_api_key

    @property
    def MEM0_API_KEY(self) -> Optional[str]:
        return self.mem0_api_key

    @property
    def MEM0_ORG_ID(self) -> Optional[str]:
        return self.mem0_org_id

    @property
    def MEM0_PROJECT_ID(self) -> Optional[str]:
        return self.mem0_project_id

# Новый интерфейс (современный)
settings = Settings()

# Алиасы для совместимости со старым кодом:
TELEGRAM_TOKEN  = settings.TELEGRAM_TOKEN
GEMINI_API_KEY  = settings.GEMINI_API_KEY
GEMINI_MODEL    = settings.GEMINI_MODEL
OPENAI_API_KEY  = settings.OPENAI_API_KEY
MEM0_API_KEY    = settings.MEM0_API_KEY
MEM0_ORG_ID     = settings.MEM0_ORG_ID
MEM0_PROJECT_ID = settings.MEM0_PROJECT_ID

# Мини-KB (CV) для RAG
CV_DATA: Dict[str, Any] = {
    "personal_info": {
        "name": "Фирдавс Файзуллаев",
        "title": "AI/ML Engineer | Архитектор LLM-систем",
        "experience_years": "5+",
        "location": "Москва",
        "expertise": "Production LLM, RAG, мультиагентные системы"
    },
    "contacts": {
        "email": "firdavs.fayzullaev@gmail.com",
        "telegram": "@FirdavsAIDev",
        "availability": "Открыт для AI/ML проектов и технического лидерства"
    },
    "work_experience": [
        {
            "company": "AI Dynamics",
            "period": "Февраль 2024 — Октябрь 2024",
            "position": "AI/ML Engineer",
            "highlights": [
                "Advanced Multi-Modal RAG Platform",
                "Autonomous Agent Network",
                "Real-time Voice AI"
            ]
        },
        {
            "company": "TechForward Solutions",
            "period": "Март 2022 — Январь 2024",
            "position": "ML Engineer",
            "highlights": [
                "Enterprise Knowledge Management",
                "Financial Document Intelligence",
                "Conversational AI Platform"
            ]
        },
        {
            "company": "Analytics Pro",
            "period": "Сентябрь 2020 — Февраль 2022",
            "position": "Data Scientist",
            "highlights": [
                "Predictive Analytics",
                "NLP Classification",
                "Recommendation Engine"
            ]
        }
    ],
    "skills": {
        "models": ["Llama", "DeepSeek", "Qwen", "Claude", "GPT"],
        "frameworks": ["LangChain", "LangGraph", "CrewAI", "AutoGen", "DSPy"],
        "infra": ["FastAPI", "Docker", "Kubernetes", "vLLM", "TGI", "AWS", "GCP"]
    },
    "education": {
        "university": "РУДН",
        "degree": "Прикладная информатика",
        "period": "2018–2022"
    }
}

