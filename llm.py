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
  "memory_tip": "A linkword mnemonic — see RULES below.",
  "synonyms": ["jp_synonym1", "jp_synonym2", "jp_synonym3"]
}}

MEMORY TIP RULES (very important — this is the highest-value field):

The memory_tip MUST be a linkword mnemonic that connects the *sound* of the
Japanese word to its *meaning* through a vivid English image. The viewer should
hear the pronunciation and instantly recall the image.

Required structure:
  "{romaji} sounds like '<English sound-alike>' — <vivid image that uses both
   the sound-alike AND the word's meaning>."

The English sound-alike must:
  - Break the Japanese romaji into 1-3 English words/syllables that sound similar
  - Use real English words or word fragments (not gibberish)
  - Form a phrase the viewer can hear in their head

The image must:
  - Use BOTH the sound-alike AND the word's meaning
  - Be specific and visual (a scene, not an abstract idea)
  - Bonus if funny, weird, or exaggerated — memorable beats elegant

Examples to model your output on:
  - 猫 (neko, cat): "NEKO sounds like 'neck-O' — picture a cat wearing an O-shaped collar around its neck."
  - 水 (mizu, water): "MIZU sounds like 'me-zoo' — imagine ME at the ZOO drinking water from a fountain."
  - 食べる (taberu, to eat): "TABERU sounds like 'table-roo' — you're eating at a TABLE when a kangaROO joins you."
  - 桜 (sakura, cherry blossom): "SAKURA sounds like 'sack-of-rah' — a SACK filled with cherry blossoms, people cheering 'RAH!'"
  - 勉強 (benkyou, study): "BENKYOU sounds like 'Ben-chew' — BEN CHEWS on his pencil while studying hard."
  - 嫌い (kirai, hated): "KIRAI sounds like 'key-rye' — you HATE finding a KEY stuck in a piece of RYE bread."

Special cases:
  - Loan words (寿司 sushi, 忍者 ninja, アイスクリーム ice cream) — skip the
    sound-alike since the Japanese already IS the English word. Instead give
    a 1-line fact or cultural anchor (e.g. "Sushi literally means 'sour-tasting'
    — referring to the vinegared rice, not the fish.")
  - Words with no good English homophone — fall back to imagery or etymology.

Length: under 28 words. One sentence preferred, two max.

Other rules:
- Return ONLY the JSON object. No explanation, no markdown.
- Example must be beginner-friendly Japanese.
- example_kana = example_jp with all kanji replaced by hiragana readings.
- Memory tip must be in English (the audience is English speakers learning Japanese).
- Synonyms must be Japanese words (kanji or kana).

Word: {kanji} ({kana}), romaji: {romaji}"""


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
