"""
One-shot backfill: walk uploads.md and add every previously-uploaded video
to its JLPT-level playlist. Idempotent — safe to re-run; videos already
in a playlist are skipped by YouTube (409 → handled silently).

Usage (local):
    export YOUTUBE_CLIENT_ID="..."
    export YOUTUBE_CLIENT_SECRET="..."
    export YOUTUBE_REFRESH_TOKEN="..."
    python backfill_playlists.py

Usage (manual workflow):
    Add a one-off step to daily.yml or run via gh workflow dispatch with
    a separate workflow. Most users will just run it once locally.

Reads uploads.md (markdown table) and pulls (jlpt_level, video_id) from
each row. Skips rows missing either.
"""
import os
import re
import sys

from playlists import add_to_level_playlist
from uploader import _get_client

UPLOAD_LOG = "uploads.md"


def _parse_uploads() -> list:
    """Return list of (jlpt_level, video_id) tuples, in chronological order."""
    rows = []
    path = os.path.join(os.path.dirname(__file__), UPLOAD_LOG)
    if not os.path.exists(path):
        print(f"  {UPLOAD_LOG} not found — nothing to backfill")
        return rows

    # Video ID extractor: matches "https://youtube.com/shorts/<id>" inside a
    # markdown link, and captures just the id.
    vid_re = re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]+)")

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 9:
                continue
            date_cell = parts[1]
            if not (len(date_cell) >= 4 and date_cell[:4].isdigit()):
                continue   # header or separator
            level     = parts[6]   # JLPT column
            video_cell = parts[8]
            m = vid_re.search(video_cell)
            if not m or not level or level == "—":
                continue
            rows.append((level, m.group(1)))
    return rows


def main() -> int:
    rows = _parse_uploads()
    if not rows:
        print("No backfillable entries found.")
        return 0

    print(f"Backfilling {len(rows)} videos into playlists...")
    yt = _get_client()

    success, fail = 0, 0
    for level, video_id in rows:
        ok = add_to_level_playlist(yt, video_id, level)
        if ok:
            success += 1
            print(f"  ✓ {video_id}  →  {level}")
        else:
            fail += 1
            print(f"  ✗ {video_id}  →  {level}  (see log above)")

    print()
    print(f"Done. {success} succeeded, {fail} failed.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
