from __future__ import annotations
from typing import Optional
import google.generativeai as genai
from config import settings

def translate_via_gemini(text:str, target_lang:str)->str:
    # target_lang: "ru-RU"|"en-US" ... (возьмем язык без региона)
    tl = (target_lang or "ru-RU").split("-")[0]
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Переведи аккуратно и естественно на язык '{tl}'. Верни только перевод, без пояснений:\n\n{text}"
    out = model.generate_content(prompt)
    return (out.text or "").strip()


