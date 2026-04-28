"""
llm.py — Groq LLM calls for Japanese example sentence, memory tip.
Falls back to Jisho data if Groq is unavailable or key is missing.
"""
import os
import json
from groq import Groq

_MODEL = "llama-3.3-70b-versatile"

_PROMPT = """You are a Japanese vocabulary assistant for a YouTube channel teaching Japanese to English speakers.

Given the Japanese word "{kanji}" (reading: "{kana}", romaji: "{romaji}", meaning: "{meaning}"),
return a JSON object with EXACTLY these fields:

{{
  "definition": "Clean, one-line English definition. Pick the most common modern usage. Max 12 words.",
  "example_jp": "ONE natural Japanese example sentence using the word. Use simple grammar suitable for beginners. Include the word naturally.",
  "example_kana": "The same example sentence written entirely in hiragana (no kanji).",
  "example_en": "Natural English translation of the example sentence.",
  "memory_tip": "ONE creative tip in English to help remember this word — use sound associations, mnemonics, or imagery. Start with 'Think of' or 'Remember'. Max 22 words.",
  "synonyms": ["jp_synonym1", "jp_synonym2", "jp_synonym3"]
}}

Rules:
- Return ONLY the JSON object. No explanation, no markdown.
- Example must be beginner-friendly Japanese.
- example_kana = example_jp with all kanji replaced by hiragana readings.
- Memory tip must be in English (the audience is English speakers learning Japanese).
- Synonyms must be Japanese words (kanji or kana).

Word: {kanji} ({kana})"""


def enrich_word_data(word: str, fallback: dict) -> dict:
    """
    Call Groq to get example sentence (JP+EN), memory tip, refined definition.
    If Groq fails or key is missing, returns fallback unchanged.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("  [llm] GROQ_API_KEY not set — using Jisho data only")
        return fallback

    try:
        client   = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model    = _MODEL,
            messages = [{"role": "user", "content": _PROMPT.format(
                kanji   = fallback["kanji"],
                kana    = fallback["kana"],
                romaji  = fallback["romaji"],
                meaning = fallback["definition"],
            )}],
            temperature      = 0.7,
            max_tokens       = 500,
            response_format  = {"type": "json_object"},
        )
        raw  = response.choices[0].message.content.strip()
        data = json.loads(raw)

        for field in ("definition", "example_jp", "example_en", "memory_tip"):
            if not data.get(field):
                raise ValueError(f"missing field: {field}")

        print(f"  [llm] definition  : {data['definition']}")
        print(f"  [llm] example_jp  : {data['example_jp']}")
        print(f"  [llm] example_en  : {data['example_en']}")
        print(f"  [llm] memory_tip  : {data['memory_tip']}")

        return {
            **fallback,
            "definition":   data["definition"],
            "example_jp":   data["example_jp"],
            "example_kana": data.get("example_kana", ""),
            "example_en":   data["example_en"],
            "memory_tip":   data["memory_tip"],
            "synonyms":     data.get("synonyms", fallback.get("synonyms", []))[:5],
        }

    except Exception as e:
        print(f"  [llm] error ({e}) — falling back to Jisho data")
        return fallback
