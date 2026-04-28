import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

# Font search order — Japanese-capable fonts first (Noto CJK), then fallbacks
FONT_PATHS = {
    "bold": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "italic": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
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
YT_CHANNEL_NAME = "@DailyNihongo"
