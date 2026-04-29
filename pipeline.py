"""Main pipeline — fetches today's Japanese word, builds video, uploads it."""
import os
import sys
import random
from datetime import date, datetime, timezone

from word_fetcher import fetch_word_data
from video_builder import create_short
from image_fetcher import fetch_word_images
from llm import enrich_word_data
from uploader import upload_short_only
from config import TEMP_DIR, OUTPUT_DIR

VIDEOS_PER_DAY = 3

UPLOAD_LOG = "uploads.md"
UPLOAD_LOG_HEADER = (
    "# Upload History\n\n"
    "Every published Short, in chronological order. Appended automatically\n"
    "by the pipeline after each successful upload.\n\n"
    "| Date | Slot | Kanji | Kana | Romaji | JLPT | Meaning | Video |\n"
    "|------|------|-------|------|--------|------|---------|-------|\n"
)


def _log_upload(word_data: dict, video_id: str, slot: int) -> None:
    """Append a row to uploads.md so we have a permanent history of what
    was published when. The GitHub Actions workflow commits this file
    back to the repo after the pipeline succeeds."""
    path = os.path.join(os.path.dirname(__file__), UPLOAD_LOG)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(UPLOAD_LOG_HEADER)
    today = date.today().isoformat()
    kanji  = word_data.get("kanji", "")
    kana   = word_data.get("kana", "") or "—"
    romaji = word_data.get("romaji", "") or "—"
    jlpt   = word_data.get("jlpt_level", "") or "—"
    defn   = (word_data.get("definition", "") or "")
    # Markdown table cells can't contain raw pipes — escape them
    defn   = defn.replace("|", "\\|")
    url    = f"https://youtube.com/shorts/{video_id}"
    row = (f"| {today} | {slot} | {kanji} | {kana} | {romaji} | "
           f"{jlpt} | {defn} | [link]({url}) |\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write(row)
    print(f"  history → {UPLOAD_LOG}")


def _get_word(slot: int) -> str:
    """Pick a unique Japanese word for today's slot."""
    with open("words.txt") as f:
        words = [
            w.strip()
            for w in f
            if w.strip() and not w.startswith("#")
        ]
    days        = (date.today() - date(2024, 1, 1)).days
    global_slot = days * VIDEOS_PER_DAY + slot
    cycle       = global_slot // len(words)
    position    = global_slot % len(words)

    rng = random.Random(cycle)
    shuffled = words[:]
    rng.shuffle(shuffled)
    return shuffled[position]


def run(slot: int = 0) -> None:
    os.makedirs(TEMP_DIR,   exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    word = _get_word(slot)
    print(f"\n[slot {slot}] word: {word}")

    # 1 — fetch from Jisho (kanji, kana, romaji, definition)
    word_data = fetch_word_data(word)
    if not word_data:
        print(f"  skipping — no Jisho data for '{word}'")
        return

    # 2 — enrich with Groq (example sentence in JP+EN, memory tip)
    word_data = enrich_word_data(word, word_data)

    print(f"  kanji      : {word_data['kanji']}")
    print(f"  kana       : {word_data['kana']}")
    print(f"  romaji     : {word_data['romaji']}")
    print(f"  definition : {word_data['definition']}")

    # 3 — background images via Pexels (English keywords from definition)
    word_images = fetch_word_images(word_data, count=5)
    print(f"  images     : {len(word_images)} fetched")

    today = date.today().isoformat()

    # 4 — build Short
    safe_name = word_data["romaji"].replace(" ", "_") or "word"
    short_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{today}_s{slot}_short.mp4")
    create_short(word_data, short_path, word_images=word_images)

    # 5 — upload
    short_id = upload_short_only(short_path, word_data)
    print(f"  short  → https://youtube.com/shorts/{short_id}")

    # 6 — append to upload history (committed back by the workflow)
    _log_upload(word_data, short_id, slot)


def _slot_from_hour() -> int:
    """Map current UTC hour to a slot (0-2) matching the cron schedule."""
    hour = datetime.now(timezone.utc).hour
    if hour < 12:   return 0
    elif hour < 17: return 1
    else:           return 2


if __name__ == "__main__":
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else _slot_from_hour()
    run(slot)
