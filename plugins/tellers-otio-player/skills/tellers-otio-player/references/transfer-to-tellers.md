# Transfer a local edit to Tellers with the CLI

Turns a local `timeline.otio` and its media into a Tellers project, with the
[Tellers CLI](https://github.com/tellers-ai/tellers-cli). The CLI has no "create
project" command; the project is created by Tellers itself:

1. Upload the media files. Each becomes an asset in the user's library.
2. Upload the `.otio`. Tellers reads it as an edit, looks up every clip's media **by file
   name** among the user's assets and, when every clip is found, creates a project
   from the timeline automatically (named after the timeline's `name`).

So the order matters (media first), and the file names in the timeline must match the
uploaded files.

## Requirements

- The Tellers CLI, signed in:

  ```bash
  brew tap tellers-ai/tellers && brew install tellers
  tellers login            # or: export TELLERS_API_KEY=sk_...
  ```

- **A CLI that sends each file's original path** (tellers-ai/tellers-cli#51 and later).
  The lookup compares clip file names with the `original_file_path` stored on each
  asset. Older builds upload the media fine, but the timeline then finds none of it: the
  `.otio` is stored as an edit without becoming a project. If that happens, update the
  CLI (`brew upgrade tellers`) and upload the media again with `--force-upload`, or open
  the `.otio` in app.tellers.ai and link the sources there.

## 1. Prepare a transfer folder

```bash
python3 "$SKILL_DIR/scripts/prepare_transfer.py" my-edit/timeline.otio
```

It writes `my-edit/tellers-transfer/`:

| Output | Why |
| --- | --- |
| `media/<name>__<file>` | Every file the timeline uses, once. Remote `https://` media is **downloaded**: Tellers can only link a clip to a file it holds. The `<name>__` prefix keeps names from colliding with same-named files already in the account (two equal candidates and the import stops to ask). |
| `<name>.otio` | The timeline with every `target_url` rewritten to `media/<file>`. |
| `text-clips.json` | Text clips, taken out and replaced by gaps of the same length. They have no media file, so the importer would mark them as missing and the project would not be created. Each entry has the track, start time, duration and the full clip, to add back later. |

Options: `--out DIR`, `--prefix NAME`, `--no-prefix`, `--root FOLDER` (where relative
URLs resolve, default the `.otio`'s folder). It ends by printing the two upload commands.

Check the result plays before uploading: serve `tellers-transfer/` with `serve.py` and
open `player.html?otio=<name>.otio` (copy `player.html` in).

## 2. Upload the media

```bash
tellers upload upload my-edit/tellers-transfer/media --in-app-path "my-edit" --show-status-until-analysed
```

- `--in-app-path` is the folder the files land in, in the Tellers library.
- `--show-status-until-analysed` waits until Tellers has processed them. Uploading the
  timeline before the media exists in the library means nothing matches.
- Add `--disable-description-generation` to skip AI descriptions of the footage (faster,
  no credits), `--dry-run` to list what would be uploaded.
- Files already uploaded from the same path are skipped (tracked in
  `~/.tellers/uploads.json`); `--force-upload` re-sends them.

Note: the subcommand really is `tellers upload upload <path>`.

## 3. Upload the timeline

```bash
tellers upload upload my-edit/tellers-transfer/my-edit.otio --in-app-path "my-edit"
```

Tellers recognises `.otio` (also `.aaf`, `.edl`, FCP7 `.xml`) as an edit. When every
clip's file is found, the project appears in the projects list at
https://app.tellers.ai, named after the timeline. When some are not found (or are
ambiguous), the edit waits in the library: open it in the app to pick the right file
for each missing source, then convert it.

## 4. Add the text back

Get the new project's id (from its URL in the app, `?project_id=…`). Then either:

- in the app, add the titles by hand, using `text-clips.json` for timings and text; or
- with the Tellers MCP (`tellers-mcp` skill): read the timeline with
  `get_project_timeline`, and insert each clip from `text-clips.json` on a text track at
  its `start` with `tellers_timeline_apply_patch`; then `preview_project`.

## 5. Check

`preview_project` (MCP) or the app's player. Clips whose file was not linked show as
missing media; re-link them in the app.

## Going the other way

To bring a Tellers project back to local files, use `scripts/pull_from_tellers.py`. It
downloads every asset the timeline uses and rewrites the `.otio` to point at them.

1. Get the project's timeline and save it as JSON, e.g. `project.otio`: the MCP's
   `get_project_timeline` (stored timeline) or `preview_project` (its structured
   `otio`, signed URLs) both work. Clips carry their asset id in the media reference
   metadata (`media_id` or `metadata["tellers.ai"].media_id`), which is what the script
   reads; the `target_url`s in the file do not matter.
2. Run it, signed in to the CLI (`tellers login`) or with `TELLERS_API_KEY` set:

   ```bash
   python3 "$SKILL_DIR/scripts/pull_from_tellers.py" project.otio --out my-edit
   ```

   It writes `my-edit/media/<clip>-<id>.<ext>` (each asset once, group clips included)
   and `my-edit/<name>.otio` with every `target_url` set to `media/<file>`. Text clips are
   kept. Clips with no asset id but an `https://` URL (stock) are downloaded from it.
   Re-running skips files already in `media/` (`--force` downloads again).

3. Copy `player.html` in, serve with `serve.py`, open `player.html?otio=<name>.otio`.

`--rendition` picks the file per asset:

| Value | File |
| --- | --- |
| `compatible` (default) | The original upload when the player can decode it, otherwise the highest player-compatible rendition. Always plays. |
| `original` | The uploaded file as is, e.g. for a finishing tool. May not play in the browser (ProRes, DNxHD, MXF…). |
| `highest`, `1080p`, `720p`, `480p`, `lowest` | Player-compatible rendition of that size (lighter proxies). |

Single assets can also be fetched with `tellers asset download <asset-id> --quality
original --output media/<file>`.
