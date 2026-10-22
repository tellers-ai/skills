---
name: tellers-otio-player
description: Build and preview a video edit locally with the Tellers player — write a Tellers OTIO timeline (.otio) that cuts, layers, titles and mixes local files and/or internet media URLs, embed the Tellers player (one <script> from tellers.ai) in an HTML page, and serve the folder on localhost so the user can play, scrub and export the result to MP4 (or the agent exports it into the folder itself). Also covers transferring the edit to Tellers with the Tellers CLI (upload media and .otio, project recreated), and pulling a Tellers project back to local files (media downloaded, .otio rewritten). Use when the user wants to assemble or preview a video from clips on their machine or from URLs, play or inspect an existing .otio file, embed the Tellers player in a web page, or asks to "make a video / montage / edit" without the Tellers MCP. No Tellers account is needed.
---

# Tellers OTIO player (local)

Everything runs on the user's machine: a folder with an HTML page, a timeline
(`.otio`) and media, served on `http://localhost`. The player is one
script, `https://tellers.ai/videoplayer/bundle.js`, so nothing is installed
(internet is needed to load it). No Tellers account,
no upload. For editing projects stored in Tellers, use the `tellers-mcp` skill instead.

Files in this skill (paths relative to this SKILL.md):

| File | What it is |
| --- | --- |
| `assets/player.html` | Ready-made full-page player (play / seek / export / fullscreen): `player.html?otio=<url>`; `exportToFolder()` saves an export into the folder |
| `assets/example.otio` | Example timeline: remote video, local clip, logo overlay, titles, music |
| `scripts/serve.py` | Local web server with Range + CORS, and `POST /exports/<name>` to save exports (Python 3, no dependencies) |
| `scripts/check_otio.py` | Validates a timeline and every media URL in it |
| `scripts/prepare_transfer.py` | Builds an upload folder to recreate the edit as a Tellers project with the CLI |
| `scripts/pull_from_tellers.py` | Downloads a Tellers project's media (original or player-compatible rendition) and rewrites its `.otio` to the local files |
| `references/otio-format.md` | **The timeline format** (effects, transitions, markers and ids follow [tellers-timeline](https://github.com/tellers-ai/tellers-timeline)). Read it before writing or editing an `.otio`. |
| `references/transfer-to-tellers.md` | Upload the edit with the Tellers CLI and recreate it as a Tellers project |

## Workflow

### 1. Set up the project folder

Use the folder the user points to, or create one (e.g. `~/Videos/my-edit`). Layout:

```
my-edit/
  player.html            <- copy of assets/player.html
  timeline.otio          <- the edit
  media/                 <- local videos, images, audio, fonts
```

```bash
SKILL_DIR="<directory of this SKILL.md>"
mkdir -p my-edit/media
cp "$SKILL_DIR/assets/player.html" my-edit/
```

Bring local media **into** the folder (`cp`, or `ln -s` for big files). The browser can
only read what the server serves; `/Users/...` or `file://` paths in a timeline never
work.

Get each file's duration (and size) before cutting, so `source_range` stays inside the
media:

```bash
ffprobe -v error -show_entries format=duration:stream=width,height -of default=nw=1 media/clip.mp4
```

(If `ffprobe` is missing, ask the user or use `mdls -name kMDItemDurationSeconds` on macOS.)

### 2. Write the timeline

Read `references/otio-format.md`, then write `timeline.otio` (JSON). Start from
`assets/example.otio` when it helps. The rules that matter most:

- Track order is painter's order: first track = bottom layer. Footage first, overlays
  and text after.
- Clips on a track play back to back. Use `Gap.1` to delay something; use another
  track to overlap.
- Sound comes only from `audio` tracks. To keep a video's own sound, put the same
  file with the same `source_range` on an audio track.
- `target_url` is either relative to the page (`media/clip.mp4`) or an absolute
  `https://` URL to the media file itself, served with CORS.
- Supported files (details in `references/otio-format.md`, Supported files): video
  `.mp4 .mov .m4v .webm .mkv .ts` (H.264 / VP9 everywhere; HEVC, AV1, ProRes
  depend on the browser); images `.jpg .png .webp .avif .gif .svg .bmp`; audio
  `.mp3 .m4a .aac .wav .ogg .opus .flac`. Not supported: HLS `.m3u8`, `.avi`, `.wmv`,
  HEIC, DNxHD — convert with ffmpeg first.

For a timeline with many clips, generate the JSON with a short Python script rather
than writing it by hand.

### 3. Check it

```bash
python3 "$SKILL_DIR/scripts/check_otio.py" my-edit/timeline.otio
```

Fix every `ERROR` (missing files, disk paths, remote URLs without CORS, missing
ranges). It also prints each track's end time, a quick way to confirm the cut.

### 4. Serve and open

```bash
python3 "$SKILL_DIR/scripts/serve.py" my-edit --port 8000
```

Run it in the background (it keeps running), then open
`http://localhost:8000/player.html?otio=timeline.otio` — in the user's browser, or in
your own browser tool to verify it plays. Tell the user the URL.

Why a server and not double-clicking the HTML: the player fetches the timeline and
media and runs workers, which browsers block on `file://`. `localhost` also counts as a
secure context, which WebCodecs requires. `serve.py` answers Range requests (fast
seeking in long videos) and disables caching, so an edited `.otio` is always picked up (see
step 5 for when to call `ui.loadUrl` and when to reload). `python3 -m http.server` also works but ignores Range: every video is
downloaded in full before it can seek.

To try a different player build, add `&src=<url of bundle.js>` to the page URL.

If port 8000 is taken, use `--port 8001`. To watch it from a phone on the same network,
`--host 0.0.0.0` and open `http://<computer-ip>:8000/...` (WebCodecs needs a secure
context, so prefer the computer's browser).

### 5. Iterate and export

Edit `timeline.otio` and re-run the check. Then refresh the player depending on the change:

- **Update to the same edit** (move, trim, retime, restyle, add or remove clips or
  text in this `timeline.otio`): don't reload. Call `await ui.loadUrl("timeline.otio")`
  in the page (in your browser tool, run it as JavaScript in the player tab; or tell the
  user to run it in the console). The player swaps the timeline in place and keeps the
  page.
- **Different timeline** (switching to another `.otio`, another project, or starting a
  new edit): reload the page with the new `?otio=` URL, so the player starts fresh.

The Export button in the
player's control bar renders the timeline to MP4 in the browser and saves it through
the browser's save dialog. Chrome or Edge give the best results; Safari and
Firefox have partial WebCodecs support.

**Export to the project folder yourself** (no dialog, no click): `assets/player.html`
has `exportToFolder(name, options)`. It renders with `ui.export({ save: "none" })` and
POSTs the file to `serve.py`, which writes it to `<served folder>/exports/<name>`. In
your browser tool, run it as JavaScript in the player tab. Don't `await` it: a long
export outlasts one JavaScript call. Start it, then poll `window.exportStatus`:

```js
exportToFolder("edit.mp4", { resolution: 1080 });   // start, returns at once
window.exportStatus   // { state: "exporting", progress: 0.42, phase } … then
                      // { state: "done", path: "exports/edit.mp4", bytes } or { state: "error", error }
```

- `name` sets the format from its extension (`.mp4`, `.webm`, `.png` / `.jpg` for one
  frame at `time`, `.mp3`, `.aac`); `options` are `ui.export`'s (`resolution`,
  `startTime`, `endTime`, `time`).
- The export renders in that browser tab, on that machine: keep the tab open (a
  background tab can slow it down), and expect long or 4K exports to take a while.
- `serve.py` accepts it only from a page on localhost (not with `--host 0.0.0.0` from
  another device), only under `exports/`, and only export file types. It overwrites a
  file of the same name.
- In your own page, do the same by hand: `const { url } = await ui.export({ format:
  "mp4", save: "none" })`, then `fetch("/exports/edit.mp4", { method: "POST", body:
  await (await fetch(url)).blob() })`.

## Embedding the player in another page

Any page, on any site, can include the player with one `<script>` tag. It is a single
self-contained file (workers, codecs and assets inlined) and brings its own controls:

```html
<div id="player" style="width: 960px; aspect-ratio: 16 / 9"></div>
<script src="https://tellers.ai/videoplayer/bundle.js"></script>
<script>
  const ui = TellersPlayerUI.mount(document.getElementById("player"), {
    otioUrl: "timeline.otio",   // or  otio: { ...timeline object... }
    title: "My edit",           // shown over the picture
    tellersLink: { variant: "powered" }, // small "Powered by Tellers" badge; false hides it
    export: { format: "mp4", resolution: 1080, save: "picker" }, // or false to hide Export
  });
</script>
```

The container must have a size; the player fills it and letterboxes the timeline's
aspect ratio. The page itself still has to be served over http(s) (not `file://`), and
the timeline's media URLs resolve against the page. The player only runs on the
hostnames its build allows (by default `tellers.ai` and `localhost`); on another site
it throws when mounted.

`mount()` returns a controller:

| Member | Use |
| --- | --- |
| `ui.load(otioObject, title?)` | Replace the timeline with a JS object (e.g. built in the page) |
| `ui.loadUrl(url, title?)` | Replace it with a timeline fetched from a URL. Use it to refresh after editing the same `.otio` (step 5) |
| `ui.export({ format, resolution, filename, save, time, startTime, endTime, onProgress })` | `format`: `mp4`, `webm`, `png`, `jpeg` (frame at `time`), `mp3`, `aac`. `save`: `"picker"` (must run in a click handler), `"download"`, or `"none"` (returns `{ url }`, a blob URL) |
| `ui.cancelExport()` | Stop a running export |
| `ui.toggleFullscreen()` | Same as the button |
| `ui.player` | The underlying `VideoPlayer`: `play()`, `pause()`, `seek(seconds)`, `currentPlaybackTime`, `totalPlaylistDuration`, `isPlaying` |
| `ui.destroy()` | Remove the player and free its decoders |

`tellersLink` sets the Tellers badge: `{ variant: "powered" }` (what `assets/player.html`
uses) shows a small "Powered by Tellers" badge above the control bar; `{ variant: "view" }`
(the default when the option is left out) shows a "View on Tellers.ai" button in the
top-right corner; `{ projectId }` or `{ url }` sets where it links; `false` hides it.

Other mount options: `playerOptions` (passed to the `VideoPlayer` constructor, e.g.
`{ renderScale: "auto" }` for slow machines), `onFullscreenRequest`,
`onFullscreenChange`.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Page says to use a local server | Opened as `file://`. Run `serve.py`. |
| "Could not load the player" | tellers.ai unreachable (offline, or blocked by a proxy). Pass `&src=` with a local build of `bundle.js`. |
| Player throws when mounted on your site | The build's hostname allowlist does not include that site. |
| Timeline does not load | `?otio=` URL wrong (it is relative to the page), or invalid JSON: run `check_otio.py`. |
| A clip stays black / silent | `target_url` 404, a disk path, or a remote URL without CORS. Check the browser console and `check_otio.py`. |
| No sound from a video | Video tracks are picture only; add the file to an audio track. |
| Text in the wrong place | Text is laid out on a 1920×1080-area box (`references/otio-format.md`, Text clip). |
| Choppy playback | Many 4K layers at once. Pass `playerOptions: { renderScale: "auto" }`, or use lighter proxies. |

## Transferring the edit to Tellers

To turn the local edit into a Tellers project, use the Tellers CLI: upload the media,
then upload the `.otio`, and Tellers creates the project by matching file names.
`scripts/prepare_transfer.py` builds the upload folder (collects and downloads media,
gives files unique names, takes text clips out). Follow
`references/transfer-to-tellers.md` step by step.

The other way, a Tellers project to local files: save its timeline (MCP
`get_project_timeline`) and run `scripts/pull_from_tellers.py project.otio --out
my-edit`. It downloads each asset, the original when the player can decode it, else the
best compatible rendition (`--rendition original` for the untouched upload), and writes
`my-edit/<name>.otio` pointing at `media/`. Details in
`references/transfer-to-tellers.md`, Going the other way.

## Going further with Tellers

The same `.otio` format is what Tellers uses. To get AI editing on top (search inside
footage, transcripts, generated voice/music/video, cloud rendering, sharing), the user
can connect the Tellers MCP — see the `tellers-mcp` skill.
