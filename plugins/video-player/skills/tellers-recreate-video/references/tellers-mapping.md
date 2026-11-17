# Tellers integration

Read the current `video-player/references/otio-format.md` before building. The mappings below were checked against tellers-ai/skills commit c2785c53a8e089f6c90b6dac27819c2903db0ed0; live schemas take precedence.

| Observed feature | Tellers representation |
| --- | --- |
| Shot/cut | Media `Clip.2`, source range; adjacent clips for hard cuts |
| Delayed overlay | `Gap.1` followed by a clip; another track for overlap |
| Text/caption | `GeneratorReference.1` with `generator_kind: Text`; plain text |
| Position, scale, opacity | `Transform`; numeric keyframes with clip-local `t` |
| Type-on / word highlight | `TextTypewriter`, `TextWordReveal`, `TextKaraoke` |
| Artwork / diagram / logo | SVG media; separately layered objects when needed |
| Mask / foreground occlusion | `Mask`, `TrackMatte`; optional local `detect` |
| Motion blur | `MotionBlur` for moving transforms; verify actual render |
| Grade / grain | `Adjustment`, `ColorLut`, `Noise` |
| Dissolve / wipe | `Transition.1` with valid media handles |
| Audio | Explicit audio track locally; check cloud auto-linked audio |
| Retiming | `TimeWarp`; ensure required source duration exists |

Timing: use rational source rates for measurements and retain integer frame indexes. OTIO time is value/rate; compute boundary times without rounding to milliseconds. VFR boundaries require actual PTS. Keep end times exclusive. Keyframe `t` is relative to clip start on the timeline. A TimeWarp clip retains its timeline duration while source consumption changes.

Geometry: the first track is the bottom layer. Text font sizes and effect lengths are in a 1080-high reference frame: a measured height of h pixels at source height H corresponds to h*1080/H reference pixels. Transform x/y are center-relative frame fractions; a desired center (cx,cy) maps to cx/W-0.5, cy/H-0.5 for a full-frame item. Verify raster text ink bounds: fontSize is not glyph ink height. Crop uses the documented Resolve effect encoding; Mask hides regions and does not automatically reframe a crop. Check aspect-fit behavior for non-full-frame media.

Local audio: video tracks are silent; add the source on an audio track exactly once. If preserving the complete source soundtrack, mute/omit per-shot audio. Cloud patches may auto-create bound audio when inserting a video: reread and mute these when a master soundtrack exists. Do not silently discard offsets or an audio tail; distinguish reference-video duration from container/audio duration.

Detection: local `detect` and outline masks depend on the viewer's browser/GPU. Prefer manual masks for simple geometry. Generated object masks require checking edges, occlusion and tracking drift; do not claim segmentation succeeds solely because the property validates.

Export: read the installed player's supported export options. Do not invent FPS or canvas-size fields. Verify the rendered file with ffprobe; disclose any export-rate/resolution limitation, especially NTSC or nonstandard aspect ratios. A JSON validator cannot prove renderer fidelity. Preserve local text when transferring: inspect the transfer helper because its current preparation can remove text clips; do not claim a lossless transfer without checking the imported timeline.

Cloud tool names documented in `tellers-mcp` include `tellers_detect_video_cuts`, `tellers_get_transcript`, `tellers_assets_get_description`, `tellers_video_analyse_gemini`, `tellers_get_audio_beats`, `tellers_get_llm_optimized_timeline`, `tellers_timeline_apply_patch` and `preview_project`. These are discovery hints, not callable schemas. If paid Gemini analysis is useful, request shot composition/actions, visible text, transitions and confidence; independently measure exact event times. Reuse available indexing first.
