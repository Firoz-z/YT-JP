import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YT_TAGS, YT_CATEGORY_ID


def _get_client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            # Needed to call thumbnails().set() — youtube.upload alone is
            # insufficient for setting custom thumbnails.
            "https://www.googleapis.com/auth/youtube",
        ],
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def _set_thumbnail(yt, video_id: str, thumbnail_path: str) -> None:
    """Upload a custom thumbnail for the given video. Channel must be
    verified for this to succeed; if it isn't, YouTube will return 400
    and we just log + continue (video is still live)."""
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return
    try:
        yt.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        print(f"  thumbnail set: {os.path.basename(thumbnail_path)}")
    except Exception as e:
        print(f"  [thumbnail] could not set custom thumbnail: {e}")
        print(f"  [thumbnail] video is still live with auto-picked frame")


def _build_description(word_data: dict) -> str:
    kanji  = word_data["kanji"]
    kana   = word_data.get("kana", "")
    romaji = word_data.get("romaji", "")
    pos    = word_data.get("part_of_speech", "")
    defn   = word_data["definition"]
    ex_jp  = word_data.get("example_jp", "")
    ex_en  = word_data.get("example_en", "")
    jlpt   = word_data.get("jlpt_level", "")

    lines = [f"Learn the Japanese word '{kanji}'!\n",
             f"Word: {kanji}"]
    if kana and kana != kanji:
        lines.append(f"Reading: {kana}")
    if romaji:
        lines.append(f"Romaji: {romaji}")
    if pos:
        lines.append(f"Part of Speech: {pos}")
    if jlpt:
        lines.append(f"JLPT Level: {jlpt}")
    lines.append(f"Meaning: {defn}")
    if ex_jp:
        lines.append(f"\nExample: {ex_jp}")
    if ex_en:
        lines.append(f"Translation: {ex_en}")
    return "\n".join(lines)


def _insert(yt, video_path: str, title: str, description: str, tags: list) -> str:
    request = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":           title,
                "description":     description,
                "tags":            tags,
                "categoryId":      YT_CATEGORY_ID,
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(video_path, mimetype="video/mp4", resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def upload_short_only(short_path: str, word_data: dict,
                      thumbnail_path: str | None = None) -> str:
    """Upload the Short and optionally set a custom thumbnail.
    Returns video ID."""
    kanji       = word_data["kanji"]
    romaji      = word_data.get("romaji", "")
    base_tags   = YT_TAGS + [kanji, romaji, f"learn {romaji}", f"{romaji} japanese"]
    description = _build_description(word_data)
    yt          = _get_client()

    title_parts = [f"{kanji}"]
    if romaji:
        title_parts.append(f"({romaji})")
    title_parts.append("| Japanese Word of the Day #shorts")
    title = " ".join(title_parts)

    video_id = _insert(
        yt, short_path,
        title       = title,
        description = description + "\n\n#japanese #learnjapanese #nihongo #jlpt #shorts",
        tags        = base_tags + ["shorts"],
    )
    _set_thumbnail(yt, video_id, thumbnail_path)
    return video_id
