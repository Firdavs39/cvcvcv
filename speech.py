import io
import os
import asyncio
from typing import Optional

from google.cloud import speech_v1p1beta1 as speech
from google.cloud import texttospeech

from config import settings
from utils.user_prefs import get as prefs_get
from i18n.tts_support import normalize_tts_request
from services.translate import translate_via_gemini

# --- TTS helpers: strip emojis + SSML prosody ---
import re, html
import logging
from google.cloud import texttospeech
from config import settings

_EMOJI_RE = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]+")
_URL_RE = re.compile(r"https?://\S+")
_COLON_CODE_RE = re.compile(r":[a-z0-9_]+:", re.IGNORECASE)

def _strip_for_tts(text: str) -> str:
    t = _EMOJI_RE.sub("", text)
    t = _COLON_CODE_RE.sub("", t)
    t = _URL_RE.sub("", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t

def _to_ssml(text: str) -> str:
    # 1) чистим текст
    t = _strip_for_tts(text)
    # 2) экранируем пользовательский текст (чтобы < и & не сломали SSML)
    t = html.escape(t)
    # 3) аккуратные паузы (вставляем ТЕГИ после экранирования, сами теги не экранируем)
    t = t.replace("...", "<break time='400ms'/>")
    t = re.sub(r"([.!?])\s+", r"\1<break time='220ms'/> ", t)
    # 4) итоговый SSML (слегка замедлим и поднимем тон на 1 полутон)
    return f"<speak><prosody rate='0.98' pitch='+1st'>{t}</prosody></speak>"

def tts_bytes(text: str, *, lang: str | None = None, voice_name: str | None = None, speaking_rate: float | None = None, pitch: float | None = None) -> bytes:
    plan = normalize_tts_request(lang, voice_name)
    speak_text = text
    if plan.strategy == "translate_for_tts":
        try:
            speak_text = translate_via_gemini(text, plan.target_lang or plan.lang)
        except Exception:
            # если перевод упал — читаем оригинал выбранным голосом (лучше так, чем падать)
            speak_text = text

    ssml = _to_ssml(speak_text)
    client = texttospeech.TextToSpeechClient()
    voice = texttospeech.VoiceSelectionParams(language_code=plan.lang, **({"name": plan.voice} if plan.voice else {}))
    audio = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
        speaking_rate=(speaking_rate if speaking_rate is not None else 0.98),
        pitch=(pitch if pitch is not None else 1.0),
    )
    return client.synthesize_speech(
        input=texttospeech.SynthesisInput(ssml=ssml), voice=voice, audio_config=audio
    ).audio_content
# --- end helpers ---

# Настройки речи из settings (без жёстких хардкодов)
STT_LANG = getattr(settings, "stt_language", "ru-RU")
TTS_VOICE = getattr(
    settings,
    "gcp_tts_voice_name",
    getattr(settings, "GCP_TTS_VOICE_NAME", "ru-RU-Neural2-D"),
)
USE_STT = getattr(settings, "enable_stt", True)
USE_TTS = getattr(settings, "enable_tts", True)

# Мягкий проброс пути к JSON с ключом в окружение
_creds = (
    # 1) JSON content via env var for serverless (preferred on Vercel)
    os.getenv("GCP_SA_JSON")
    or getattr(settings, "google_application_credentials", None)
    or getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", None)
)
if _creds and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    if _creds.strip().startswith("{"):
        # store to /tmp for runtime use
        tmp_path = "/tmp/gcp-sa.json"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(_creds)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp_path
        except Exception:
            pass
    else:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _creds


def _ensure_gcp_credentials() -> None:
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS", settings.GOOGLE_APPLICATION_CREDENTIALS
        )


class GoogleSpeechService:
    def __init__(self):
        _ensure_gcp_credentials()
        self._stt_client: Optional[speech.SpeechClient] = None
        self._tts_client: Optional[texttospeech.TextToSpeechClient] = None

    @property
    def stt_client(self) -> speech.SpeechClient:
        if self._stt_client is None:
            self._stt_client = speech.SpeechClient()
        return self._stt_client

    @property
    def tts_client(self) -> texttospeech.TextToSpeechClient:
        if self._tts_client is None:
            self._tts_client = texttospeech.TextToSpeechClient()
        return self._tts_client

    async def transcribe_ogg_opus(self, audio_bytes: bytes, language_code: str = STT_LANG, user_id: Optional[int] = None) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._transcribe_sync(audio_bytes, language_code, user_id)
        )

    def _transcribe_sync(self, audio_bytes: bytes, language_code: str, user_id: Optional[int]) -> str:
        # Определяем язык из пользовательских настроек, если доступен
        if user_id is not None:
            try:
                p = prefs_get(user_id)
                language_code = p.get("lang") or "ru-RU"
            except Exception:
                language_code = language_code or "ru-RU"
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=48000,
            audio_channel_count=1,
            language_code=language_code,
            alternative_language_codes=["en-US", "uk-UA"],
            enable_automatic_punctuation=True,
            model="latest_long",
        )
        response = self.stt_client.recognize(config=config, audio=audio)
        for result in response.results:
            if result.alternatives:
                return result.alternatives[0].transcript.strip()
        return ""

    async def synthesize_speech(
        self,
        text: str,
        language_code: str = STT_LANG,
        voice_name: Optional[str] = None,
        speaking_rate: Optional[float] = None,
        pitch: Optional[float] = None,
        encoding: Optional[str] = None,
    ) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._synthesize_sync(
                text=text,
                language_code=language_code,
                voice_name=voice_name or TTS_VOICE,
                speaking_rate=speaking_rate if speaking_rate is not None else settings.GCP_TTS_SPEAKING_RATE,
                pitch=pitch if pitch is not None else settings.GCP_TTS_PITCH,
                encoding=encoding or settings.GCP_TTS_ENCODING,
            ),
        )

    def _synthesize_sync(
        self,
        text: str,
        language_code: str,
        voice_name: str,
        speaking_rate: float,
        pitch: float,
        encoding: str,
    ) -> bytes:
        # Trim overly long text for better UX in voice notes
        safe_text = text.strip()
        if len(safe_text) > 1200:
            safe_text = safe_text[:1200] + "…"

        synthesis_input = texttospeech.SynthesisInput(text=safe_text)

        candidate_voices = [voice_name, "ru-RU-Neural2-D", "ru-RU-Wavenet-D", "ru-RU-Wavenet-C", "ru-RU-Standard-A"]
        last_err: Optional[Exception] = None

        for candidate in [v for v in candidate_voices if v]:
            try:
                voice_params = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=candidate,
                )
                if encoding.upper() == "OGG_OPUS":
                    audio_config = texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
                        speaking_rate=speaking_rate,
                        pitch=pitch,
                    )
                else:
                    audio_config = texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.MP3,
                        speaking_rate=speaking_rate,
                        pitch=pitch,
                    )
                response = self.tts_client.synthesize_speech(
                    input=synthesis_input, voice=voice_params, audio_config=audio_config
                )
                return response.audio_content
            except Exception as err:  # fallback to next candidate voice
                last_err = err
                continue

        if last_err:
            raise last_err
        raise RuntimeError("TTS synthesis failed: no voice candidates succeeded")


speech_service = GoogleSpeechService()


