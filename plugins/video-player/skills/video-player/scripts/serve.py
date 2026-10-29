#!/usr/bin/env python3
"""Serve a folder over http://localhost for the Tellers player.

Why not `python3 -m http.server`: it ignores `Range` headers, so the player has
to download a whole video before it can seek in it. This server answers byte
ranges (206), sends CORS headers so a page on another localhost port can read the
media (other sites cannot), rejects requests whose Host is not localhost while it
listens on localhost (DNS rebinding),
disables caching so an edited .otio is picked up on reload, and knows the
media types the player needs (.otio, .mov, .m4a, .wasm...).

It also saves exports: `POST /exports/<name>` from a page on this machine writes
the request body to `<folder>/exports/<name>` (export file types only), so the
player can render with `ui.export({ save: "none" })` and hand the file over.

Usage:
    python3 serve.py [folder] [--port 8000] [--host 127.0.0.1]

Then open http://localhost:8000/player.html?otio=timeline.otio
Standard library only; Python 3.8+.
"""
import argparse
import http.server
import json
import mimetypes
import os
import re
import socketserver
import sys
import urllib.parse

EXTRA_TYPES = {
    ".otio": "application/json",
    ".json": "application/json",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
    ".vtt": "text/vtt",
    ".woff2": "font/woff2",
    ".wasm": "application/wasm",
    ".js": "text/javascript",
}
for ext, mime in EXTRA_TYPES.items():
    mimetypes.add_type(mime, ext)

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")
LOOPBACK_ORIGIN_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
LOOPBACK_HOST_RE = re.compile(r"^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
CHUNK = 1 << 20
EXPORT_DIR = "exports"
EXPORT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,150}\.(mp4|webm|png|jpe?g|mp3|aac)$")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **EXTRA_TYPES}
    loopback_only = True  # set from --host in main()

    def end_headers(self):
        # Only pages on this machine may read the files; any other site gets no CORS header.
        origin = self.headers.get("Origin", "")
        if LOOPBACK_ORIGIN_RE.match(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header("Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def host_allowed(self):
        # A website can point its own domain at 127.0.0.1 (DNS rebinding) and read the
        # folder as same-origin; its requests still carry that domain as Host.
        if self.loopback_only and not LOOPBACK_HOST_RE.match(self.headers.get("Host", "")):
            self.send_error(403, "Host must be localhost")
            return False
        return True

    def do_OPTIONS(self):
        if not self.host_allowed():
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.end_headers()

    def do_POST(self):
        """Save an export: POST /exports/<name> with the file as the body."""
        if not self.host_allowed():
            return
        # Any site can send a POST to localhost; only pages served from this machine may write.
        if not LOOPBACK_ORIGIN_RE.match(self.headers.get("Origin", "")):
            self.send_error(403, "Exports are accepted only from a page on localhost")
            return
        prefix = "/" + EXPORT_DIR + "/"
        path = self.path.split("?", 1)[0]
        name = urllib.parse.unquote(path[len(prefix):]) if path.startswith(prefix) else ""
        if not EXPORT_NAME_RE.match(name):
            self.send_error(400, "POST to /exports/<name>.mp4 (or .webm .png .jpg .mp3 .aac)")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.send_error(411, "Content-Length required")
            return

        folder = os.path.join(self.directory, EXPORT_DIR)
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, name)
        partial = target + ".part"
        left = length
        with open(partial, "wb") as f:
            while left > 0:
                data = self.rfile.read(min(CHUNK, left))
                if not data:
                    break
                f.write(data)
                left -= len(data)
        if left:
            os.remove(partial)
            self.send_error(400, "Upload ended early")
            return
        os.replace(partial, target)

        body = json.dumps({"path": os.path.join(EXPORT_DIR, name), "bytes": length}).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        sys.stderr.write(f"Saved {target} ({length} bytes)\n")

    def send_head(self):
        if not self.host_allowed():
            return None
        path = self.translate_path(self.path)
        range_header = self.headers.get("Range")
        if not range_header or os.path.isdir(path) or not os.path.isfile(path):
            response = super().send_head()
            return response

        match = RANGE_RE.match(range_header.strip())
        size = os.path.getsize(path)
        if not match or (not match.group(1) and not match.group(2)):
            self.send_error(416, "Unsupported range")
            return None
        if match.group(1):
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
        else:  # "bytes=-N": the last N bytes
            start = max(0, size - int(match.group(2)))
            end = size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._range_left = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_range_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        self._range_left = None
        while left > 0:
            data = source.read(min(CHUNK, left))
            if not data:
                break
            outputfile.write(data)
            left -= len(data)

    def log_message(self, fmt, *args):
        # Keep the log readable: one line per request, errors stand out.
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?", default=".", help="folder to serve (default: current folder)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from another device")
    args = parser.parse_args()

    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        sys.exit(f"Not a folder: {root}")

    Handler.loopback_only = args.host in ("127.0.0.1", "localhost", "::1")

    def handler(*a, **kw):
        return Handler(*a, directory=root, **kw)

    try:
        server = Server((args.host, args.port), handler)
    except OSError as error:
        sys.exit(f"Port {args.port} is not free ({error}). Try --port {args.port + 1}.")

    print(f"Serving {root}")
    print(f"  http://localhost:{args.port}/")
    if os.path.isfile(os.path.join(root, "player.html")):
        print(f"  http://localhost:{args.port}/player.html?otio=timeline.otio")
    print("Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
