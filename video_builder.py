import glob
import os
import random
import subprocess
import textwrap
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pykakasi import kakasi
from config import *
from tts import generate_speech

AUDIO_PADDING = 0.15

# Background music — drop .mp3/.m4a/.wav files into music/ to enable
MUSIC_DIR        = os.path.join(BASE_DIR, "music")
MUSIC_VOLUME_DB  = -18     # background level relative to speech (dB)
MUSIC_FADE_SEC   = 1.5     # fade in/out duration

# Shared converter for showing reading aids under kanji
_kks_render = kakasi()


def _kana_of(text: str) -> str:
    """Hiragana reading of any Japanese text. Returns '' if the text is
    already pure kana (so we don't render a duplicate line)."""
    if not text:
        return ""
    parts = _kks_render.convert(text)
    hira = "".join(p["hira"] for p in parts).strip()
    return "" if hira == text else hira


def _romaji_of(text: str) -> str:
    """Hepburn romaji for any Japanese text."""
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

    f_hook   = _load_font("regular", int(52 * scale))
    f_word   = _load_font("bold",    int(150 * scale))
    f_kana   = _load_font("regular", int(54 * scale))
    f_romaji = _load_font("italic",  int(44 * scale))

    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")

    show_kana   = bool(kana)   and kana   != kanji
    show_romaji = bool(romaji) and romaji != kanji

    h_top    = f_hook.getbbox("Do you know what")[3]
    h_kanji  = f_word.getbbox(kanji)[3]
    h_kana   = f_kana.getbbox(kana)[3]     if show_kana   else 0
    h_rom    = f_romaji.getbbox(romaji)[3] if show_romaji else 0
    h_bot    = f_hook.getbbox("means?")[3]
    gap      = int(20 * scale)
    total    = (h_top + gap + h_kanji
                + (gap + h_kana if show_kana   else 0)
                + (gap + h_rom  if show_romaji else 0)
                + gap + h_bot)
    y = (h - total) // 2

    y = _draw_centered(draw, "Do you know what", f_hook, DEFINITION_COLOR, y, w) + gap
    y = _draw_centered(draw, kanji, f_word, WORD_COLOR, y, w) + gap
    if show_kana:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + gap
    if show_romaji:
        y = _draw_centered(draw, romaji, f_romaji, ROMAJI_COLOR, y, w) + gap
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
    """Definition scene — vertically centered in the YouTube safe zone
    (top 6% to bottom 82%; bottom 18% is reserved for YouTube's overlay UI)."""
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji  = _load_font("bold",    int(130 * scale))
    f_kana   = _load_font("regular", int(64 * scale))
    f_romaji = _load_font("italic",  int(48 * scale))
    f_label  = _load_font("regular", int(50 * scale))
    f_def    = _load_font("regular", int(68 * scale))

    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")
    pos    = word_data.get("part_of_speech", "")
    defn   = word_data.get("definition", "")

    safe_top    = int(h * 0.06)
    safe_bottom = int(h * 0.82)
    y = safe_top + int(40 * scale)

    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(14 * scale)
    if kana and kana != kanji:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + int(10 * scale)
    if romaji:
        y = _draw_centered(draw, romaji, f_romaji, ROMAJI_COLOR, y, w) + int(28 * scale)
    if pos:
        y = _draw_centered(draw, pos, f_label, ROMAJI_COLOR, y, w) + int(24 * scale)
    lx1, lx2 = w // 5, 4 * w // 5
    draw.line([(lx1, y + 8), (lx2, y + 8)], fill=(55, 55, 75), width=2)
    y += int(48 * scale)
    if defn:
        _draw_wrapped(draw, defn, f_def, DEFINITION_COLOR, y, w)
    return img


def _make_example_frame(word_data: dict, w: int, h: int,
                         bg_image: Image.Image | None = None) -> Image.Image:
    """Example scene — header sized for impact; body fills the safe zone
    so the short doesn't feel top-heavy on a phone screen."""
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji   = _load_font("bold",    int(96 * scale))
    f_kana    = _load_font("regular", int(50 * scale))
    f_romaji  = _load_font("italic",  int(40 * scale))
    f_label   = _load_font("regular", int(46 * scale))
    f_jp      = _load_font("regular", int(64 * scale))
    f_jp_kana = _load_font("regular", int(46 * scale))
    f_en      = _load_font("italic",  int(52 * scale))

    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")

    safe_top = int(h * 0.06)
    y = safe_top + int(40 * scale)

    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(10 * scale)
    if kana and kana != kanji:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + int(8 * scale)
    if romaji:
        y = _draw_centered(draw, romaji, f_romaji, ROMAJI_COLOR, y, w) + int(28 * scale)
    y = _draw_centered(draw, "Example", f_label, ROMAJI_COLOR, y, w) + int(12 * scale)
    draw.line([(w // 5, y + 8), (4 * w // 5, y + 8)], fill=(55, 55, 75), width=2)
    y += int(36 * scale)

    example_jp   = word_data.get("example_jp", "")
    example_kana = word_data.get("example_kana", "")
    example_en   = word_data.get("example_en", "")

    if example_jp:
        y = _draw_wrapped_jp(draw, example_jp, f_jp, DEFINITION_COLOR, y, w) + int(12 * scale)
        if not example_kana:
            example_kana = _kana_of(example_jp)
        if example_kana and example_kana != example_jp:
            y = _draw_wrapped_jp(draw, example_kana, f_jp_kana, KANA_COLOR, y, w) + int(28 * scale)
    if example_en:
        _draw_wrapped(draw, f'"{example_en}"', f_en, EXAMPLE_COLOR, y, w)
    return img


def _make_synonyms_frame(word_data: dict, w: int, h: int,
                          bg_image: Image.Image | None = None) -> Image.Image:
    """Synonyms scene — vertically centered in the YouTube safe zone with
    larger type so the layout fills the visual frame instead of clustering
    at the top."""
    scale  = w / 1080
    img    = _make_bg(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji      = _load_font("bold",    int(110 * scale))
    f_kana_top   = _load_font("regular", int(56 * scale))
    f_romaji_top = _load_font("italic",  int(44 * scale))
    f_label      = _load_font("regular", int(48 * scale))
    f_syn        = _load_font("bold",    int(78 * scale))
    f_syn_kana   = _load_font("regular", int(44 * scale))
    f_syn_rom    = _load_font("italic",  int(38 * scale))

    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")
    syns   = word_data.get("synonyms", [])[:3]

    show_kana   = bool(kana)   and kana   != kanji
    show_romaji = bool(romaji)

    # Pre-compute total content height so we can vertically center the
    # whole block inside the safe zone (top 6% to bottom 82%).
    h_kanji   = f_kanji.getbbox(kanji)[3]
    h_kana    = f_kana_top.getbbox(kana)[3]    if show_kana   else 0
    h_romaji  = f_romaji_top.getbbox(romaji)[3] if show_romaji else 0
    h_label   = f_label.getbbox("Related")[3]

    gap_after_kanji  = int(10 * scale)
    gap_after_kana   = int(8 * scale)
    gap_after_romaji = int(28 * scale)
    gap_after_label  = int(20 * scale)
    gap_after_line   = int(40 * scale)
    gap_between_syns = int(36 * scale)

    syn_block_heights = []
    for syn in syns:
        sh = f_syn.getbbox(syn)[3]
        sk = _kana_of(syn)
        if sk:
            sh += int(8 * scale) + f_syn_kana.getbbox(sk)[3]
        sr = _romaji_of(syn)
        if sr:
            sh += int(6 * scale) + f_syn_rom.getbbox(sr)[3]
        syn_block_heights.append(sh)

    total_syn_h = (sum(syn_block_heights)
                   + gap_between_syns * max(0, len(syns) - 1))

    total_h = (h_kanji + gap_after_kanji
               + (h_kana   + gap_after_kana   if show_kana   else 0)
               + (h_romaji + gap_after_romaji if show_romaji else 0)
               + h_label + gap_after_label
               + gap_after_line
               + total_syn_h)

    safe_top    = int(h * 0.06)
    safe_bottom = int(h * 0.82)
    y = max(safe_top, safe_top + (safe_bottom - safe_top - total_h) // 2)

    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + gap_after_kanji
    if show_kana:
        y = _draw_centered(draw, kana, f_kana_top, KANA_COLOR, y, w) + gap_after_kana
    if show_romaji:
        y = _draw_centered(draw, romaji, f_romaji_top, ROMAJI_COLOR, y, w) + gap_after_romaji
    y = _draw_centered(draw, "Related", f_label, ROMAJI_COLOR, y, w) + gap_after_label
    draw.line([(w // 5, y + 8), (4 * w // 5, y + 8)], fill=(55, 55, 75), width=2)
    y += gap_after_line

    for j, syn in enumerate(syns):
        y = _draw_centered(draw, syn, f_syn, WORD_COLOR, y, w) + int(8 * scale)
        sk = _kana_of(syn)
        if sk:
            y = _draw_centered(draw, sk, f_syn_kana, KANA_COLOR, y, w) + int(6 * scale)
        sr = _romaji_of(syn)
        if sr:
            y = _draw_centered(draw, sr, f_syn_rom, ROMAJI_COLOR, y, w)
        if j < len(syns) - 1:
            y += gap_between_syns
    return img


def _make_tip_frame(word_data: dict, tip: str, w: int, h: int,
                     bg_image: Image.Image | None = None) -> Image.Image:
    """Memory-tip scene — header sized for impact, tip body at a comfortable
    reading size, all anchored within the YouTube safe zone."""
    scale  = w / 1080
    img    = _make_bg_clear(w, h, bg_image)
    draw   = ImageDraw.Draw(img)
    _draw_brand(draw, w, h)

    f_kanji  = _load_font("bold",    int(110 * scale))
    f_kana   = _load_font("regular", int(56 * scale))
    f_romaji = _load_font("italic",  int(44 * scale))
    f_label  = _load_font("regular", int(48 * scale))
    f_tip    = _load_font("italic",  int(58 * scale))

    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")

    safe_top = int(h * 0.06)
    y = safe_top + int(40 * scale)

    y = _draw_centered(draw, kanji, f_kanji, WORD_COLOR, y, w) + int(10 * scale)
    if kana and kana != kanji:
        y = _draw_centered(draw, kana, f_kana, KANA_COLOR, y, w) + int(8 * scale)
    if romaji:
        y = _draw_centered(draw, romaji, f_romaji, ROMAJI_COLOR, y, w) + int(28 * scale)
    y = _draw_centered(draw, "Memory Tip", f_label, ROMAJI_COLOR, y, w) + int(12 * scale)
    draw.line([(w // 5, y + 8), (4 * w // 5, y + 8)], fill=(55, 55, 75), width=2)
    y += int(40 * scale)
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


def _multi_tts(segments: list, out: str, default_gap: float = 0.05,
               trim_silence: bool = False) -> None:
    """Generate TTS for each segment and concatenate them.

    segments = [{"text": str, "lang": "en"|"jp", "rate": "+0%",
                 "pause_after": 0.0 (optional)}, ...]

    `default_gap` is used between segments that don't specify `pause_after`.
    Set very small (0.05s) so a single sentence split across voices flows
    naturally. Use larger explicit `pause_after` between distinct items
    (e.g. listing synonyms).

    `trim_silence` strips edge-tts's ~200-400ms of leading/trailing silence
    from each segment before concatenation. Off by default; turn on for
    scenes that need to flow as a single sentence across multiple voices
    (e.g. the hook).
    """
    audio_paths = []
    for i, seg in enumerate(segments):
        path = out + f".seg{i}.mp3"
        if trim_silence:
            raw = out + f".raw{i}.mp3"
            _tts_with_retry(seg["text"], raw,
                            lang=seg.get("lang", "en"),
                            rate=seg.get("rate", "+0%"))
            subprocess.run([
                "ffmpeg", "-y", "-i", raw,
                "-af",
                "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-40dB:"
                "stop_periods=-1:stop_duration=0.05:stop_threshold=-40dB",
                "-q:a", "4", "-acodec", "libmp3lame",
                path,
            ], check=True, capture_output=True)
            os.remove(raw)
        else:
            _tts_with_retry(seg["text"], path,
                            lang=seg.get("lang", "en"),
                            rate=seg.get("rate", "+0%"))
        audio_paths.append(path)

    if len(audio_paths) == 1:
        os.replace(audio_paths[0], out)
        return

    # Build per-gap silence files; skip when gap is effectively zero (lavfi
    # rejects -t 0 anyway).
    silences = []
    for i in range(len(segments) - 1):
        gap = segments[i].get("pause_after", default_gap)
        if gap <= 0.001:
            silences.append(None)
            continue
        sil = out + f".sil{i}.mp3"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{gap:.3f}", "-q:a", "9", "-acodec", "libmp3lame",
            sil,
        ], check=True, capture_output=True)
        silences.append(sil)

    interleaved = []
    for i, audio in enumerate(audio_paths):
        interleaved.append(audio)
        if i < len(silences) and silences[i] is not None:
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

    for p in audio_paths + [s for s in silences if s]:
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


# ---------- background music ----------

def _select_music_track() -> str | None:
    """Pick a random music file from MUSIC_DIR. Returns None if the
    directory is empty or missing — pipeline runs without music in that
    case (no breakage)."""
    if not os.path.isdir(MUSIC_DIR):
        return None
    tracks = []
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.ogg", "*.aac"):
        tracks.extend(glob.glob(os.path.join(MUSIC_DIR, ext)))
    if not tracks:
        return None
    return random.choice(tracks)


def _mix_background_music(video_in: str, music_path: str, video_out: str) -> None:
    """Overlay music under speech. Music is lowered to -22dB, looped if
    shorter than the video, trimmed to video length, and fades in at the
    start and out at the end."""
    dur = get_audio_duration(video_in)
    fade_out_start = max(0.0, dur - MUSIC_FADE_SEC)
    music_filter = (
        f"[1:a]volume={MUSIC_VOLUME_DB}dB,"
        f"afade=t=in:st=0:d={MUSIC_FADE_SEC},"
        f"afade=t=out:st={fade_out_start:.3f}:d={MUSIC_FADE_SEC}[m];"
        f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_in,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex", music_filter,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-shortest", "-movflags", "+faststart",
        video_out,
    ], check=True, capture_output=True)


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

    # Scene 1: hook — single English voice reading the romanized word
    # inline so the sentence flows from one speaker. Splitting between
    # the EN narration voice and the JP word voice made it sound like
    # two different people in conversation. The viewer still hears the
    # authentic Japanese pronunciation in scene 2 immediately after.
    hook_word = romaji or kanji
    specs = [{
        "frame": _make_hook_frame(word_data, WIDTH, HEIGHT),
        "segments": [
            {"text": f"Do you know what {hook_word} means?",
             "lang": "en", "rate": "+15%"},
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
        _multi_tts(spec["segments"], apath,
                   trim_silence=spec.get("trim_silence", False))

        dur  = get_audio_duration(apath) + AUDIO_PADDING
        clip = os.path.join(TEMP_DIR, f"short_clip_{i}.mp4")
        _render_one_scene(spec["frame"], apath, dur, clip, WIDTH, HEIGHT)
        clip_paths.append(clip)

        if os.path.exists(apath):
            os.remove(apath)

    # Step 1: concat all scene clips into one continuous video
    music = _select_music_track()
    if music:
        # Concat into a temp file first, then mix music on top
        pre_music = output_path + ".no_music.mp4"
        _concat_clips(clip_paths, pre_music)
        print(f"  [music] mixing {os.path.basename(music)}")
        _mix_background_music(pre_music, music, output_path)
        os.remove(pre_music)
    else:
        _concat_clips(clip_paths, output_path)

    for p in clip_paths:
        if os.path.exists(p):
            os.remove(p)
