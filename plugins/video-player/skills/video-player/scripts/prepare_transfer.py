#!/usr/bin/env python3
"""Prepare a local Tellers timeline for upload with the Tellers CLI.

Tellers turns an uploaded .otio into a project by matching every clip's media,
by file name, against assets already in the account. This script builds a
folder that makes that match certain:

    <out>/
      media/<prefix>__<file>     every media file the timeline uses, once
      <name>.otio                the timeline, target_urls rewritten to media/...
      text-clips.json            text clips taken out of the timeline (see below)

- Local media is copied (hard-linked when possible). Remote http(s) media is
  downloaded, since Tellers can only link a clip to a file it holds.
- File names get a "<prefix>__" so they cannot collide with same-named files
  already in the account (two candidates = the import asks instead of linking).
- Text clips have no media file, so the importer would mark them as missing.
  They are replaced by gaps of the same length and saved to text-clips.json
  (track, start time, duration, clip) to be added back once the project exists.

Usage:
    python3 prepare_transfer.py timeline.otio [--root FOLDER] [--out DIR]
                                [--prefix NAME] [--no-prefix]
Standard library only.
"""
import argparse
import copy
import json
import os
import re
import shutil
import ssl
import sys
import urllib.parse
import urllib.request


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "edit"


def seconds(rational_time):
    rate = float(rational_time.get("rate", 1)) or 1
    return float(rational_time.get("value", 0)) / rate


def is_text_clip(item):
    if not str(item.get("OTIO_SCHEMA", "")).startswith("Clip"):
        return False
    references = item.get("media_references") or {}
    reference = references.get(item.get("active_media_reference_key") or "DEFAULT_MEDIA") or {}
    return str(reference.get("OTIO_SCHEMA", "")).startswith("GeneratorReference")


def download(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "tellers-prepare-transfer"})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.URLError as error:
        if not isinstance(error.reason, ssl.SSLCertVerificationError):
            raise
        # python.org builds on macOS ship without CA certificates.
        response = urllib.request.urlopen(request, timeout=60, context=ssl._create_unverified_context())
    with response, open(destination, "wb") as out:
        shutil.copyfileobj(response, out)


def place(source, destination):
    if os.path.exists(destination):
        return
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("otio")
    parser.add_argument("--root", help="folder relative target_urls resolve against (default: the .otio's folder)")
    parser.add_argument("--out", help="output folder (default: <root>/tellers-transfer)")
    parser.add_argument("--prefix", help="file name prefix (default: the timeline name)")
    parser.add_argument("--no-prefix", action="store_true", help="keep original file names")
    args = parser.parse_args()

    with open(args.otio, encoding="utf-8") as f:
        timeline = json.load(f)
    root = os.path.abspath(args.root or os.path.dirname(os.path.abspath(args.otio)))
    name = slug(timeline.get("name") or os.path.splitext(os.path.basename(args.otio))[0])
    prefix = "" if args.no_prefix else f"{slug(args.prefix or name)}__"
    out = os.path.abspath(args.out or os.path.join(root, "tellers-transfer"))
    media_dir = os.path.join(out, "media")
    os.makedirs(media_dir, exist_ok=True)

    placed = {}      # source (path or url) -> file name in media/
    taken = {}       # file name -> source, to keep names unique
    text_clips = []
    errors = []

    def media_name(source, original_name):
        if source in placed:
            return placed[source]
        base, extension = os.path.splitext(original_name or "media")
        candidate = f"{prefix}{base}{extension}"
        counter = 2
        while candidate.lower() in taken and taken[candidate.lower()] != source:
            candidate = f"{prefix}{base}-{counter}{extension}"
            counter += 1
        taken[candidate.lower()] = source
        placed[source] = candidate
        return candidate

    result = copy.deepcopy(timeline)
    for t, track in enumerate(result.get("tracks", {}).get("children", [])):
        position = 0.0
        children = []
        for item in track.get("children", []):
            source_range = item.get("source_range") or {}
            duration = seconds(source_range.get("duration") or {})
            if is_text_clip(item):
                text_clips.append({"track_index": t, "track_name": track.get("name"),
                                   "start": round(position, 6), "duration": duration, "clip": item})
                children.append({"OTIO_SCHEMA": "Gap.1", "name": "", "source_range": {
                    "OTIO_SCHEMA": "TimeRange.1",
                    "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 0},
                    "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": duration}}})
                position += duration
                continue
            for reference in (item.get("media_references") or {}).values():
                url = reference.get("target_url") if isinstance(reference, dict) else None
                if not url:
                    continue
                parsed = urllib.parse.urlparse(url)
                original_name = os.path.basename(urllib.parse.unquote(parsed.path))
                if parsed.scheme in ("http", "https"):
                    file_name = media_name(url, original_name)
                    destination = os.path.join(media_dir, file_name)
                    if not os.path.exists(destination):
                        print(f"downloading {url}")
                        try:
                            download(url, destination)
                        except Exception as error:
                            errors.append(f"{url}: download failed ({error})")
                            continue
                else:
                    path = urllib.parse.unquote(parsed.path) if parsed.scheme == "file" else url
                    path = path if os.path.isabs(path) and os.path.exists(path) else os.path.join(root, path.lstrip("/"))
                    if not os.path.isfile(path):
                        errors.append(f"{url}: not found ({path})")
                        continue
                    path = os.path.realpath(path)
                    file_name = media_name(path, original_name)
                    place(path, os.path.join(media_dir, file_name))
                reference["target_url"] = f"media/{file_name}"
            children.append(item)
            position += duration
        track["children"] = children

    otio_path = os.path.join(out, f"{name}.otio")
    with open(otio_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    text_path = os.path.join(out, "text-clips.json")
    if text_clips:
        with open(text_path, "w", encoding="utf-8") as f:
            json.dump(text_clips, f, indent=2)
    elif os.path.exists(text_path):
        os.remove(text_path)

    print(f"\n{out}")
    print(f"  {len(placed)} media file(s) in media/")
    print(f"  {os.path.basename(otio_path)}")
    if text_clips:
        print(f"  text-clips.json: {len(text_clips)} text clip(s) to add back after import")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        sys.exit(1)

    folder = name
    print("\nNext:")
    print(f'  tellers upload upload "{media_dir}" --in-app-path "{folder}" --show-status-until-analysed')
    print(f'  tellers upload upload "{otio_path}" --in-app-path "{folder}"')


if __name__ == "__main__":
    main()
