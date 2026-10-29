# Tellers OTIO format

A Tellers timeline is an [OpenTimelineIO](https://opentimelineio.readthedocs.io) JSON
document (`.otio`) with a few extra metadata keys. Write it as plain JSON; the
`opentimelineio` Python package is not needed.

## Skeleton

```json
{
  "OTIO_SCHEMA": "Timeline.1",
  "name": "my-video",
  "metadata": { "tellers_aspect_ratio": "16_9" },
  "tracks": {
    "OTIO_SCHEMA": "Stack.1",
    "children": [
      { "OTIO_SCHEMA": "Track.1", "name": "Video", "kind": "video", "children": [] },
      { "OTIO_SCHEMA": "Track.1", "name": "Music", "kind": "audio", "children": [] }
    ]
  }
}
```

- `tellers_aspect_ratio`: `"16_9"`, `"9_16"`, `"1_1"`, `"4_5"`, `"4_3"`… (`W_H`, underscore).
  The output frame takes this shape; media that does not match is fitted inside it.
- **Layer order (painter's order):** the first track in `tracks.children` is drawn at
  the bottom, the last one on top. Put the main footage first, overlays (logos, titles,
  subtitles) after it.
- **Sound only comes from `audio` tracks.** A video clip on a `video` track is picture
  only. To hear a video's own sound, put the same file on an audio track with the same
  timing. Audio tracks can go anywhere in the list; keeping them first is the convention.
- Track `kind` is `"video"` or `"audio"`.

## Time

Every time is a `RationalTime.1`: `value / rate` seconds. Using `rate: 1` and seconds as
`value` (decimals allowed) is the simplest and is what Tellers itself writes.

```json
{ "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 2.5 }
```

A clip's `source_range` says which part of the media to play:

```json
"source_range": {
  "OTIO_SCHEMA": "TimeRange.1",
  "start_time": { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 12 },
  "duration":   { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 4 }
}
```

This plays seconds 12→16 of the source. For images and text, `start_time` is 0 and
`duration` is how long they stay on screen.

**There is no "position on the timeline" field.** Children of a track play one after
the other; a clip starts where the previous one ends. To start something later, put a
`Gap.1` before it:

```json
{
  "OTIO_SCHEMA": "Gap.1",
  "source_range": {
    "OTIO_SCHEMA": "TimeRange.1",
    "start_time": { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 0 },
    "duration":   { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 3 }
  }
}
```

Clips on one track never overlap. To overlap two things (picture-in-picture, a title
over footage, music under a voice-over), put them on different tracks.

The timeline lasts as long as its longest track.

## Media clip (video, image, audio)

```json
{
  "OTIO_SCHEMA": "Clip.2",
  "name": "interview",
  "source_range": { "...": "see Time" },
  "media_references": {
    "DEFAULT_MEDIA": {
      "OTIO_SCHEMA": "ExternalReference.1",
      "name": "DEFAULT_MEDIA",
      "target_url": "media/interview.mp4"
    }
  },
  "active_media_reference_key": "DEFAULT_MEDIA",
  "effects": []
}
```

The same shape is used for video, image and audio clips. See **Supported files** below
for exactly what can go in `target_url`.

### Supported files

On a **video track**, the player decides from the URL's extension (query string
ignored) whether the clip is a picture or a video:

| Kind | Extensions | Notes |
| --- | --- | --- |
| Video | `.mp4` `.m4v` `.mov` `.webm` `.mkv` `.ts` | Container read by the player (MP4, QuickTime, Matroska, WebM, MPEG-TS). Picture only; sound comes from an audio track. |
| Image | `.jpg` `.jpeg` `.png` `.webp` `.avif` `.bmp` | Still image, shown for the clip's `duration`. Transparency (PNG, WebP, AVIF) is kept. |
| Animated image | `.gif` everywhere; animated `.webp` / `.avif` where the browser has `ImageDecoder` (Chrome, Edge) | Plays its own animation, looping, for the clip's duration. |
| Vector | `.svg` | Rendered sharp at any size; SMIL / CSS animations play. |
| Unknown or no extension | e.g. a signed URL `…/asset?sig=…` | The player downloads the start of the file and sniffs it. Works, but a URL ending in the real extension avoids the extra probe. |

On an **audio track**: `.mp3`, `.m4a` / `.aac`, `.wav`, `.ogg` / `.opus`, `.flac`, or any
video file above (its first audio track is used; a video with no sound plays silence).

Codecs inside those containers are decoded by the browser (WebCodecs), plus a few
software decoders bundled with the player:

| | Works everywhere (Chrome, Edge, Safari, Firefox) | Depends on the browser / machine | Not supported |
| --- | --- | --- | --- |
| Video | H.264 (AVC), VP8, VP9 | HEVC / H.265 (Safari, and Chrome / Edge with hardware support), AV1 (not on older Safari / Macs), ProRes 422 / 4444 (software, slow for long 4K) | HLS streams (`.m3u8`), `.avi`, `.wmv`, `.flv`, MPEG-2, DNxHD / DNxHR, raw camera formats |
| Audio | AAC, MP3, Opus, Vorbis, FLAC, PCM (WAV) | AC-3 / E-AC-3 (software decoder, loaded on demand) | WMA, DTS |
| Image | JPEG, PNG, WebP, GIF, SVG, BMP | AVIF (not on old browsers), TIFF (Safari only) | HEIC / HEIF (convert to JPEG first), PSD, RAW |

When in doubt, convert to the safe default:

```bash
ffmpeg -i input.mov -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac -b:a 192k -movflags +faststart output.mp4
```

(`-movflags +faststart` puts the index at the start of the file, so playback starts
without reading the whole video.)

**HLS (`.m3u8`) does not play:** the player reads the playlist but never loads its
segments, so the clip stays black (tested with a local and a remote stream). Download
the part you need into an MP4 and use that instead:

```bash
ffmpeg -ss 20 -t 10 -i "https://example.com/stream.m3u8" -c copy media/stream-part.mp4
``` For images: `sips -s format jpeg in.heic --out out.jpg`
on macOS, or `magick in.heic out.jpg`.

Other files a timeline can reference: fonts (`.woff2`, `.woff`, `.ttf`, `.otf`, in
`availableFonts`).

### `target_url`: local or internet

- **Relative URL** (`media/clip.mp4`, `/media/clip.mp4`): resolved against the **HTML
  page's URL**, not against the `.otio` file's location. Simplest layout: page, `.otio`
  and a `media/` folder all in the folder you serve, and URLs like `media/clip.mp4`.
- **Absolute URL** (`https://cdn.example.com/clip.mp4`): fetched directly by the
  browser. The server must send **CORS** headers (`Access-Control-Allow-Origin`) and
  should support **Range** requests, or the clip stays black / silent. Presigned S3 /
  GCS URLs, most CDNs and Pexels videos work; a YouTube page or a Google Drive "share"
  link does not (that is an HTML page, not a media file).
- **Local file paths** (`/Users/me/video.mp4`, `file:///...`) **do not work**: the
  browser cannot read your disk. Copy or symlink the file into the served folder and use
  a relative URL.
- Mixing both in one timeline is fine.

## Text clip

Text is a clip whose media reference is a `Text` generator: a string and a font style.
Put it on its own video track above the footage.

```json
{
  "OTIO_SCHEMA": "Clip.2",
  "name": "Subtitle",
  "source_range": {
    "OTIO_SCHEMA": "TimeRange.1",
    "start_time": { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 0 },
    "duration":   { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 3 }
  },
  "media_references": {
    "DEFAULT_MEDIA": {
      "OTIO_SCHEMA": "GeneratorReference.1",
      "name": "Text",
      "generator_kind": "Text",
      "parameters": {
        "text": "Hello",
        "maxWidth": 0.9,
        "style": {
          "fontFamily": "Inter", "fontWeight": 700, "fontSize": 64, "fill": "#ffffff",
          "dropShadow": { "color": "#000000", "alpha": 0.8, "blur": 8, "distance": 2 }
        }
      }
    }
  },
  "active_media_reference_key": "DEFAULT_MEDIA",
  "effects": [
    { "OTIO_SCHEMA": "Effect.1", "effect_name": "Transform",
      "metadata": { "tellers.ai": { "parameters": { "y": 0.38 } } } }
  ]
}
```

- `parameters`: `text` (`\n` for line breaks), `maxWidth` (0.9, wrap width in frame
  widths), `wrap` (true; false breaks only at `\n`), `style`.
- `style` (defaults): `fontFamily` (`sans-serif`), `fontSize` (64, px), `fontWeight`
  (`normal`, or `700`…), `fontStyle` (`normal` | `italic`), `fill` (`#ffffff`), `align`
  (`center` | `left` | `right`), `lineHeight` (multiple of the font size; 0 = auto),
  `letterSpacing` (px), `stroke` (`{ "color", "width" }`), `dropShadow`
  (`{ "color", "alpha", "blur", "distance", "angle" }`), `background`
  (`{ "mode": "block" | "line" | "word", "color", "opacity", "padding", "radius" }`).
- Sizes are px in a 1080-pixel-tall reference frame and scale with the output.
- The text is centered in the frame. Move it with a `Transform` effect (`y: 0.38` puts
  a subtitle near the bottom); fades, pops and slides of the whole text are `Transform`
  keyframes. Animate letters and words with the **Text animation** effects below.
- One clip has one style: for a word in another color, use a second clip or a
  `TextColor` / `TextKaraoke` effect.

### Fonts

Declare web fonts once in the timeline metadata, then use the `family` as `fontFamily`:

```json
"metadata": {
  "tellers_aspect_ratio": "16_9",
  "tellers.ai": {
    "availableFonts": [
      { "family": "Inter", "url": "https://cdn.jsdelivr.net/npm/@fontsource/inter@5.1.1/files/inter-latin-700-normal.woff2", "weight": "700", "style": "normal" }
    ]
  }
}
```

Font URLs must be `https:`/`http:`/`data:` and allow CORS (a local font served by
`serve.py` works). Only fonts actually used are downloaded.

## Effects

Effects follow the conventions of
[tellers-timeline](https://github.com/tellers-ai/tellers-timeline) (the timeline engine
Tellers uses; `pip install tellers-timeline` if you want to build or edit timelines with
it instead of writing JSON by hand). An effect is an OTIO `Effect.1` in the `effects`
list of a **clip**, a **track** (applies to every clip of the track), or the **root
stack** `tracks` (applies to the whole composited picture / mix):

```json
"effects": [
  {
    "OTIO_SCHEMA": "Effect.1",
    "name": "soft focus",
    "effect_name": "Blur",
    "enabled": true,
    "metadata": { "tellers.ai": { "parameters": {
      "strength": { "keyframes": [ { "t": 0, "v": 0, "ease": "easeOut" }, { "t": 1.5, "v": 8 } ] },
      "quality": 4
    } } }
  }
]
```

- **`effect_name`: write the bare name** (`"Blur"`). tellers-timeline names its effects
  `tellers.ai.Blur`, but the player matches the bare name only (as of 2026-10-19), and
  tellers-timeline reads the bare name and adds the prefix when it next writes the
  effect. A prefixed or unknown name is silently skipped by the player.
- `enabled: false` turns an effect off without removing it; absent means on.
- `name` is a free display label.
- Parameters live under `metadata["tellers.ai"].parameters`. A missing parameter takes
  its default (table below), so `{}` is a valid "defaults" effect.
- **Every numeric parameter can be animated**: a number, or
  `{ "keyframes": [ { "t": <s>, "v": <value>, "ease": "<curve>" } ] }`. `t` is seconds
  from the **start of the clip on the timeline** (not media time). Before the first and
  after the last keyframe the value holds. `ease` is the curve to the *next* keyframe:
  `linear` (default), `hold`, `easeIn`, `easeOut`, `easeInOut`. Colors, presets, modes
  and booleans are fixed values.
- Lengths marked *px* are in a 1080-pixel-tall reference frame and scale with the output
  (like text). Positions marked *frac* are fractions of the clip's box.

### Picture effects (video tracks)

| `effect_name` | Parameters (default) |
| --- | --- |
| `Transform` | `x` (0), `y` (0): offset in frame widths / heights, `+y` is down; `scale` (1), `scaleX` (1), `scaleY` (1); `rotation` (0, degrees); `opacity` (1, 0–1). Adds to the Resolve `Transform` below when both are present. |
| `Blur` | `strength` (8, px), `quality` (4, passes) |
| `Pixelate` | `size` (10, px block) |
| `Adjustment` | `gamma`, `saturation`, `contrast`, `brightness`, `red`, `green`, `blue`, `alpha` (all 1 = unchanged, ≥ 0) |
| `ColorMatrix` | `preset`: `sepia` `vintage` `polaroid` `kodachrome` `technicolor` `browni` `lsd` `blackAndWhite` `negative` `desaturate`; `hue` (0, degrees); `amount` (1, 0–1 mix) |
| `HslAdjustment` | `hue` (0), `saturation` (0), `lightness` (0), `colorize` (0; ≥ 0.5 = on), `amount` (1) |
| `Noise` | `amount` (0.15, 0–1), `speed` (24 changes/s; 0 = static), `seed` (0) |
| `RGBSplit` | `amount` (6, px), `angle` (0, degrees) |
| `ZoomBlur` | `strength` (0.1), `centerX` / `centerY` (0.5, frame fraction), `innerRadius` (0, px) |
| `DropShadow` | `offsetX` / `offsetY` (8, px), `blur` (4, px), `alpha` (0.5), `color` (`#000000`) |
| `ChromaKey` | `color` (`#00ff00`), `similarity` (0.5), `smoothness` (0.2), `spill` (1, 0–1), `choke` (1, px) |
| `Border` | `width` (8, px; default for every side), `top` / `right` / `bottom` / `left` (px), `color` (`#ffffff`), `opacity` (1) |
| `MotionBlur` | `shutterAngle` (180, 0–720 degrees), `shutterPhase` (−angle/2), `samples` (16, 2–32). Blurs moving `Transform`s. |
| `Blend` | `mode`: `normal` `add` `screen` `lighten` `multiply` `darken` `overlay` `soft-light` `hard-light` `difference` |
| `Mask` | `shape`: `rectangle` (default) `ellipse` `path`; `x` / `y` (0, offset from the center, *frac*); `width` / `height` (1, *frac*); `rotation` (degrees); `corner_radius` (px); `feather` (px); `opacity` (1); `invert` (false); `mode`: `add` `subtract` `intersect`; for `path`, `points`: `[[x, y], …]` or `{x, y, in_x, in_y, out_x, out_y}` bezier points (*frac*, each animatable) and `closed` (true). Several masks combine in list order. |
| `TrackMatte` | `mode`: `alpha` `luma` `alpha_inverted` `luma_inverted`; `track`: name or id of the track whose picture is the matte |
| `ColorLut` | `.cube` LUT, see **Color grading** below |

Stage order for the same picture: the clip's effects, then its track's, then the root
stack's (whole frame, text included).

### Detect a subject (`detect`)

A filter (`Blur`, `Pixelate`, `Adjustment`, `ColorMatrix`, …) or a `Mask` on a **clip**
can name a subject to find instead of drawn shapes, e.g. `"detect": { "target": "faces" }`
in a `Blur`'s parameters. On load the player detects `target` (`faces`, `people`,
`animals`, `vehicles`, or a COCO category such as `car` or `dog`) over the clip and
fills in the filter's `regions` or the `Mask`'s shape. Optional keys: `pick`
(`{ "t", "x", "y" }`, the subject at that clip time and position), `shape`
(`rectangle`, `ellipse`, or `outline` for the subject's exact contour as a keyframed
`path`) and the model settings (`objectModel`: `fast` | `accurate`, `faceModel`:
`short` | `full`). Full reference:
[tellers-timeline `docs/otio-reference.md#detect`](https://github.com/tellers-ai/tellers-timeline/blob/main/docs/otio-reference.md#detect).

> **`detect` and `shape: "outline"` need a GPU.** Detection runs in the viewer's
> browser, on the machine opening the player. Without a GPU (or with WebGPU / WebGL
> off) it falls back to the CPU and can take a long time, and slow down playback while
> it runs. `outline` and the `accurate` / `full` models are the heaviest. On a machine
> without a GPU, warn the user before using them, prefer drawn `Mask` shapes or
> `regions`, or keep `detect` to short clips with the `fast` model and a rectangle or
> ellipse.

### Sound effects (audio tracks)

| `effect_name` | Parameters (default) |
| --- | --- |
| `Volume` | `volume` (0, dB; `-12` quieter, animatable for ducking); `fadeIn` / `fadeOut` (seconds, fixed numbers) |
| `Pan` | `pan` (0; −1 left … 1 right) |

On a track, `Volume` / `Pan` apply on top of each clip's own.

### Speed

| `effect_name` | Parameters |
| --- | --- |
| `TimeWarp` | `speed` (0.25–4, or −4 to −0.25 to play backwards; animatable for a speed ramp; 2 = twice as fast; 0 = freeze on the first frame). Pitch is kept; set `"preserve_pitch": false` in `metadata["tellers.ai"]` (beside `parameters`) to let it shift. |

The clip keeps its `source_range.duration` **on the timeline**; the speed changes how
much media it plays in that time, starting at `source_range.start_time`. A 5 s clip at
`speed: 2` lasts 5 s and plays 10 s of media; a keyframed speed plays the integral of
the curve. Make sure `start_time` + that much media stays inside the file, plus any
transition handle. Keyframes must all have the same sign (a curve cannot cross zero).
OTIO `LinearTimeWarp.1` (`time_scalar`) and `FreezeFrame.1` are read too.

### Text animation (text clips)

| `effect_name` | Parameters (default) |
| --- | --- |
| `TextTypewriter` | `progress` (0–1, letters shown; default runs over the clip) |
| `TextWordReveal` | `progress`; `style`: `fade` `appear` `pop` `slideUp` |
| `TextKaraoke` | `progress`; `scale` (1) and `color` (`#ffd400`) of the active word |
| `TextWave` | `amplitude` (0.015, frame heights), `speed` (1, cycles/s), `wavelength` (8 letters) |
| `TextColor` | `colors` (CSS colors, cycled), `period` (1 s per color), `position` (overrides the cycle) |

### Resolve transform, crop and volume

The DaVinci Resolve encodings tellers-timeline also reads and writes (and Resolve
imports) still work, as `effect_name: "Resolve Effect"` with the data under
`metadata.Resolve_OTIO`:

```json
"effects": [
  {
    "OTIO_SCHEMA": "Effect.1",
    "name": "",
    "effect_name": "Resolve Effect",
    "metadata": {
      "Resolve_OTIO": {
        "Effect Name": "Transform", "Name": "Transform", "Enabled": true, "Type": 2,
        "Parameters": [
          { "Parameter ID": "transformationZoomX", "Parameter Value": 0.35 },
          { "Parameter ID": "transformationZoomY", "Parameter Value": 0.35 },
          { "Parameter ID": "transformationPan",   "Parameter Value": 0.3 },
          { "Parameter ID": "transformationTilt",  "Parameter Value": -0.3 },
          { "Parameter ID": "transformationRotationAngle", "Parameter Value": 0 }
        ]
      }
    }
  },
  {
    "OTIO_SCHEMA": "Effect.1",
    "name": "",
    "effect_name": "Resolve Effect",
    "metadata": {
      "Resolve_OTIO": {
        "Effect Name": "Cropping", "Name": "Cropping", "Enabled": true, "Type": 2,
        "Parameters": [
          { "Parameter ID": "cropLeft",   "Parameter Value": 0.1 },
          { "Parameter ID": "cropRight",  "Parameter Value": 0.1 },
          { "Parameter ID": "cropTop",    "Parameter Value": 0 },
          { "Parameter ID": "cropBottom", "Parameter Value": 0 }
        ]
      }
    }
  }
]
```

| Parameter | Meaning |
| --- | --- |
| `transformationZoomX` / `ZoomY` | scale; `1` = media fitted to the frame, `0.35` = 35% of that |
| `transformationPan` | horizontal offset in frame widths: `-0.5` left edge … `0` center … `0.5` right edge |
| `transformationTilt` | vertical offset in frame heights: `-0.5` top edge … `0` center … `0.5` bottom edge (positive is **down**) |
| `transformationRotationAngle` | degrees |
| `cropLeft` / `Right` / `Top` / `Bottom` | fraction of the media removed from that side, `0`–`1` |

The example puts a clip at 35% size in the top-right quarter (picture-in-picture).
Crop exists only in this form. For position / size use either form; the tellers
`Transform` is the one to use when it must be animated or faded (`opacity`).

Audio clip level, Resolve form (dB, max `+30`):

```json
{
  "OTIO_SCHEMA": "Effect.1",
  "name": "",
  "effect_name": "Resolve Effect",
  "metadata": {
    "Resolve_OTIO": {
      "Effect Name": "Fairlight Clip Volume and Fades", "Name": "Fairlight Clip Volume and Fades",
      "Enabled": true, "Type": 2,
      "Parameters": [ { "Parameter ID": "volume", "Parameter Value": -12 } ]
    }
  }
}
```

## Color grading (`ColorLut`)

A `.cube` LUT, on a video or image clip, a video track or the root stack (graded in
that order; text is graded only at the stack):

```json
{
  "OTIO_SCHEMA": "Effect.1",
  "name": "film-look.cube",
  "effect_name": "ColorLut",
  "metadata": { "tellers.ai": {
    "asset_id": "film-look",
    "cube_url": "media/film-look.cube",
    "parameters": { "cube_url": "media/film-look.cube" }
  } }
}
```

`asset_id` is what Tellers stores; `cube_url` is where the file is downloaded from (same
rules as `target_url`). tellers-timeline now writes `cube_url` inside `parameters`; the
player still reads it beside `parameters`, so write both. Without a `cube_url` the LUT is
skipped.

## Transitions

An OTIO `Transition.1` between two items of a track overlaps them by `in_offset`
(before the cut) + `out_offset` (after it). It takes no time of its own: do not add its
duration to the track.

```json
{
  "OTIO_SCHEMA": "Transition.1",
  "name": "",
  "transition_type": "SMPTE_Dissolve",
  "in_offset":  { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 0.5 },
  "out_offset": { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 0.5 },
  "metadata": { "tellers.ai": { "parameters": { "direction": "left" } } }
}
```

`transition_type` (case and punctuation ignored): `SMPTE_Dissolve` / `Dissolve`,
`DipToBlack`, `DipToWhite`, `DipToColor` (with `parameters.color`), `Wipe`, `Push`,
`Slide`, `Zoom`. `direction` (`left` `right` `up` `down`) is for wipe, push and slide.
Both neighbours need enough media beyond the cut to cover the offsets.

## Markers

Notes on the edit, plain OTIO `Marker.2` in the `markers` list of the root stack (timeline
time), a track (timeline time) or a clip (its **media** time, so the marker follows the
clip):

```json
"markers": [
  {
    "OTIO_SCHEMA": "Marker.2",
    "name": "Fix color",
    "comment": "Too warm compared to the previous shot",
    "color": "RED",
    "marked_range": {
      "OTIO_SCHEMA": "TimeRange.1",
      "start_time": { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 12 },
      "duration":   { "OTIO_SCHEMA": "RationalTime.1", "rate": 1, "value": 0 }
    }
  }
]
```

`color`: `PINK` `RED` `ORANGE` `YELLOW` `GREEN` `CYAN` `BLUE` `PURPLE` `MAGENTA` `BLACK`
`WHITE`. Duration `0` is a point marker.

## Ids and Tellers info (`metadata["tellers.ai"]`)

Optional when writing a timeline by hand; Tellers fills in what is missing on import.
These are the keys tellers-timeline reads and writes:

| Where | Key | Meaning |
| --- | --- | --- |
| clip, gap, track, marker | `timeline_id` | Stable id (any string, unique in the timeline). Keep it when editing a timeline that came from Tellers. |
| media reference | `media_id` | Tellers asset id of the media; how `pull_from_tellers.py` finds the file. |
| track, marker | `created_by` | `"auto"` on tracks the engine created (pruned when empty); the user id on markers. |
| clip | `Tellers Group ID` | Number shared by clips edited as one group. |
| clip, `metadata.Resolve_OTIO` | `Link Group ID` | Number shared by a video clip and its sound clips on audio tracks, so they move and trim together. |
| timeline | `availableFonts` | See **Fonts**. |

A video with its own sound is two clips (video track + audio track) with the same timing;
giving both the same `Link Group ID` keeps them linked once the timeline is in Tellers:

```json
"metadata": { "Resolve_OTIO": { "Link Group ID": 1 } }
```

## Checklist before opening the player

1. Valid JSON (`python3 -m json.tool timeline.otio > /dev/null`).
2. Every `source_range` has both `start_time` and `duration`.
3. Footage first, overlays after; sound on `audio` tracks.
4. Every relative `target_url` exists under the served folder; every remote one answers
   with CORS. `scripts/check_otio.py` checks all of this.
5. Any `detect` (above all `shape: "outline"`): the machine opening the player has a
   GPU, or the user knows detection will be slow.
