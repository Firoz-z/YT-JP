"""
Local test runner — generates a video for a single word WITHOUT uploading.

Usage:
  python test_local.py             # uses default test word
  python test_local.py 勉強         # specific word
  python test_local.py 食べる       # any word from words.txt or your own

Prerequisites:
  - ffmpeg installed (brew install ffmpeg on macOS)
  - pip install -r requirements.txt
  - Optional: GROQ_API_KEY env var for richer example sentences
  - Optional: PEXELS_API_KEY env var for background images

The output MP4 is saved to ./output/ — open it to preview.
"""
import os
import sys
from datetime import date

from word_fetcher import fetch_word_data
from video_builder import create_short, create_thumbnail
from image_fetcher import fetch_word_images
from llm import enrich_word_data
from config import TEMP_DIR, OUTPUT_DIR


def main():
    word = sys.argv[1] if len(sys.argv) > 1 else "勉強"

    os.makedirs(TEMP_DIR,   exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n=== Testing pipeline for: {word} ===\n")

    print("[1/4] Fetching from Jisho...")
    word_data = fetch_word_data(word)
    if not word_data:
        print(f"  ERROR: no Jisho data for '{word}'")
        return 1
    print(f"  kanji      : {word_data['kanji']}")
    print(f"  kana       : {word_data['kana']}")
    print(f"  romaji     : {word_data['romaji']}")
    print(f"  definition : {word_data['definition']}")
    print(f"  pos        : {word_data['part_of_speech']}")
    print(f"  jlpt       : {word_data['jlpt_level']}")

    print("\n[2/4] Enriching via Groq LLM (skipped if no GROQ_API_KEY)...")
    word_data = enrich_word_data(word, word_data)

    print("\n[3/4] Fetching background images from Pexels...")
    word_images = fetch_word_images(word_data, count=5)
    print(f"  images     : {len(word_images)} fetched")

    print("\n[4/4] Building video (TTS + frames + ffmpeg) and thumbnail...")
    today = date.today().isoformat()
    safe_name = word_data["romaji"].replace(" ", "_") or "test"
    output_path    = os.path.join(OUTPUT_DIR, f"TEST_{safe_name}_{today}.mp4")
    thumbnail_path = os.path.join(OUTPUT_DIR, f"TEST_{safe_name}_{today}_thumb.jpg")
    create_short(word_data, output_path, word_images=word_images)
    create_thumbnail(word_data, thumbnail_path, word_images=word_images)

    print(f"\n=== DONE ===")
    print(f"Video    : {output_path}")
    print(f"Thumbnail: {thumbnail_path}")
    print(f"Open video    : open '{output_path}'")
    print(f"Open thumbnail: open '{thumbnail_path}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
