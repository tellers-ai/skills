#!/usr/bin/env python3
"""Local reference inspection. No network, model calls, or automatic fidelity verdict."""
import argparse
import bisect
import io
import json
import math
from pathlib import Path
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw


def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def probe(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    if video is None:
        raise ValueError('Input has no video stream')
    raw = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                          '-show_entries', 'frame=best_effort_timestamp_time,pkt_duration_time', '-of', 'json', str(path)]).stdout)['frames']
    if not raw or any('best_effort_timestamp_time' not in f for f in raw):
        raise ValueError('All frames need presentation timestamps')
    pts = [float(f['best_effort_timestamp_time']) for f in raw]
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise ValueError('Non-increasing video timestamps; normalize a working copy first')
    times = [t - pts[0] for t in pts]
    steps = np.diff(times)
    fallback = float(np.median(steps)) if len(steps) else 0.0
    last_duration = float(raw[-1].get('pkt_duration_time', 0)) or fallback
    if last_duration <= 0:
        last_duration = float(video.get('duration', 0))
    if last_duration <= 0:
        raise ValueError('Cannot determine the last frame duration')
    result = {'video': video, 'audio': [s for s in data['streams'] if s['codec_type'] == 'audio'],
              'format': data.get('format', {}), 'frame_count': len(times), 'first_video_pts': pts[0],
              'video_duration': times[-1] + last_duration,
              'variable_frame_intervals': bool(len(steps) > 1 and np.ptp(steps) > max(0.00001, fallback * 0.01))}
    return result, times, pts


def extract(path, index):
    result = run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0', '-vf',
                  f'select=eq(n\\,{index})', '-fps_mode', 'passthrough', '-frames:v', '1',
                  '-f', 'image2pipe', '-vcodec', 'png', '-threads', '1', '-'])
    if not result.stdout:
        raise ValueError(f'No decoded frame {index}')
    return Image.open(io.BytesIO(result.stdout)).convert('RGB')


def sheet(items, out):
    if not items:
        return
    width, height, columns = 320, 208, min(4, len(items))
    canvas = Image.new('RGB', (width * columns, height * math.ceil(len(items) / columns)), '#181818')
    draw = ImageDraw.Draw(canvas)
    for i, (img, label) in enumerate(items):
        thumb = img.copy()
        thumb.thumbnail((width, height - 28))
        x, y = (i % columns) * width, (i // columns) * height
        canvas.paste(thumb, (x + (width - thumb.width) // 2, y))
        draw.text((x + 6, y + height - 23), label, fill='white')
    canvas.save(out)


def frames_arg(raw):
    indexes = set()
    for part in raw.split(','):
        if ':' in part:
            a, b = map(int, part.split(':'))
            if b <= a:
                raise ValueError('Frame range end must be greater than start')
            indexes.update(range(a, b))
        else:
            indexes.add(int(part))
    if not indexes or min(indexes) < 0 or len(indexes) > 120:
        raise ValueError('Select 1 to 120 non-negative frame indexes per batch')
    return sorted(indexes)


def frame_outputs(path, indexes, times, out):
    if any(k >= len(times) for k in indexes):
        raise ValueError('Requested frame is outside the video')
    items = []
    for k in indexes:
        img = extract(path, k)
        img.save(out / f'frame-{k:08d}.png')
        items.append((img, f'f{k} | {times[k]:.6f}s'))
    sheet(items, out / 'contact-sheet.jpg')


def analyze(args, metadata, times, pts):
    save(args.out / 'probe.json', metadata)
    save(args.out / 'frame-times.json', [{'frame': i, 'pts': p, 'seconds': t} for i, (p, t) in enumerate(zip(pts, times))])
    result = run(['ffmpeg', '-hide_banner', '-copyts', '-i', str(args.input), '-map', '0:v:0', '-an',
                  '-vf', f"select=gt(scene\\,{args.threshold}),showinfo", '-fps_mode', 'passthrough', '-f', 'null', '-'])
    hits = [float(t) for t in re.findall(r'pts_time:([\d.eE+\-]+)', result.stderr.decode(errors='replace'))]
    cuts = []
    for t in hits:
        k = bisect.bisect_left(pts, t)
        k = min(range(max(0, k - 1), min(len(pts), k + 2)), key=lambda j: abs(pts[j] - t))
        if k and not any(c['frame'] == k for c in cuts):
            cuts.append({'frame': k, 'seconds': times[k], 'status': 'candidate-needs-visual-review'})
    save(args.out / 'cut-candidates.json', {'method': 'ffmpeg-scene-score', 'threshold': args.threshold,
        'limitations': 'Can miss punch-ins and soft cuts; flashes/graphics can be false positives.', 'cuts': cuts})
    candidates = sorted(set([0, len(times) - 1] + [c['frame'] for c in cuts] +
                            [round(i * (len(times) - 1) / 11) for i in range(12)]))
    if len(candidates) > 24:
        candidates = [candidates[round(i * (len(candidates) - 1) / 23)] for i in range(24)]
    frame_outputs(args.input, candidates, times, args.out)


def compare(args, source, times):
    other, other_times, _ = probe(args.render)
    wanted = [float(t) for t in args.times.split(',')]
    if not 1 <= len(wanted) <= 120:
        raise ValueError('Choose 1 to 120 comparison times')
    rows, items = [], []
    for i, t in enumerate(wanted):
        if not math.isfinite(t) or t < 0 or t >= min(source['video_duration'], other['video_duration']):
            raise ValueError(f'Comparison time {t} is outside one of the videos')
        k = max(0, bisect.bisect_right(times, t) - 1)
        j = max(0, bisect.bisect_right(other_times, t) - 1)
        a, b = extract(args.input, k), extract(args.render, j)
        original_size = b.size
        resized = b.resize(a.size, Image.Resampling.LANCZOS)
        delta = np.abs(np.asarray(a, dtype=np.float32) - np.asarray(resized, dtype=np.float32))
        rows.append({'seconds': t, 'reference_frame': k, 'render_frame': j,
                     'reference_size': list(a.size), 'render_size': list(original_size),
                     'normalized_rgb_mae': float(delta.mean() / 255), 'resized_for_metric': a.size != original_size})
        pair = Image.new('RGB', (a.width * 2, a.height + 30), '#181818')
        pair.paste(a, (0, 30))
        pair.paste(resized, (a.width, 30))
        draw = ImageDraw.Draw(pair)
        draw.text((8, 8), f'Reference | {t:.6f}s | f{k}', fill='white')
        draw.text((a.width + 8, 8), f'Render | f{j}', fill='white')
        pair.save(args.out / f'compare-{i:03d}.png')
        items.append((pair, f'{t:.6f}s | reference / render'))
    sheet(items, args.out / 'contact-sheet.jpg')
    save(args.out / 'comparison.json', {'reference': source, 'render': other,
        'scope': 'Sampled RGB differences only; no audio or automatic fidelity verdict.', 'samples': rows})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('analyze', 'frames', 'compare'):
        p = sub.add_parser(name)
        p.add_argument('input', type=Path)
        p.add_argument('--out', type=Path, required=True)
        if name == 'analyze':
            p.add_argument('--threshold', type=float, default=0.25)
        elif name == 'frames':
            p.add_argument('--frames', required=True)
        else:
            p.add_argument('render', type=Path)
            p.add_argument('--times', required=True)
    args = parser.parse_args()
    args.input = args.input.resolve(strict=True)
    if args.command == 'compare':
        args.render = args.render.resolve(strict=True)
    if args.command == 'analyze' and not 0 < args.threshold < 1:
        parser.error('threshold must be between 0 and 1')
    if args.out.exists() and any(args.out.iterdir()):
        parser.error('output directory must be empty; choose a new review directory')
    args.out.mkdir(parents=True, exist_ok=True)
    metadata, times, pts = probe(args.input)
    if args.command == 'analyze':
        analyze(args, metadata, times, pts)
    elif args.command == 'frames':
        frame_outputs(args.input, frames_arg(args.frames), times, args.out)
    else:
        compare(args, metadata, times)
    print(f'{args.command}: wrote results to {args.out}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.decode(errors='replace')[-1500:] if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise SystemExit(f'Reference inspection failed: {detail}') from error
