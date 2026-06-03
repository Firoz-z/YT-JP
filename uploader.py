import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YT_TAGS, YT_CATEGORY_ID
from playlists import add_to_level_playlist


def _get_client():
    """Build a YouTube client from a refresh token.

    IMPORTANT: we do NOT pass `scopes=` here. Doing so makes the refresh
    request explicitly ask Google for those scopes, and if the token
    was originally authorized for a narrower set, Google rejects the
    whole refresh with `invalid_scope: Bad Request`. By omitting scopes,
    the refresh succeeds with whatever the token actually has — so
    uploads work even when only youtube.upload was authorized, and
    playlist calls fail per-call with a clean 403 (handled in
    playlists.py).

    To unlock playlist management, re-run setup_oauth.py — that flow
    requests the broader youtube scope at authorization time.
    """
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


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


def upload_long_form(long_path: str, word_data: dict) -> str:
    """Upload the 1920×1080 landscape companion video. Returns video ID."""
    kanji     = word_data["kanji"]
    romaji    = word_data.get("romaji", "")
    # Same tag set as the Short minus 'shorts' — this is a regular upload
    base_tags = [t for t in YT_TAGS if t != "shorts"] + [
        kanji, romaji, f"learn {romaji}", f"{romaji} japanese",
        "japanese lesson", "japanese tutorial",
    ]
    description = _build_description(word_data)
    yt          = _get_client()

    title = f"Let's Learn: 「{kanji}」 ({romaji}) — Japanese Word of the Day"

    video_id = _insert(
        yt, long_path,
        title       = title,
        description = description + "\n\n#japanese #learnjapanese #nihongo #jlpt",
        tags        = base_tags,
    )

    level = word_data.get("jlpt_level", "")
    if level:
        if add_to_level_playlist(yt, video_id, level):
            print(f"  playlist: added long-form {video_id} to {level}")

    return video_id


def upload_short_only(short_path: str, word_data: dict) -> str:
    """Upload the Short, then drop it into its JLPT-level playlist.
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

    # Add to the playlist for this JLPT level. Failures here are logged
    # but do not raise — the video is already uploaded and that's what
    # matters most.
    level = word_data.get("jlpt_level", "")
    if level:
        if add_to_level_playlist(yt, video_id, level):
            print(f"  playlist: added {video_id} to {level}")

    return video_id
