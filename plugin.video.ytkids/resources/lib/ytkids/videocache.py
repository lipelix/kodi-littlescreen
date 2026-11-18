"""Titles of recently listed videos, so a queued playlist can show them.

A queue is started from a video id list in the URL; the titles, lengths and channels come
from here instead of the URL.
"""

import json

LIMIT = 1500


class VideoCache:
    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.data = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            self.data = {}

    def remember(self, videos):
        changed = False
        for video in videos:
            entry = [video.title, video.channel, video.duration]
            if self.data.get(video.video_id) != entry:
                self.data.pop(video.video_id, None)
                self.data[video.video_id] = entry  # newest last, trimming drops the oldest
                changed = True
        while len(self.data) > LIMIT:
            self.data.pop(next(iter(self.data)))
        if changed:
            try:
                with open(self.path, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, ensure_ascii=False)
            except OSError:
                pass  # a queue without titles still plays

    def get(self, video_id):
        """(title, channel, duration) or None."""
        entry = self.data.get(video_id)
        if isinstance(entry, list) and len(entry) == 3:
            return tuple(entry)
        return None
