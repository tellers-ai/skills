# Optional generation

No external generation API is required to reconstruct cuts, typography, SVG graphics and native Tellers effects from existing media. The host agent's visual reasoning is still required; local measurements are not semantic understanding.

Use Tellers OAuth and connected tools for optional cloud analysis/generation. Do not require separate HeyGen, OpenAI, Google or other provider keys when routing through Tellers. Discover actual generation schemas and available models at execution time. A remembered model name is not evidence that a particular reference input is supported.

Choose by capability:
- Clean plate: image editing with a supplied reference; remove only obstructing text/graphics and inspect identity, background and fine details afterward.
- Replacement footage: video generation with the applicable first-frame, image-reference or motion-reference capability. Check which input combinations the chosen tool accepts. Never assume first-frame plus image references or motion plus audio can be combined.
- Speech: preserve the source voice by default. Generate new speech only for a changed script/request; never silently clone a voice or impersonate a person.
- Missing music/SFX: use available Tellers tools only when the brief needs new audio. Reuse the original mix for faithful reconstruction when allowed.

Describe the proposed calls, duration, count, cost/credit estimate if exposed, and budget before an unapproved paid run. Carry prior approval forward; do not repeatedly ask within an approved scope. Record job IDs and reuse finished outputs on retries; check status before resubmitting.

Generate one intended shot at a time or in bounded independent batches. A motion guide should cover only that shot. Remove drawn overlays from reference inputs if cleanup is required. Preserve a clean first/last frame where supported, but do not promise exact timing: generated motion can arrive late, add movements or disregard intermediate frame timestamps. Compare event times, trim and retime within supported limits. Regenerate only for a concrete failure and within budget. If a required control is unavailable, use existing footage or clearly report the approximation.

Keep generated shots as replaceable media clips and add captions/graphics separately. Do not label the pixels inside generated footage as editable layers. Do not change the person's face or replace clean footage just to satisfy an artificial regeneration step.
