"""Playlist management — find or create a playlist per JLPT level, then
add uploaded videos to it.

Playlist IDs are cached in playlists.json (committed back by the GitHub
Actions workflow) so we never burn API quota searching for them on
every run.
"""
import json
import os
from googleapiclient.errors import HttpError

from config import (BASE_DIR, PLAYLIST_BY_LEVEL,
                    PLAYLIST_DESCRIPTION_TEMPLATE, YT_CHANNEL_NAME)

CACHE_FILE = os.path.join(BASE_DIR, "playlists.json")


# ---------- cache I/O ----------

def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


# ---------- find / create ----------

def _search_playlist_by_title(yt, title: str) -> str | None:
    """Look up an existing playlist on this channel by its exact title.

    Used as a fallback when the cache is missing — e.g. you renamed a
    level's playlist, deleted playlists.json, or you're on a fresh
    machine. Returns None if no matching playlist is found.
    """
    page_token = None
    while True:
        kwargs = {"part": "snippet", "mine": True, "maxResults": 50}
        if page_token:
            kwargs["pageToken"] = page_token
        resp = yt.playlists().list(**kwargs).execute()
        for item in resp.get("items", []):
            if item["snippet"]["title"] == title:
                return item["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            return None


def _create_playlist(yt, title: str, description: str) -> str:
    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "defaultLanguage": "en",
        },
        "status": {"privacyStatus": "public"},
    }
    resp = yt.playlists().insert(part="snippet,status", body=body).execute()
    return resp["id"]


def ensure_playlist_for_level(yt, level: str) -> str | None:
    """Return the YouTube playlist ID for the given JLPT level. Searches
    the channel, creates the playlist if missing, and updates the local
    cache. Returns None if level is unknown / not configured."""
    if not level:
        return None
    title = PLAYLIST_BY_LEVEL.get(level)
    if not title:
        return None

    cache = _load_cache()
    if level in cache:
        return cache[level]

    # Cache miss — search YouTube
    pid = _search_playlist_by_title(yt, title)
    if pid is None:
        # Doesn't exist yet — create it
        description = PLAYLIST_DESCRIPTION_TEMPLATE.format(
            level=level, channel=YT_CHANNEL_NAME,
        )
        pid = _create_playlist(yt, title, description)
        print(f"  [playlist] created '{title}' → {pid}")
    else:
        print(f"  [playlist] found existing '{title}' → {pid}")

    cache[level] = pid
    _save_cache(cache)
    return pid


# ---------- add video ----------

def add_video_to_playlist(yt, playlist_id: str, video_id: str) -> bool:
    """Append a video to a playlist. Returns True on success, False on
    any handled error (so a playlist mishap never blocks the upload
    pipeline)."""
    try:
        yt.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind":    "youtube#video",
                        "videoId": video_id,
                    },
                },
            },
        ).execute()
        return True
    except HttpError as e:
        # 409 = already in playlist (idempotent — fine)
        if e.resp.status == 409:
            print(f"  [playlist] video {video_id} already in {playlist_id}")
            return True
        print(f"  [playlist] HTTP error adding {video_id} → {playlist_id}: {e}")
        return False
    except Exception as e:
        print(f"  [playlist] unexpected error: {e}")
        return False


def add_to_level_playlist(yt, video_id: str, level: str) -> bool:
    """One-call convenience: ensure the playlist for this level exists,
    then add the video to it. Returns True on success, False on any
    handled failure (logged but not raised)."""
    try:
        pid = ensure_playlist_for_level(yt, level)
        if not pid:
            return False
        return add_video_to_playlist(yt, pid, video_id)
    except HttpError as e:
        # 403 here is usually the OAuth scope issue — token only has
        # youtube.upload, not the broader youtube scope needed for
        # playlist management. Don't crash; the video is already uploaded.
        if e.resp.status == 403:
            print(f"  [playlist] 403 — token scope insufficient for playlist "
                  f"management. Re-run setup_oauth.py to authorize the broader "
                  f"'youtube' scope, then update the GitHub secret.")
        else:
            print(f"  [playlist] HTTP error: {e}")
        return False
    except Exception as e:
        print(f"  [playlist] unexpected error: {e}")
        return False
