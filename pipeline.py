"""Main pipeline — fetches today's Japanese word, builds video, uploads it."""
import os
import sys
import random
from datetime import date, datetime, timezone

from word_fetcher import fetch_word_data
from video_builder import create_short, create_long_form
from image_fetcher import fetch_word_images
from llm import enrich_word_data
from uploader import upload_short_only, upload_long_form
from config import (TEMP_DIR, OUTPUT_DIR,
                    CHANNEL_START_DATE, LEVEL_UNLOCK_DAYS, LATEST_LEVEL_BIAS)

VIDEOS_PER_DAY = 4

UPLOAD_LOG = "uploads.md"
UPLOAD_LOG_HEADER = (
    "# Upload History\n\n"
    "Every published video pair (Short + Long), in chronological order.\n"
    "Appended automatically by the pipeline after each successful upload.\n\n"
    "| Date | Slot | Kanji | Kana | Romaji | JLPT | Meaning | Short | Long |\n"
    "|------|------|-------|------|--------|------|---------|-------|------|\n"
)


def _log_upload(word_data: dict, short_id: str, slot: int,
                long_id: str = None) -> None:
    """Append a row to uploads.md — one row per word, with Short and Long
    video links. The GitHub Actions workflow commits this file back to the
    repo after each successful run."""
    path = os.path.join(os.path.dirname(__file__), UPLOAD_LOG)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(UPLOAD_LOG_HEADER)
    today  = date.today().isoformat()
    kanji  = word_data.get("kanji", "")
    kana   = word_data.get("kana", "") or "—"
    romaji = word_data.get("romaji", "") or "—"
    jlpt   = word_data.get("jlpt_level", "") or "—"
    defn   = (word_data.get("definition", "") or "").replace("|", "\\|")
    short_cell = f"[short](https://youtube.com/shorts/{short_id})"
    long_cell  = (f"[long](https://youtube.com/watch?v={long_id})"
                  if long_id else "—")
    row = (f"| {today} | {slot} | {kanji} | {kana} | {romaji} | "
           f"{jlpt} | {defn} | {short_cell} | {long_cell} |\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write(row)
    print(f"  history → {UPLOAD_LOG}")


def _already_uploaded() -> set:
    """Return the set of kanji headwords already published, parsed from
    uploads.md. Used to skip duplicates when two runs happen in the same
    slot window (manual workflow_dispatch + the scheduled cron, or a
    retried run, etc.)."""
    path = os.path.join(os.path.dirname(__file__), UPLOAD_LOG)
    if not os.path.exists(path):
        return set()
    used = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            # Markdown table row: "| 2026-04-29 | 2 | 嫌い | ... |"
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            date_cell = parts[1]
            kanji_cell = parts[3]
            if not (len(date_cell) >= 4 and date_cell[:4].isdigit()):
                continue   # skip header / separator rows
            if kanji_cell:
                used.add(kanji_cell)
    return used


_LEVEL_HEADER_PREFIX = "# ===== LEVEL:"


def _load_words_by_level() -> dict:
    """Parse words.txt into {level_name: [words]}.

    A line like "# ===== LEVEL: N5 =====" starts a new section. Comment
    lines starting with "# ---" or "#" between section headers are
    ignored (they're sub-theme labels inside a level). Returns a dict
    in the order levels appear in the file.
    """
    levels = {}
    current = None
    with open("words.txt", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(_LEVEL_HEADER_PREFIX):
                # "# ===== LEVEL: N5 =====" → "N5"
                name = line[len(_LEVEL_HEADER_PREFIX):].strip()
                name = name.split()[0].strip()   # drop trailing "====="
                name = name.rstrip("=").strip()
                current = name
                levels.setdefault(current, [])
                continue
            if line.startswith("#"):
                continue
            if current is None:
                # Pre-section words (legacy / pre-level) — bucket as "N5"
                current = "N5"
                levels.setdefault(current, [])
            levels[current].append(line)
    return levels


def _unlocked_levels(today: date) -> list:
    """Return the list of unlocked level names in order (oldest first)."""
    days_since_start = (today - CHANNEL_START_DATE).days
    unlocked = [
        level for level, unlock_day in LEVEL_UNLOCK_DAYS.items()
        if days_since_start >= unlock_day
    ]
    return unlocked or ["N5"]   # always at least N5 unlocked


def _get_word(slot: int) -> str:
    """Pick a Japanese word for this slot.

    Selection logic:
      1. Read words.txt into per-level buckets.
      2. Compute which levels are unlocked based on today's date.
      3. The newest unlocked level gets LATEST_LEVEL_BIAS of slots; older
         levels share the rest evenly. Which pool this slot uses is
         determined deterministically by (date + slot).
      4. Within the chosen pool, deterministic shuffle by (date + slot),
         then walk forward past anything already in uploads.md so we
         never publish a duplicate.
    """
    levels         = _load_words_by_level()
    unlocked       = _unlocked_levels(date.today())
    used           = _already_uploaded()

    # Decide which level pool this slot draws from
    days        = (date.today() - CHANNEL_START_DATE).days
    global_slot = days * VIDEOS_PER_DAY + slot
    # Deterministic float in [0, 1) for this slot
    rng_pool    = random.Random(f"pool-{global_slot}").random()

    latest = unlocked[-1]
    if len(unlocked) == 1 or rng_pool < LATEST_LEVEL_BIAS:
        chosen_level = latest
    else:
        # Spread the remaining (1 - bias) across older levels
        older = unlocked[:-1]
        idx   = int((rng_pool - LATEST_LEVEL_BIAS) /
                    ((1 - LATEST_LEVEL_BIAS) / len(older)))
        idx   = min(idx, len(older) - 1)
        chosen_level = older[idx]

    pool = levels.get(chosen_level, [])
    if not pool:
        # Defensive: chosen level is empty (config drift) — fall back to latest
        pool = levels.get(latest, [])
    if not pool:
        # Last resort: any unlocked level with words
        for lvl in reversed(unlocked):
            if levels.get(lvl):
                pool = levels[lvl]
                chosen_level = lvl
                break

    if not pool:
        raise RuntimeError("No words available in any unlocked level — "
                           "check words.txt has level sections populated.")

    cycle    = global_slot // len(pool)
    position = global_slot % len(pool)

    print(f"  [picker] level={chosen_level}  pool={len(pool)}  "
          f"position={position}  cycle={cycle}  unlocked={unlocked}")

    # Walk forward past any already-uploaded words
    for offset in range(len(pool) * 4):
        c = cycle + (position + offset) // len(pool)
        i = (position + offset) % len(pool)
        rng = random.Random(f"{chosen_level}-{c}")
        shuffled = pool[:]
        rng.shuffle(shuffled)
        candidate = shuffled[i]
        if candidate not in used:
            return candidate

    # Every word in the pool has been used — fall back to the
    # deterministic pick (will get caught by the unique-by-slot upload
    # constraint or just publish a known repeat in extreme edge cases).
    rng = random.Random(f"{chosen_level}-{cycle}")
    shuffled = pool[:]
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
    safe_name = word_data["romaji"].replace(" ", "_") or "word"

    # 4a — build Short (1080×1920 vertical)
    short_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{today}_s{slot}_short.mp4")
    create_short(word_data, short_path, word_images=word_images)

    # 4b — build Long-form (1920×1080 landscape) — same scenes, different hook
    long_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{today}_s{slot}_long.mp4")
    create_long_form(word_data, long_path, word_images=word_images)

    # 5a — upload Short
    short_id = upload_short_only(short_path, word_data)
    print(f"  short  → https://youtube.com/shorts/{short_id}")

    # 5b — upload Long-form (failure here is logged but does NOT abort the run;
    #       the Short is already live and that's what matters most)
    long_id = None
    try:
        long_id = upload_long_form(long_path, word_data)
        print(f"  long   → https://youtube.com/watch?v={long_id}")
    except Exception as exc:
        print(f"  [warn] long-form upload failed — {exc}")

    # 6 — append to upload history (committed back by the workflow)
    _log_upload(word_data, short_id, slot, long_id=long_id)


def _slot_from_hour() -> int:
    """Map current UTC hour to a slot (0-3) matching the cron schedule.

    Cron fires at 08:00, 14:00, 19:00, 23:00 UTC.
    Each branch covers the window up to (but not including) the next
    cron, so a workflow that runs slightly late still picks the right
    slot it was meant for.
    """
    hour = datetime.now(timezone.utc).hour
    if hour < 12:   return 0   # 8 AM UTC run
    elif hour < 17: return 1   # 2 PM UTC run
    elif hour < 22: return 2   # 7 PM UTC run
    else:           return 3   # 11 PM UTC run


if __name__ == "__main__":
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else _slot_from_hour()
    run(slot)
