import os
import subprocess
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pykakasi import kakasi
from config import *
from tts import generate_speech

AUDIO_PADDING = 0.15

# Shared kana converter for displaying readings below kanji
_kks_render = kakasi()


def _kana_of(text: str) -> str:
    """Return the hiragana reading of any Japanese text. Returns '' for
    text that is already pure hiragana/katakana (so we don't render a
    duplicate line)."""
    if not text:
        return ""
    parts = _kks_render.convert(text)
    hira = "".join(p["hira"] for p in parts).strip()
    # Skip if input has no kanji (already pure kana) — hira will equal text
    if hira == text:
        return ""
    return hira


def _romaji_of(text: str) -> str:
    """Return the Hepburn romaji of any Japanese text."""
    if not text:
        return ""
    parts = _kks_render.convert(text)
    return " ".join(p["hepburn"] for p in parts if p["hepburn"]).strip()


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

    f_kanji     = _load_font("bold",    int(80 * scale))
    f_kana_top  = _load_font("regular", int(40 * scale))
    f_label     = _load_font("regular", int(44 * scale))
    f_jp        = _load_font("regular", int(54 * scale))
    f_jp_kana   = _load_font("regular", int(40 * scale))
    f_en        = _load_font("italic",  int(44 * scale))

    kanji = word_data["kanji"]
    kana_top = _kana_of(kanji)

    y = int(h * 0.10)
    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(8 * scale)
    if kana_top:
        y = _draw_centered(draw, kana_top, f_kana_top, KANA_COLOR, y, w) + int(20 * scale)
    else:
        y += int(20 * scale)
    y = _draw_centered(draw, "Example", f_label, ROMAJI_COLOR, y, w) + int(12 * scale)
    draw.line([(w // 4, y + 8), (3 * w // 4, y + 8)], fill=(55, 55, 75), width=2)
    y += int(28 * scale) + int(20 * scale)

    example_jp   = word_data.get("example_jp", "")
    example_kana = word_data.get("example_kana", "")
    example_en   = word_data.get("example_en", "")

    if example_jp:
        y = _draw_wrapped_jp(draw, example_jp, f_jp, DEFINITION_COLOR, y, w) + int(12 * scale)
        # All-hiragana reading of the example sentence (from LLM, falls back
        # to pykakasi if not provided)
        if not example_kana:
            example_kana = _kana_of(example_jp)
        if example_kana and example_kana != example_jp:
            y = _draw_wrapped_jp(draw, example_kana, f_jp_kana, KANA_COLOR, y, w) + int(24 * scale)
        else:
            y += int(20 * scale)
    if example_en:
        _draw_wrapped(draw, f'"{example_en}"', f_en, EXAMPLE_COLOR, y, w)
    return img


def _make_synonyms_frame(word_data: dict, w: int, h: int,
                          bg_image: Image.Image | None = None) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji      = _load_font("bold",    int(80 * scale))
    f_kana_top   = _load_font("regular", int(40 * scale))
    f_label      = _load_font("regular", int(44 * scale))
    f_syn        = _load_font("regular", int(56 * scale))
    f_syn_kana   = _load_font("regular", int(34 * scale))
    f_syn_romaji = _load_font("italic",  int(30 * scale))

    kanji = word_data["kanji"]
    kana_top = _kana_of(kanji)

    y = int(h * 0.10)
    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(6 * scale)
    if kana_top:
        y = _draw_centered(draw, kana_top, f_kana_top, KANA_COLOR, y, w) + int(20 * scale)
    else:
        y += int(20 * scale)
    y = _draw_centered(draw, "Related", f_label, ROMAJI_COLOR, y, w) + int(10 * scale)
    draw.line([(w // 4, y + 8), (3 * w // 4, y + 8)], fill=(55, 55, 75), width=2)
    y += int(28 * scale) + int(12 * scale)

    # Show top 3 synonyms with their hiragana reading + romaji underneath each
    for syn in word_data.get("synonyms", [])[:3]:
        y = _draw_centered(draw, syn, f_syn, WORD_COLOR, y, w) + int(2 * scale)
        syn_kana = _kana_of(syn)
        if syn_kana:
            y = _draw_centered(draw, syn_kana, f_syn_kana, KANA_COLOR, y, w) + int(2 * scale)
        syn_romaji = _romaji_of(syn)
        if syn_romaji:
            y = _draw_centered(draw, syn_romaji, f_syn_romaji, ROMAJI_COLOR, y, w) + int(20 * scale)
        else:
            y += int(20 * scale)
    return img


def _make_tip_frame(word_data: dict, tip: str, w: int, h: int,
                     bg_image: Image.Image | None = None) -> Image.Image:
    scale  = w / 1080
    img    = _make_bg_clear(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji    = _load_font("bold",    int(80 * scale))
    f_kana_top = _load_font("regular", int(40 * scale))
    f_label    = _load_font("regular", int(44 * scale))
    f_tip      = _load_font("italic",  int(46 * scale))

    kanji = word_data["kanji"]
    kana_top = _kana_of(kanji)

    y = int(h * 0.12)
    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(8 * scale)
    if kana_top:
        y = _draw_centered(draw, kana_top, f_kana_top, KANA_COLOR, y, w) + int(24 * scale)
    else:
        y += int(24 * scale)
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


def _trim_silence(in_path: str, out_path: str) -> None:
    """Trim leading + trailing silence from a TTS audio file.

    edge-tts pads the start and end of every MP3 with ~200-400ms of
    silence. Concatenating those padded clips creates audible gaps
    even when our explicit between-segment gap is near zero. Stripping
    the silence first lets us control pacing precisely.
    """
    subprocess.run([
        "ffmpeg", "-y", "-i", in_path,
        "-af",
        # First filter: trim leading silence
        # Second filter: reverse, trim leading (= original trailing), reverse back
        "silenceremove=start_periods=1:start_silence=0:start_threshold=-45dB,"
        "areverse,silenceremove=start_periods=1:start_silence=0:start_threshold=-45dB,areverse",
        "-q:a", "4", "-acodec", "libmp3lame",
        out_path,
    ], check=True, capture_output=True)


def _multi_tts(segments: list, out: str, default_gap: float = 0.0) -> None:
    """Generate TTS for each segment, trim TTS-added silence, and
    concatenate them.

    segments = [{"text": str, "lang": "en"|"jp", "rate": "+0%",
                 "pause_after": 0.0 (optional)}, ...]

    `default_gap` is used between segments that don't specify
    `pause_after`. With silence-trimming on each segment, a default of
    0 still leaves a natural micro-gap from the TTS engine itself, so
    bilingual sentences like "Do you know what 勉強 means?" flow as one
    continuous utterance.
    """
    audio_paths = []
    for i, seg in enumerate(segments):
        raw  = out + f".seg{i}.raw.mp3"
        path = out + f".seg{i}.mp3"
        _tts_with_retry(seg["text"], raw,
                        lang=seg.get("lang", "en"),
                        rate=seg.get("rate", "+0%"))
        try:
            _trim_silence(raw, path)
            os.remove(raw)
        except subprocess.CalledProcessError:
            # Trim failed (rare) — fall back to untrimmed
            os.replace(raw, path)
        audio_paths.append(path)

    if len(audio_paths) == 1:
        os.replace(audio_paths[0], out)
        return

    # Build per-gap silence files only when a real (positive) gap is
    # requested. Skipping zero-duration silence avoids ffmpeg failing to
    # produce an empty mp3 (lavfi anullsrc + -t 0 returns no output).
    silences = {}
    for i in range(len(segments) - 1):
        gap = segments[i].get("pause_after", default_gap)
        if gap <= 0.001:
            continue
        sil = out + f".sil{i}.mp3"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{gap:.3f}", "-q:a", "9", "-acodec", "libmp3lame",
            sil,
        ], check=True, capture_output=True)
        silences[i] = sil

    interleaved = []
    for i, audio in enumerate(audio_paths):
        interleaved.append(audio)
        if i in silences:
            interleaved.append(silences[i])

    cmd = ["ffmpeg", "-y"]
    for inp in interleaved:
        cmd += ["-i", inp]

    n = len(interleaved)
    aformat = "".join(
        f"[{i}:a]aformat=sample_rates=44100:channel_layouts=mono[a{i}];"
        for i in range(n)
    )
    concat_in = "".join(f"[a{i}]" for i in range(n))
    fc = aformat + concat_in + f"concat=n={n}:v=0:a=1[out]"

    cmd += ["-filter_complex", fc, "-map", "[out]", out]
    subprocess.run(cmd, check=True, capture_output=True)

    for p in audio_paths + list(silences.values()):
        if os.path.exists(p):
            os.remove(p)


def _render_one_scene(img: Image.Image, audio: str, duration: float,
                      out: str, w: int, h: int) -> None:
    """Render a single scene with tightly-aligned audio.

    The output clip is exactly `duration` seconds long. Audio plays from
    t=0 and is padded with silence to match the video duration so concat
    later doesn't drop frames or drift.
    """
    png = out + ".png"
    img.save(png)
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", png,
        "-i", audio,
        # Pad audio with silence to exactly match video length
        "-af", f"apad,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
        "-vf", f"scale={w}:{h},fps={FPS},setpts=PTS-STARTPTS",
        "-vsync", "cfr",
        "-t", f"{duration:.3f}",
        out,
    ], check=True, capture_output=True)
    os.remove(png)


def _concat_clips(clips: list, output: str) -> None:
    """Concat clips with re-encoding to keep audio/video locked in sync.

    Stream copy (-c copy) preserves per-clip PTS offsets which can drift
    when clips have slightly different audio durations; re-encoding with
    a uniform fps and sample rate keeps everything aligned.
    """
    lst = output + ".list.txt"
    with open(lst, "w") as f:
        for p in clips:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
        "-vsync", "cfr", "-r", str(FPS),
        "-movflags", "+faststart",
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

    # Scene 1: hook — bilingual, intended to flow as ONE sentence:
    # "Do you know what {kanji} means?" with no perceptible pauses between
    # voices. Each segment's silence is trimmed before concat (see
    # _trim_silence) and the JP word is spoken at natural pace so it
    # doesn't drag the line down.
    specs = [{
        "frame": _make_hook_frame(word_data, WIDTH, HEIGHT),
        "segments": [
            {"text": "Do you know what",  "lang": "en", "rate": "+10%"},
            {"text": kanji,                "lang": "jp", "rate": "+5%"},
            {"text": "means?",             "lang": "en", "rate": "+10%"},
        ],
    }]

    # Scene 2: pronunciation — say the word in Japanese twice
    specs.append({
        "frame": _make_word_frame(word_data, WIDTH, HEIGHT),
        "segments": [
            {"text": kanji, "lang": "jp", "rate": "-20%"},
            {"text": kanji, "lang": "jp", "rate": "-20%"},
        ],
    })

    # Scene 3: definition — read English definition
    specs.append({
        "frame": _make_definition_frame(word_data, WIDTH, HEIGHT, bg_image=img(img_slot)),
        "segments": [
            {"text": (f"{pos}. " if pos else "") + defn + ".",
             "lang": "en", "rate": "+10%"},
        ],
    })
    img_slot += 1

    # Scene 4: example sentence (JP voice for sentence + EN voice for translation)
    example_jp = word_data.get("example_jp", "")
    example_en = word_data.get("example_en", "")
    if example_jp:
        ex_segments = [{"text": example_jp, "lang": "jp", "rate": "-10%"}]
        if example_en:
            ex_segments.append({"text": f"In English: {example_en}",
                                 "lang": "en", "rate": "+10%"})
        specs.append({
            "frame":    _make_example_frame(word_data, WIDTH, HEIGHT, img(img_slot)),
            "segments": ex_segments,
        })
        img_slot += 1

    # Scene 5: synonyms — EN intro, then each synonym pronounced individually in JP.
    # Larger pause_after between synonyms so each word has room to land.
    if syns:
        syn_segments = [
            {"text": "Related words.", "lang": "en", "rate": "+10%",
             "pause_after": 0.30},
        ]
        top = syns[:3]
        for j, s in enumerate(top):
            syn_segments.append({
                "text": s, "lang": "jp", "rate": "-15%",
                "pause_after": 0.25 if j < len(top) - 1 else 0.0,
            })
        specs.append({
            "frame":    _make_synonyms_frame(word_data, WIDTH, HEIGHT, img(img_slot)),
            "segments": syn_segments,
        })
        img_slot += 1

    # Scene 6: memory tip (English only)
    if tip:
        specs.append({
            "frame": _make_tip_frame(word_data, tip, WIDTH, HEIGHT, img(img_slot)),
            "segments": [
                {"text": f"Memory tip. {tip}", "lang": "en", "rate": "+15%"},
            ],
        })

    # Scene 7: recap — final pronunciation
    specs.append({
        "frame": _make_word_frame(word_data, WIDTH, HEIGHT),
        "segments": [
            {"text": kanji, "lang": "jp", "rate": "-10%"},
        ],
    })

    # Render each scene: build audio (multi-segment) then mux with frame
    clip_paths = []
    for i, spec in enumerate(specs):
        apath = os.path.join(TEMP_DIR, f"short_a_{i}.mp3")
        _multi_tts(spec["segments"], apath)

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
