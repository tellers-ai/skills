#!/usr/bin/env python3
"""Check a Tellers .otio timeline before opening it in the player.

Usage:
    python3 check_otio.py timeline.otio [--root FOLDER] [--offline]

--root     the folder serve.py serves (default: the .otio's folder). Relative
           target_urls are resolved against the page, which sits at that root.
--offline  skip the network check of http(s) media.

Reports JSON errors, missing source ranges, unknown track kinds, local media
that does not exist under the root, local paths the browser cannot read, and
remote media that does not answer or does not send CORS headers, and effects
the player would skip (unknown or `tellers.ai.`-prefixed names, see
references/otio-format.md, Effects).
Prints the timeline duration and a one-line summary per track.
Exit code 1 when an error was found. Standard library only.
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

errors = []
warnings = []

VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".ts"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".svg", ".bmp", ".tif", ".tiff"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac"}
UNSUPPORTED_EXT = {
    ".m3u8": "HLS streams do not play (the player never loads the segments); "
             "save the part you need with: ffmpeg -i URL.m3u8 -c copy part.mp4",
    ".avi": "AVI is not supported; convert to .mp4 (H.264)",
    ".wmv": "WMV is not supported; convert to .mp4 (H.264)",
    ".flv": "FLV is not supported; convert to .mp4 (H.264)",
    ".mxf": "MXF is not supported by the player; convert to .mp4 or .mov",
    ".heic": "HEIC is not supported; convert to .jpg",
    ".heif": "HEIF is not supported; convert to .jpg",
    ".psd": "PSD is not supported; export a .png",
    ".wma": "WMA is not supported; convert to .m4a or .mp3",
}

# Effect names the player renders (tellers-timeline's EFFECT_SPECS, bare).
TELLERS_EFFECTS = {
    "Transform", "Blur", "Pixelate", "Adjustment", "ColorMatrix", "HslAdjustment", "Noise",
    "RGBSplit", "ZoomBlur", "DropShadow", "ChromaKey", "Border", "MotionBlur", "Blend", "Mask",
    "TrackMatte", "ColorLut", "Volume", "Pan", "TimeWarp", "TextTypewriter", "TextWordReveal",
    "TextKaraoke", "TextWave", "TextColor",
}
RESOLVE_EFFECTS = {"Transform", "Cropping", "Fairlight Clip Volume and Fades"}


def check_effects(effects, where):
    if not isinstance(effects, list):
        return
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        schema = str(effect.get("OTIO_SCHEMA", ""))
        if schema.startswith(("LinearTimeWarp.", "FreezeFrame.")):
            continue
        name = effect.get("effect_name", "")
        if name == "Resolve Effect":
            resolve = (effect.get("metadata") or {}).get("Resolve_OTIO") or {}
            if resolve.get("Effect Name") not in RESOLVE_EFFECTS:
                warnings.append(f"{where}: Resolve effect {resolve.get('Effect Name')!r} is ignored by the player")
        elif name.startswith("tellers.ai.") and name[len("tellers.ai."):] in TELLERS_EFFECTS:
            warnings.append(f"{where}: write effect_name {name[len('tellers.ai.'):]!r}; the player skips {name!r}")
        elif name not in TELLERS_EFFECTS:
            warnings.append(f"{where}: unknown effect {name!r} is ignored by the player")
        elif name == "ColorLut":
            tellers = (effect.get("metadata") or {}).get("tellers.ai") or {}
            if not tellers.get("cube_url"):
                warnings.append(f"{where}: ColorLut without metadata[\"tellers.ai\"].cube_url is skipped")
        elif not isinstance(((effect.get("metadata") or {}).get("tellers.ai") or {}).get("parameters", {}), dict):
            errors.append(f"{where}: {name} parameters must be an object")


def check_extension(url, kind, where):
    path = urllib.parse.urlparse(url).path
    extension = os.path.splitext(urllib.parse.unquote(path))[1].lower()
    if extension in UNSUPPORTED_EXT:
        errors.append(f"{where}: {UNSUPPORTED_EXT[extension]} ({url})")
    elif extension in (".tif", ".tiff"):
        warnings.append(f"{where}: TIFF only displays in Safari; prefer .png or .jpg ({url})")
    elif kind == "audio" and extension in IMAGE_EXT:
        errors.append(f"{where}: an image on an audio track ({url})")
    elif extension and extension not in VIDEO_EXT | IMAGE_EXT | AUDIO_EXT:
        warnings.append(f"{where}: unknown extension {extension}; the player will sniff the file ({url})")
    elif kind == "video" and extension in AUDIO_EXT:
        warnings.append(f"{where}: an audio file on a video track shows nothing; move it to an audio track ({url})")


def seconds(rational_time):
    if not isinstance(rational_time, dict):
        return None
    try:
        rate = float(rational_time.get("rate", 1)) or 1
        return float(rational_time.get("value", 0)) / rate
    except (TypeError, ValueError):
        return None


def item_duration(item, where):
    source_range = item.get("source_range")
    if not isinstance(source_range, dict):
        errors.append(f"{where}: missing source_range")
        return 0
    if "start_time" not in source_range and item.get("OTIO_SCHEMA") != "Gap.1":
        errors.append(f"{where}: source_range has no start_time")
    duration = seconds(source_range.get("duration"))
    if duration is None:
        errors.append(f"{where}: source_range has no valid duration")
        return 0
    if duration <= 0:
        warnings.append(f"{where}: duration is {duration:g}s")
    return duration


def media_url(clip):
    references = clip.get("media_references") or {}
    key = clip.get("active_media_reference_key") or "DEFAULT_MEDIA"
    reference = references.get(key) or {}
    return reference.get("OTIO_SCHEMA", ""), reference.get("target_url")


def check_remote(url, where):
    request = urllib.request.Request(
        url, headers={"Range": "bytes=0-1", "Origin": "http://localhost:8000", "User-Agent": "tellers-check-otio"}
    )
    try:
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.URLError as error:
            if not isinstance(error.reason, ssl.SSLCertVerificationError):
                raise
            # python.org builds on macOS ship without CA certificates; only headers are read here.
            response = urllib.request.urlopen(request, timeout=15, context=ssl._create_unverified_context())
        with response:
            headers = response.headers
            status = response.status
    except urllib.error.HTTPError as error:
        errors.append(f"{where}: {url} answered HTTP {error.code}")
        return
    except Exception as error:  # DNS, TLS, timeout...
        errors.append(f"{where}: {url} unreachable ({error})")
        return
    content_type = headers.get("Content-Type", "")
    if "text/html" in content_type:
        errors.append(f"{where}: {url} is an HTML page, not a media file")
    if not headers.get("Access-Control-Allow-Origin"):
        errors.append(f"{where}: {url} sends no Access-Control-Allow-Origin header; the browser will block it")
    if status != 206 and headers.get("Accept-Ranges") != "bytes":
        warnings.append(f"{where}: {url} does not support Range requests; seeking will be slow")


def check_url(url, where, root, offline, checked):
    if not url:
        errors.append(f"{where}: ExternalReference without target_url")
        return
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ("http", "https"):
        if parsed.hostname in ("localhost", "127.0.0.1"):
            local = urllib.parse.unquote(parsed.path).lstrip("/")
            path = os.path.join(root, local)
            if not os.path.isfile(path):
                warnings.append(f"{where}: {url} -> {path} not found under the served root")
            return
        if not offline and url not in checked:
            checked.add(url)
            check_remote(url, where)
        return
    if parsed.scheme == "file" or (os.path.isabs(url) and os.path.exists(url)) or (len(url) > 1 and url[1] == ":"):
        errors.append(
            f"{where}: {url} is a path on disk; the browser cannot read it. "
            "Copy the file into the served folder and use a relative URL."
        )
        return
    if parsed.scheme in ("data", "blob"):
        return
    path = os.path.join(root, urllib.parse.unquote(parsed.path).lstrip("/"))
    if not os.path.isfile(path):
        errors.append(f"{where}: {url} -> {path} does not exist")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("otio")
    parser.add_argument("--root", help="folder served by serve.py (default: the .otio's folder)")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    try:
        with open(args.otio, encoding="utf-8") as f:
            timeline = json.load(f)
    except json.JSONDecodeError as error:
        sys.exit(f"ERROR invalid JSON: {error}")
    root = os.path.abspath(args.root or os.path.dirname(os.path.abspath(args.otio)))

    if timeline.get("OTIO_SCHEMA") != "Timeline.1":
        errors.append("root OTIO_SCHEMA is not Timeline.1")
    if not (timeline.get("metadata") or {}).get("tellers_aspect_ratio"):
        warnings.append('no metadata.tellers_aspect_ratio; the player assumes "16_9"')
    tracks = ((timeline.get("tracks") or {}).get("children")) or []
    if not tracks:
        errors.append("tracks.children is empty")

    check_effects((timeline.get("tracks") or {}).get("effects"), "timeline")
    checked = set()
    total = 0.0
    lines = []
    for t, track in enumerate(tracks):
        kind = str(track.get("kind", "")).lower()
        name = track.get("name") or f"track {t}"
        if kind not in ("video", "audio"):
            errors.append(f"{name}: kind must be video or audio, got {track.get('kind')!r}")
        check_effects(track.get("effects"), name)
        position = 0.0
        counts = {}
        for c, item in enumerate(track.get("children") or []):
            schema = item.get("OTIO_SCHEMA", "?")
            where = f"{name} / #{c} {item.get('name') or schema}"
            if schema.startswith("Transition"):
                counts["transition"] = counts.get("transition", 0) + 1
                continue
            check_effects(item.get("effects"), where)
            duration = item_duration(item, where)
            if schema.startswith("Clip"):
                reference_schema, url = media_url(item)
                if reference_schema.startswith("ExternalReference"):
                    if url:
                        check_extension(url, kind, where)
                    check_url(url, where, root, args.offline, checked)
                    counts["media"] = counts.get("media", 0) + 1
                elif reference_schema.startswith("GeneratorReference"):
                    if kind == "audio":
                        errors.append(f"{where}: text clip on an audio track")
                    counts["text"] = counts.get("text", 0) + 1
                else:
                    errors.append(f"{where}: unknown media reference {reference_schema!r}")
            elif schema.startswith("Gap"):
                counts["gap"] = counts.get("gap", 0) + 1
            else:
                warnings.append(f"{where}: {schema} is not a Clip or Gap")
            position += duration
        total = max(total, position)
        summary = ", ".join(f"{n} {k}" for k, n in counts.items()) or "empty"
        lines.append(f"  [{t}] {kind:5} {name!r}: {summary}, ends at {position:.2f}s")

    print(f"{args.otio}: {len(tracks)} tracks, {total:.2f}s (first track = bottom layer)")
    print("\n".join(lines))
    for warning in warnings:
        print(f"WARNING {warning}")
    for error in errors:
        print(f"ERROR {error}")
    if not errors:
        print("OK")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
