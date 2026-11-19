"""Serve a folder over HTTP with byte ranges, like GitHub Pages, for testing the Kodi repository.

    .venv/bin/python scripts/build_repo.py --out dist/pages --url http://127.0.0.1:8765/
    .venv/bin/python scripts/serve_repo.py dist/pages 8765

Kodi opens a zip on an HTTP source ("Install from zip file") with Range requests, which
python -m http.server does not answer.
"""

import functools
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        path = self.translate_path(self.path)
        if not match or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        first, last = match.groups()
        if first:
            start, end = int(first), int(last) if last else size - 1
        else:
            start, end = max(0, size - int(last or 0)), size - 1
        end = min(end, size - 1)
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")  # closed by SimpleHTTPRequestHandler.do_GET
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        self._remaining = None
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "dist/pages"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    handler = functools.partial(RangeHandler, directory=folder)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"serving {folder} on http://127.0.0.1:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
