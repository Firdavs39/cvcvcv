from __future__ import annotations
from dataclasses import dataclass

# Мини-истина: расширим позже. Сейчас гарантированно OK: ru-RU, en-US.
SUPPORTED_TTS_LANGS = {"ru-RU", "en-US"}   # uz-UZ считаем неподдерживаемым в TTS

VOICES_BY_LANG = {
  "ru-RU": ["ru-RU-Wavenet-D", "ru-RU-Wavenet-C"],
  "en-US": ["en-US-Wavenet-D", "en-US-Wavenet-F"],
}

@dataclass
class TtsPlan:
    lang: str
    voice: str|None
    strategy: str  # "direct" | "translate_for_tts"
    target_lang: str|None = None  # куда переводить, если strategy=translate_for_tts

def normalize_tts_request(user_lang:str|None, user_voice:str|None)->TtsPlan:
    lang = (user_lang or "ru-RU")
    # если язык поддержан — подбираем голос
    if lang in SUPPORTED_TTS_LANGS:
        voice = user_voice if (user_voice and (lang in user_voice)) else (VOICES_BY_LANG.get(lang) or [None])[0]
        return TtsPlan(lang=lang, voice=voice, strategy="direct")
    # если язык НЕ поддержан (например, uz-UZ) — переводим для TTS на русский
    return TtsPlan(lang="ru-RU", voice=VOICES_BY_LANG["ru-RU"][0], strategy="translate_for_tts", target_lang="ru-RU")


