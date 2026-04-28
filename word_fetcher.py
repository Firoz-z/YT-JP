"""Fetch Japanese word data from Jisho API + romaji via pykakasi."""
import requests
from pykakasi import kakasi

_API = "https://jisho.org/api/v1/search/words"

_kks = kakasi()


def _to_romaji(text: str) -> str:
    """Convert Japanese text to Hepburn romaji."""
    if not text:
        return ""
    parts = _kks.convert(text)
    return " ".join(p["hepburn"] for p in parts if p["hepburn"]).strip()


def _to_hiragana(text: str) -> str:
    """Convert kanji/katakana to hiragana."""
    if not text:
        return ""
    parts = _kks.convert(text)
    return "".join(p["hira"] for p in parts).strip()


def fetch_word_data(word: str) -> dict | None:
    """Return structured word data from the Jisho API."""
    try:
        resp = requests.get(_API, params={"keyword": word}, timeout=10)
        if resp.status_code != 200:
            return None
        results = resp.json().get("data", [])
        if not results:
            return None
    except Exception as e:
        print(f"  [word_fetcher] error: {e}")
        return None

    # Pick the most common entry (usually first)
    entry = results[0]
    japanese = entry.get("japanese", [{}])[0]
    kanji = japanese.get("word") or japanese.get("reading", word)
    kana  = japanese.get("reading") or _to_hiragana(kanji)
    romaji = _to_romaji(kana or kanji)

    # Senses → first English definition + part of speech
    senses = entry.get("senses", [])
    definition = ""
    part_of_speech = ""
    example_en = ""
    if senses:
        first = senses[0]
        eng = first.get("english_definitions", [])
        definition = "; ".join(eng[:3]) if eng else ""
        pos_list = first.get("parts_of_speech", [])
        part_of_speech = pos_list[0] if pos_list else ""

    if not definition:
        return None

    # JLPT level
    jlpt = entry.get("jlpt", [])
    jlpt_level = jlpt[0].replace("jlpt-", "").upper() if jlpt else ""

    # Common synonyms — gather alternative kanji/readings as variants
    synonyms = []
    for jp in entry.get("japanese", [])[1:6]:
        alt = jp.get("word") or jp.get("reading")
        if alt and alt != kanji:
            synonyms.append(alt)

    return {
        "word":           kanji,
        "kanji":          kanji,
        "kana":           kana,
        "romaji":         romaji,
        "part_of_speech": part_of_speech,
        "definition":     definition,
        "example_jp":     "",
        "example_en":     example_en,
        "synonyms":       synonyms[:5],
        "jlpt_level":     jlpt_level,
        "audio_url":      None,    # Jisho doesn't provide audio
    }


def download_audio(url: str, dest: str) -> bool:
    """Stub — Jisho has no audio. Pronunciation comes from TTS."""
    return False
