# Reference analysis and verification

## Local helper

Install dependencies in the project's existing environment when needed: Python 3, Pillow, NumPy, FFmpeg and ffprobe. The helper does not download media/models or call any API. Use local video paths; obtain URL media through authorized service tools first.

`analyze` reads all video frame timestamps and runs FFmpeg's scene-score detector. It produces `probe.json`, `frame-times.json`, `cut-candidates.json`, individual preview frames and `contact-sheet.jpg`. Scene detection is a heuristic: jump cuts, punch-ins and low-contrast cuts may be missed; flashes and large graphics may be false positives. Contact sheets are an overview, not sufficient temporal analysis. The default sheet has at most 24 images to limit context; inspect omitted shots separately. For long videos create short working sections, record their exact source offsets and avoid claiming full coverage from a single sheet.

`frames --frames 80:90` means frame indexes 80 through 89, zero-based, exclusive end. Comma-separated indexes also work. Extraction decodes from the start and selects decoded frame indexes, preserving VFR ordering. The timestamps in `frame-times.json` retain raw PTS and normalized time from the first video frame. Extracted frames are auto-oriented by FFmpeg; use their dimensions to measure rotated media. Geometry in ffprobe can still describe the unrotated storage dimensions.

`compare --times ...` chooses the last presented frame at or before each normalized video time independently for each file. Inputs are not automatically shifted to hide sync errors. It reports metadata for both, sampled frame indexes, normalized mean absolute RGB error (0 identical, 1 maximum) and actual frame sizes. Diagnostic differences resize the render to reference dimensions; a dimension mismatch remains explicit and must be fixed. Resize/noise/compression/font rasterization can change pixel error; it is not a quality threshold. Missing/short outputs error instead of looping the final frame. The helper does not measure lip sync, audio offset, perceptual SSIM, or every-frame equivalence.

Use the native player's export for check frames and the final video. View the helper's labelled side-by-side images. If exact timing matters, also check consecutive frames around the event. Listen across all cuts; inspect waveform or PCM cross-correlation when sync is uncertain. Report audio checks separately. Check channels, leading silence, clipping and doubled sound.

## Shot/layer plan

A compact example (illustrative measurements, not an OTIO schema):

```json
{
  "mode": "faithful",
  "source": {"fps": "30000/1001", "vfr": false, "width": 1920, "height": 1080},
  "shots": [{
    "id": "shot-01", "start_frame": 0, "end_frame_exclusive": 83,
    "start_seconds": 0, "end_seconds": 2.769433333333333,
    "layers": [
      {"id": "footage", "treatment": "reuse", "asset": "media/source.mp4", "editable": "clip timing/crop", "confidence": "high"},
      {"id": "title", "treatment": "rebuild", "text": "Launch", "bbox_px": [400, 180, 1120, 180], "editable": "text/style/motion", "confidence": "medium"}
    ],
    "events": [{"frame": 12, "kind": "title-enter", "motion": "hard switch"}],
    "unresolved": ["Confirm original font"]
  }]
}
```

For each shot record the visible text verbatim, object boxes, background, z-order, masks, camera motion, easing, entrance/exit, source in/out, audio cues and asset provenance. Distinguish observed properties from estimates. For burned-in captions, visual switches govern display timing; speech timestamps only locate words. Compare the complete life of prominent text: entrance, hold, material/color changes and exit.

## Acceptance

- All shots and major layers accounted for; no undocumented whole-frame reuse.
- Cuts and hard events compared at frame boundaries; any frame-rate conversion disclosed.
- Text content, ink bounds, font substitutions and color match checked visually.
- Occlusion and motion checked in moving sections, not only static snapshots.
- Audio checked by listening; source mix/stem limitations disclosed.
- Export dimensions, duration, FPS and media availability verified.
- Every generated/reused/flattened part and unresolved discrepancy listed.
- Report what was actually tested; do not turn sampled pixel metrics into a claim of full fidelity.
