import os
import subprocess
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import *
from tts import generate_speech

AUDIO_PADDING = 0.8


# ---------- font loading ----------

def _load_font(style: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS.get(style, []):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------- background ----------

def _make_bg(w: int, h: int, bg_image: Image.Image | None = None) -> Image.Image:
    if bg_image is not None:
        img = bg_image.resize((w, h), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=22))
        overlay = Image.new("RGB", (w, h), (5, 5, 18))
        img = Image.blend(img, overlay, alpha=0.62)
        return img
    img  = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _make_bg_clear(w: int, h: int, bg_image: Image.Image | None = None) -> Image.Image:
    if bg_image is not None:
        img = bg_image.resize((w, h), Image.LANCZOS)
        overlay = Image.new("RGB", (w, h), (0, 0, 0))
        return Image.blend(img, overlay, alpha=0.30)
    return _make_bg(w, h)


# ---------- text helpers ----------

def _draw_centered(draw, text, font, color, y, w):
    bbox = font.getbbox(text)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    draw.text(((w - tw) // 2, y), text, font=font, fill=color)
    return y + th


def _draw_wrapped(draw, text, font, color, y, w, padding=80):
    max_w = w - padding * 2
    avg_w = max(1, font.getlength("x"))
    cpl   = max(1, int(max_w / avg_w))
    lines = textwrap.wrap(text, width=cpl)
    for line in lines:
        bbox = font.getbbox(line)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]
        draw.text(((w - tw) // 2, y), line, font=font, fill=color)
        y += th + 12
    return y


def _draw_wrapped_jp(draw, text, font, color, y, w, padding=80):
    """Wrap Japanese text by character count (no spaces)."""
    max_w = w - padding * 2
    char_w = font.getlength("あ") or 40
    cpl = max(1, int(max_w / char_w))
    chunks = [text[i:i+cpl] for i in range(0, len(text), cpl)]
    for line in chunks:
        bbox = font.getbbox(line)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]
        draw.text(((w - tw) // 2, y), line, font=font, fill=color)
        y += th + 12
    return y


def _draw_brand(draw, w, h):
    scale   = w / 1080
    f_brand = _load_font("regular", int(34 * scale))
    brand_y = h - int(110 * (h / 1920))
    bbox    = f_brand.getbbox(YT_CHANNEL_NAME)
    draw.text(((w - (bbox[2] - bbox[0])) // 2, brand_y),
              YT_CHANNEL_NAME, font=f_brand, fill=BRAND_COLOR)


# ---------- frame builders ----------

def _make_hook_frame(word_data: dict, w: int, h: int) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg(w, h)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_hook = _load_font("regular", int(52 * scale))
    f_word = _load_font("bold",    int(160 * scale))
    f_kana = _load_font("regular", int(56 * scale))

    kanji = word_data["kanji"]
    kana  = word_data.get("kana", "")

    h_top  = f_hook.getbbox("Do you know what")[3]
    h_kanji = f_word.getbbox(kanji)[3]
    h_kana  = f_kana.getbbox(kana)[3] if kana else 0
    h_bot  = f_hook.getbbox("means?")[3]
    gap    = int(24 * scale)
    total  = h_top + gap + h_kanji + (gap + h_kana if kana else 0) + gap + h_bot
    y      = (h - total) // 2

    y = _draw_centered(draw, "Do you know what", f_hook, DEFINITION_COLOR, y, w) + gap
    y = _draw_centered(draw, kanji,             f_word, WORD_COLOR,       y, w) + gap
    if kana and kana != kanji:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + gap
    _draw_centered(draw, "means?", f_hook, DEFINITION_COLOR, y, w)
    return img


def _make_word_frame(word_data: dict, w: int, h: int,
                      bg_image: Image.Image | None = None) -> Image.Image:
    """Show kanji + kana + romaji prominently."""
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji  = _load_font("bold",    int(180 * scale))
    f_kana   = _load_font("regular", int(72 * scale))
    f_romaji = _load_font("italic",  int(52 * scale))

    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")

    h_kanji = f_kanji.getbbox(kanji)[3]
    h_kana  = f_kana.getbbox(kana)[3] if kana else 0
    h_rom   = f_romaji.getbbox(romaji)[3] if romaji else 0
    gap     = int(36 * scale)
    total   = h_kanji + (gap + h_kana if kana else 0) + (gap + h_rom if romaji else 0)
    y       = (h - total) // 2

    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + gap
    if kana and kana != kanji:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + gap
    if romaji:
        _draw_centered(draw, romaji, f_romaji, ROMAJI_COLOR, y, w)
    return img


def _make_definition_frame(word_data: dict, w: int, h: int,
                            bg_image: Image.Image | None = None) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji = _load_font("bold",    int(110 * scale))
    f_kana  = _load_font("regular", int(52 * scale))
    f_label = _load_font("regular", int(40 * scale))
    f_def   = _load_font("regular", int(56 * scale))

    kanji = word_data["kanji"]
    kana  = word_data.get("kana", "")
    pos   = word_data.get("part_of_speech", "")
    defn  = word_data.get("definition", "")

    y = int(h * 0.13)
    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(20 * scale)
    if kana and kana != kanji:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + int(24 * scale)
    if pos:
        y = _draw_centered(draw, pos, f_label, ROMAJI_COLOR, y, w) + int(20 * scale)
    lx1, lx2 = w // 4, 3 * w // 4
    draw.line([(lx1, y + 8), (lx2, y + 8)], fill=(55, 55, 75), width=2)
    y += int(36 * scale)
    if defn:
        _draw_wrapped(draw, defn, f_def, DEFINITION_COLOR, y, w)
    return img


def _make_example_frame(word_data: dict, w: int, h: int,
                         bg_image: Image.Image | None = None) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji = _load_font("bold",    int(80 * scale))
    f_label = _load_font("regular", int(44 * scale))
    f_jp    = _load_font("regular", int(54 * scale))
    f_en    = _load_font("italic",  int(44 * scale))

    y = int(h * 0.10)
    y = _draw_centered(draw, word_data["kanji"], f_kanji, WORD_COLOR, y, w) + int(28 * scale)
    y = _draw_centered(draw, "Example", f_label, ROMAJI_COLOR, y, w) + int(12 * scale)
    draw.line([(w // 4, y + 8), (3 * w // 4, y + 8)], fill=(55, 55, 75), width=2)
    y += int(28 * scale) + int(20 * scale)

    example_jp = word_data.get("example_jp", "")
    example_en = word_data.get("example_en", "")
    if example_jp:
        y = _draw_wrapped_jp(draw, example_jp, f_jp, DEFINITION_COLOR, y, w) + int(28 * scale)
    if example_en:
        _draw_wrapped(draw, f'"{example_en}"', f_en, EXAMPLE_COLOR, y, w)
    return img


def _make_synonyms_frame(word_data: dict, w: int, h: int,
                          bg_image: Image.Image | None = None) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji = _load_font("bold",    int(80 * scale))
    f_label = _load_font("regular", int(44 * scale))
    f_syn   = _load_font("regular", int(64 * scale))

    y = int(h * 0.12)
    y = _draw_centered(draw, word_data["kanji"], f_kanji, WORD_COLOR, y, w) + int(32 * scale)
    y = _draw_centered(draw, "Related", f_label, ROMAJI_COLOR, y, w) + int(12 * scale)
    draw.line([(w // 4, y + 8), (3 * w // 4, y + 8)], fill=(55, 55, 75), width=2)
    y += int(28 * scale) + int(20 * scale)

    for syn in word_data.get("synonyms", [])[:4]:
        y = _draw_centered(draw, syn, f_syn, KANA_COLOR, y, w) + int(20 * scale)
    return img


def _make_tip_frame(word_data: dict, tip: str, w: int, h: int,
                     bg_image: Image.Image | None = None) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg_clear(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji = _load_font("bold",    int(80 * scale))
    f_label = _load_font("regular", int(44 * scale))
    f_tip   = _load_font("italic",  int(46 * scale))

    y = int(h * 0.12)
    y = _draw_centered(draw, word_data["kanji"], f_kanji, WORD_COLOR, y, w) + int(32 * scale)
    y = _draw_centered(draw, "Memory Tip", f_label, ROMAJI_COLOR, y, w) + int(12 * scale)
    draw.line([(w // 4, y + 8), (3 * w // 4, y + 8)], fill=(55, 55, 75), width=2)
    y += int(28 * scale) + int(20 * scale)
    _draw_wrapped(draw, tip, f_tip, DEFINITION_COLOR, y, w)
    return img


# ---------- audio ----------

def get_audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _tts_with_retry(text: str, path: str, lang: str = "jp",
                    rate: str = "+0%", retries: int = 4) -> None:
    for attempt in range(retries):
        try:
            generate_speech(text, path, rate=rate, lang=lang)
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))


def _concat_audio_pair(jp_path: str, en_path: str, out: str,
                        gap_sec: float = 0.4) -> None:
    """Concat JP audio + small gap + EN audio."""
    silence = out + ".silence.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(gap_sec),
        "-q:a", "9", "-acodec", "libmp3lame",
        silence,
    ], check=True, capture_output=True)

    inputs = ["-i", jp_path, "-i", silence, "-i", en_path]
    fc = ("[0:a]aformat=sample_rates=44100:channel_layouts=mono[a0];"
          "[1:a]aformat=sample_rates=44100:channel_layouts=mono[a1];"
          "[2:a]aformat=sample_rates=44100:channel_layouts=mono[a2];"
          "[a0][a1][a2]concat=n=3:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-y"] + inputs +
                   ["-filter_complex", fc, "-map", "[out]", out],
                   check=True, capture_output=True)
    if os.path.exists(silence):
        os.remove(silence)


def _render_one_scene(img: Image.Image, audio: str, duration: float,
                      out: str, w: int, h: int) -> None:
    png = out + ".png"
    img.save(png)
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", png,
        "-i", audio,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
        "-vf", f"scale={w}:{h},fps={FPS}",
        "-t", str(duration),
        out,
    ], check=True, capture_output=True)
    os.remove(png)


def _concat_clips(clips: list, output: str) -> None:
    lst = output + ".list.txt"
    with open(lst, "w") as f:
        for p in clips:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-c", "copy", "-movflags", "+faststart",
        output,
    ], check=True, capture_output=True)
    os.remove(lst)


# ---------- public API ----------

def create_short(word_data: dict, output_path: str,
                 word_images: list = None) -> None:
    os.makedirs(TEMP_DIR, exist_ok=True)

    kanji   = word_data["kanji"]
    kana    = word_data.get("kana", "")
    romaji  = word_data.get("romaji", "")
    pos     = word_data.get("part_of_speech", "")
    defn    = word_data["definition"]
    syns    = word_data.get("synonyms", [])
    tip     = word_data.get("memory_tip", "")
    images  = word_images or []

    def img(i):
        return images[i] if i < len(images) else (images[-1] if images else None)

    img_slot = 0

    # Scene 1: hook (English) — "Do you know what 勉強 means?"
    specs = [{
        "frame": _make_hook_frame(word_data, WIDTH, HEIGHT),
        "tts":   f"Do you know what {kanji} means?",
        "rate":  "+30%",
        "lang":  "en",
    }]

    # Scene 2: pronunciation — say the word in Japanese twice
    specs.append({
        "frame": _make_word_frame(word_data, WIDTH, HEIGHT),
        "tts":   f"{kanji}。{kanji}。",
        "rate":  "-15%",
        "lang":  "jp",
    })

    # Scene 3: definition — read English definition
    specs.append({
        "frame": _make_definition_frame(word_data, WIDTH, HEIGHT, bg_image=img(img_slot)),
        "tts":   (f"{pos}. " if pos else "") + defn + ".",
        "rate":  "+10%",
        "lang":  "en",
    })
    img_slot += 1

    # Scene 4: example sentence (Japanese audio + English translation)
    example_jp = word_data.get("example_jp", "")
    example_en = word_data.get("example_en", "")
    if example_jp:
        specs.append({
            "frame":     _make_example_frame(word_data, WIDTH, HEIGHT, img(img_slot)),
            "example":   True,
            "jp_text":   example_jp,
            "en_text":   f"In English: {example_en}" if example_en else "",
        })
        img_slot += 1

    # Scene 5: synonyms / related
    if syns:
        specs.append({
            "frame": _make_synonyms_frame(word_data, WIDTH, HEIGHT, img(img_slot)),
            "tts":   "Related words: " + ", ".join(syns[:3]) + ".",
            "rate":  "-10%",
            "lang":  "jp",
        })
        img_slot += 1

    # Scene 6: memory tip (English)
    if tip:
        specs.append({
            "frame": _make_tip_frame(word_data, tip, WIDTH, HEIGHT, img(img_slot)),
            "tts":   f"Memory tip. {tip}",
            "rate":  "+15%",
            "lang":  "en",
        })

    # Scene 7: recap — final pronunciation
    specs.append({
        "frame": _make_word_frame(word_data, WIDTH, HEIGHT),
        "tts":   f"{kanji}。",
        "rate":  "+0%",
        "lang":  "jp",
    })

    # Render each scene
    clip_paths = []
    for i, spec in enumerate(specs):
        if spec.get("example"):
            jp_path = os.path.join(TEMP_DIR, f"short_a_{i}_jp.mp3")
            en_path = os.path.join(TEMP_DIR, f"short_a_{i}_en.mp3")
            apath   = os.path.join(TEMP_DIR, f"short_a_{i}.mp3")
            _tts_with_retry(spec["jp_text"], jp_path, lang="jp", rate="-10%")
            if spec.get("en_text"):
                _tts_with_retry(spec["en_text"], en_path, lang="en", rate="+10%")
                _concat_audio_pair(jp_path, en_path, apath)
            else:
                os.rename(jp_path, apath)
            for p in (jp_path, en_path):
                if os.path.exists(p):
                    os.remove(p)
        else:
            apath = os.path.join(TEMP_DIR, f"short_a_{i}.mp3")
            _tts_with_retry(spec["tts"], apath,
                            lang=spec.get("lang", "en"),
                            rate=spec.get("rate", "+0%"))

        dur  = get_audio_duration(apath) + AUDIO_PADDING
        clip = os.path.join(TEMP_DIR, f"short_clip_{i}.mp4")
        _render_one_scene(spec["frame"], apath, dur, clip, WIDTH, HEIGHT)
        clip_paths.append(clip)

        if os.path.exists(apath):
            os.remove(apath)

    _concat_clips(clip_paths, output_path)

    for p in clip_paths:
        if os.path.exists(p):
            os.remove(p)
