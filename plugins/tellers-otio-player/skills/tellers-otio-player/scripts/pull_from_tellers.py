#!/usr/bin/env python3
"""Bring a Tellers project's timeline and media to local files.

Takes the project's .otio (as returned by the Tellers MCP's get_project_timeline
or preview_project, or exported from the app) and builds a folder the local
player can open:

    <out>/
      media/<name>-<id>.<ext>    every asset the timeline uses, once
      <name>.otio                the timeline, target_urls rewritten to media/...

Each clip's asset id is read from its media reference metadata (media_id, or
metadata["tellers.ai"].media_id). The file is resolved through the Tellers API
(POST /asset/download_urls) at the chosen rendition:

    compatible  (default) the original file when the player can decode it,
                otherwise the highest player-compatible rendition
    original    the uploaded file as is (may not play in the browser, e.g. ProRes,
                DNxHD, MXF)
    highest / 1080p / 720p / 480p / lowest
                player-compatible rendition of that size

Clips without an asset id but with an http(s) target_url (stock, signed URLs)
are downloaded from that URL. Text clips are kept as they are.

Auth: TELLERS_API_KEY, or the session saved by `tellers login`.
API base: TELLERS_API_BASE (default https://api.prod.aws.tellers.ai).

Usage:
    python3 pull_from_tellers.py project.otio [--out DIR] [--rendition R]
                                 [--name NAME] [--force]
Standard library only.
"""
import argparse
import json
import mimetypes
import os
import re
import shutil
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("TELLERS_API_BASE", "https://api.prod.aws.tellers.ai").rstrip("/")

# rendition -> (quality, player_compatible) for /asset/download_urls
RENDITIONS = {
    "compatible": ("original", True),
    "original": ("original", False),
    "highest": ("highest", True),
    "1080p": ("1080p", True),
    "720p": ("720p", True),
    "480p": ("480p", True),
    "lowest": ("lowest", True),
}

CONTENT_TYPE_EXT = {
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
    "video/x-matroska": ".mkv", "video/mp2t": ".ts", "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/wav": ".wav", "audio/x-wav": ".wav",
    "audio/ogg": ".ogg", "audio/flac": ".flac", "image/jpeg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg", "image/avif": ".avif",
}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "media"


def open_url(request, timeout=60):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as error:
        if not isinstance(error.reason, ssl.SSLCertVerificationError):
            raise
        # python.org builds on macOS ship without CA certificates.
        return urllib.request.urlopen(request, timeout=timeout, context=ssl._create_unverified_context())


def auth_headers():
    api_key = os.environ.get("TELLERS_API_KEY")
    if api_key:
        return {"x-api-key": api_key}
    bearer = os.environ.get("TELLERS_AUTH_BEARER")
    if not bearer:
        # Session written by `tellers login` (dirs::config_dir()/tellers/auth.json).
        candidates = [
            os.path.expanduser("~/Library/Application Support/tellers/auth.json"),
            os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "tellers", "auth.json"),
            os.path.join(os.environ.get("APPDATA", ""), "tellers", "auth.json"),
        ]
        for path in candidates:
            try:
                with open(path, encoding="utf-8") as f:
                    bearer = json.load(f).get("access_token")
            except (OSError, ValueError):
                continue
            if bearer:
                break
    if not bearer:
        sys.exit("No Tellers credentials: set TELLERS_API_KEY or run `tellers login`.")
    return {"Authorization": bearer if bearer.startswith("Bearer ") else f"Bearer {bearer}"}


def resolve_download_urls(asset_ids, quality, player_compatible):
    body = json.dumps({"asset_ids": asset_ids, "quality": quality,
                       "player_compatible": player_compatible}).encode()
    request = urllib.request.Request(
        f"{API_BASE}/asset/download_urls", data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "tellers-pull", **auth_headers()})
    try:
        with open_url(request) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        hint = " (token expired? run `tellers login` again)" if error.code == 401 else ""
        sys.exit(f"Tellers API {error.code} on /asset/download_urls{hint}: {detail}")
    except urllib.error.URLError as error:
        sys.exit(f"Cannot reach the Tellers API at {API_BASE}: {error.reason}")
    result = {}
    for item in payload.get("items", []):
        download = item.get("download") or {}
        if item.get("error") or not download.get("url"):
            result[item.get("asset_id")] = (None, item.get("error_message") or "no download URL")
        else:
            result[item.get("asset_id")] = (download["url"], None)
    return result


def download(url, destination_base):
    """Download url to destination_base + extension; return the file name."""
    request = urllib.request.Request(url, headers={"User-Agent": "tellers-pull"})
    with open_url(request, timeout=120) as response:
        extension = os.path.splitext(urllib.parse.unquote(urllib.parse.urlparse(url).path))[1].lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,5}", extension or ""):
            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            extension = CONTENT_TYPE_EXT.get(content_type) or mimetypes.guess_extension(content_type) or ""
        destination = destination_base + extension
        partial = destination + ".part"
        with open(partial, "wb") as out:
            shutil.copyfileobj(response, out, 1024 * 1024)
    os.replace(partial, destination)
    return os.path.basename(destination)


def existing(destination_base):
    folder, base = os.path.split(destination_base)
    if not os.path.isdir(folder):
        return None
    for name in os.listdir(folder):
        if os.path.splitext(name)[0] == base and not name.endswith(".part"):
            return name
    return None


def media_id_of(reference):
    metadata = reference.get("metadata") or {}
    tellers = metadata.get("tellers.ai") if isinstance(metadata.get("tellers.ai"), dict) else {}
    value = metadata.get("media_id") or tellers.get("media_id")
    return str(value) if value else None


def iter_references(node):
    """Every (clip, reference) pair in the timeline, group clips (nested stacks) included."""
    if isinstance(node, dict):
        if str(node.get("OTIO_SCHEMA", "")).startswith("Clip"):
            for reference in (node.get("media_references") or {}).values():
                if isinstance(reference, dict):
                    yield node, reference
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from iter_references(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_references(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("otio", help="Tellers project timeline (.otio / .json)")
    parser.add_argument("--out", help="output folder (default: <otio folder>/<name>)")
    parser.add_argument("--rendition", choices=list(RENDITIONS), default="compatible",
                        help="which file to fetch per asset (default: compatible)")
    parser.add_argument("--name", help="output .otio name (default: the timeline name)")
    parser.add_argument("--force", action="store_true", help="download again files already in media/")
    args = parser.parse_args()

    with open(args.otio, encoding="utf-8") as f:
        timeline = json.load(f)
    # preview_project's structured result wraps the timeline as {"otio": {...}}.
    if "tracks" not in timeline and isinstance(timeline.get("otio"), dict):
        timeline = timeline["otio"]
    name = slug(args.name or timeline.get("name") or os.path.splitext(os.path.basename(args.otio))[0])
    out = os.path.abspath(args.out or os.path.join(os.path.dirname(os.path.abspath(args.otio)), name))
    media_dir = os.path.join(out, "media")
    os.makedirs(media_dir, exist_ok=True)
    quality, player_compatible = RENDITIONS[args.rendition]

    references = list(iter_references(timeline))
    asset_names = {}   # media id -> readable name for the file
    for clip, reference in references:
        media_id = media_id_of(reference)
        if media_id and media_id not in asset_names:
            asset_names[media_id] = reference.get("name") if reference.get("name") not in (None, "", "DEFAULT_MEDIA") else clip.get("name")

    files = {}         # media id or url -> file name in media/
    errors = []

    def base_for(key, label):
        return os.path.join(media_dir, f"{slug(label)}-{re.sub(r'[^A-Za-z0-9]', '', key)[-8:]}")

    def fetch(key, url, label):
        base = base_for(key, label)
        found = None if args.force else existing(base)
        if found:
            files[key] = found
            return
        print(f"downloading {label}")
        try:
            files[key] = download(url, base)
        except Exception as error:
            errors.append(f"{label}: download failed ({error})")

    ids = sorted(asset_names)
    pending = [i for i in ids if args.force or not existing(base_for(i, asset_names[i] or i))]
    resolved = {}
    for start in range(0, len(pending), 50):
        resolved.update(resolve_download_urls(pending[start:start + 50], quality, player_compatible))
    for media_id in ids:
        url, error = resolved.get(media_id, (None, None))
        if error:
            errors.append(f"asset {media_id} ({asset_names[media_id]}): {error}")
            continue
        fetch(media_id, url or "", asset_names[media_id] or media_id)

    unlinked = 0
    for clip, reference in references:
        media_id = media_id_of(reference)
        url = reference.get("target_url") or ""
        if media_id:
            if media_id in files:
                reference["target_url"] = f"media/{files[media_id]}"
            continue
        if url.startswith(("http://", "https://")):
            if url not in files:
                path_name = os.path.splitext(os.path.basename(urllib.parse.urlparse(url).path))[0]
                fetch(url, url, clip.get("name") or path_name)
            if url in files:
                reference["target_url"] = f"media/{files[url]}"
        elif str(reference.get("OTIO_SCHEMA", "")).startswith("ExternalReference") and not url:
            unlinked += 1

    otio_path = os.path.join(out, f"{name}.otio")
    with open(otio_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2)

    print(f"\n{out}")
    print(f"  {len(set(files.values()))} media file(s) in media/ ({args.rendition})")
    print(f"  {os.path.basename(otio_path)}")
    if unlinked:
        print(f"WARNING {unlinked} media reference(s) have neither an asset id nor a URL")
    for error in errors:
        print(f"ERROR {error}")
    print("\nNext:")
    print(f'  cp "{os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "player.html"))}" "{out}/"')
    print(f'  python3 "{os.path.join(os.path.dirname(os.path.abspath(__file__)), "serve.py")}" "{out}" --port 8000')
    print(f"  open http://localhost:8000/player.html?otio={os.path.basename(otio_path)}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
