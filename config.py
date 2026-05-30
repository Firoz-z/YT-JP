import os
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- Curriculum / level unlocking ----------
#
# The picker only draws words from levels that have unlocked. Days are
# measured from CHANNEL_START_DATE — the first day the channel published
# (so day 1 = first upload, day 121 = N4 unlocks for the first time, etc.)
#
# Adjust these if you want a faster or slower progression. Lowering a
# number unlocks a level earlier; raising it delays the unlock.
#
# Empirically a 4-month dwell at each level matches how long it takes a
# typical viewer to actually internalize the vocabulary, and it keeps the
# channel positioned for a clear audience segment at any given moment.

CHANNEL_START_DATE = date(2026, 4, 29)   # first published upload

LEVEL_UNLOCK_DAYS = {
    "N5":   0,     # day 1 — beginner foundation
    "N4":   120,   # day 121 — ~4 months in
    "N3":   240,   # day 241 — ~8 months in
    "N2":   540,   # day 541 — ~18 months in
    "N1":   900,   # day 901 — ~30 months in
}

# When a higher level is unlocked, the picker still pulls some words from
# lower levels for variety (so viewers who joined later see beginner
# content sometimes). This is the % of picks that come from the LATEST
# unlocked level; the remainder is spread across older unlocked levels.
LATEST_LEVEL_BIAS = 0.70   # 70% latest level, 30% mix of older levels

# Short (9:16 vertical)
WIDTH  = 1080
HEIGHT = 1920
FPS    = 30

# Long video (16:9 horizontal)
LONG_WIDTH  = 1920
LONG_HEIGHT = 1080

# Color palette (dark theme — slightly warmer for Japanese aesthetic)
BG_TOP     = (15, 10, 25)
BG_BOTTOM  = (35, 18, 50)
WORD_COLOR = (255, 255, 255)
KANA_COLOR        = (255, 165, 80)   # warm orange
ROMAJI_COLOR      = (255, 200, 100)  # gold
DEFINITION_COLOR  = (220, 220, 220)
EXAMPLE_COLOR     = (200, 180, 160)
BRAND_COLOR       = (180, 110, 60)

# Short scene durations (seconds)
SCENE1_DUR = 2.0
SCENE2_DUR = 2.5
SCENE3_DUR = 6.5
SCENE4_DUR = 3.0

# Long video scene durations (seconds)
LONG_SCENE1_DUR =  3.0
LONG_SCENE2_DUR =  4.0
LONG_SCENE3_DUR = 10.0
LONG_SCENE4_DUR = 10.0

# Paths
TEMP_DIR   = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# Font search order — Japanese-capable fonts first (Noto CJK on Linux,
# Hiragino on macOS), then fallbacks
FONT_PATHS = {
    "bold": [
        # Linux (GitHub Actions)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
        # macOS (local testing)
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        # Fallback
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "italic": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ],
}

# YouTube metadata
YT_TAGS = [
    "japanese", "learn japanese", "japanese vocabulary", "nihongo",
    "japanese lesson", "japanese word of the day", "jlpt",
    "japanese pronunciation", "japanese language", "shorts",
]
YT_CATEGORY_ID = "27"   # Education
YT_CHANNEL_NAME = "@EverydayJapanese"
