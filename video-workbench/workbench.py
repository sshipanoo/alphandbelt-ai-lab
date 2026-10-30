#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A small, local, content-addressed concept-film build system. Python 3.9+."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
import uuid

from PIL import Image, ImageDraw, ImageFont
import PIL

ROOT = Path(__file__).resolve().parent
FONT = Path('/System/Library/Fonts/STHeiti Medium.ttc')


def run(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
    return result.stdout


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                           '-of', 'json', path]))


def ffmpeg(args):
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y'] + args)


def atomic_json(path, data):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def validate(spec):
    """Validate local input before running any expensive command."""
    for key in ('width', 'height', 'fps', 'rate'):
        if type(spec.get(key)) is not int or spec[key] <= 0:
            raise ValueError('Expected a positive integer: ' + key)
    if spec['width'] % 2 or spec['height'] % 2:
        raise ValueError('H.264 yuv420p requires even width and height')
    if not (1 <= spec['fps'] <= 60) or not (64 <= spec['width'] <= 3840) or not (64 <= spec['height'] <= 2160):
        raise ValueError('Output exceeds this workbench\'s supported bounds')
    if not isinstance(spec.get('shots'), list) or not 1 <= len(spec['shots']) <= 12:
        raise ValueError('Expected 1 to 12 shots')
    if not isinstance(spec.get('voice'), str) or not spec['voice'].strip():
        raise ValueError('Expected a voice name')
    seen = set()
    for shot in spec['shots']:
        sid = shot.get('id', '')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', sid) or sid in seen:
            raise ValueError('Invalid or duplicate shot id: ' + sid)
        seen.add(sid)
        seconds = shot.get('seconds')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 2 <= seconds <= 20:
            raise ValueError('Shot duration must be 2 to 20 seconds: ' + sid)
        if abs(seconds * spec['fps'] - round(seconds * spec['fps'])) > 1e-6:
            raise ValueError('Shot duration must contain an integer number of frames: ' + sid)
        if not isinstance(shot.get('narration'), str) or not 1 <= len(shot['narration']) <= 160:
            raise ValueError('Expected 1 to 160 narration characters: ' + sid)
        if shot.get('motion') not in ('in', 'out', 'right'):
            raise ValueError('Unsupported camera motion: ' + sid)
        asset = (ROOT / shot.get('image', '')).resolve()
        if not asset.is_relative_to((ROOT / 'assets').resolve()):
            raise ValueError('Image must be inside assets/: ' + sid)
        if not asset.is_file():
            raise ValueError('Missing image: ' + shot.get('image', ''))
        with Image.open(asset) as im:
            im.verify()
        with Image.open(asset) as im:
            if min(im.size) < 720:
                raise ValueError('Source image is too small: ' + sid)


class Build:
    def __init__(self, cache, spec):
        validate(spec)
        self.cache = Path(cache).resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.spec = spec
        self.events = []
        self.tools = {
            'ffmpeg': run(['ffmpeg', '-version']).splitlines()[0],
            'pillow': PIL.__version__,
            'os': platform.platform(),
        }
        if not shutil.which('say') or not FONT.is_file():
            raise ValueError('This sample uses macOS say + STHeiti. Other systems need a TTS/font adapter.')

    def node(self, label, recipe, dependencies, ext, producer):
        start = time.perf_counter()
        payload = {'recipe': recipe, 'deps': [digest(p) for p in dependencies]}
        key = hashlib.sha256(canonical(payload).encode()).hexdigest()
        kind = label.split('/')[0]
        path = self.cache / (kind + '-' + key + ext)
        metadata = path.with_suffix(path.suffix + '.json')
        reason = 'missing'
        if path.is_file() and metadata.is_file():
            try:
                recorded = json.loads(metadata.read_text(encoding='utf-8'))
                if recorded['sha256'] == digest(path):
                    event = dict(node=label, status='HIT', key=key[:12], seconds=round(time.perf_counter()-start, 4))
                    self.events.append(event)
                    print(label + ': HIT', flush=True)
                    return path
                reason = 'hash-mismatch'
            except (OSError, ValueError, KeyError):
                reason = 'metadata-invalid'
        tmp = self.cache / ('.' + uuid.uuid4().hex + ext)
        try:
            producer(tmp)
            if not tmp.is_file() or tmp.stat().st_size == 0:
                raise RuntimeError('Producer returned no artifact: ' + label)
            output_hash = digest(tmp)
            os.replace(tmp, path)
            atomic_json(metadata, {'sha256': output_hash, 'recipe': recipe, 'dependencies': payload['deps']})
        finally:
            tmp.unlink(missing_ok=True)
        event = dict(node=label, status='BUILD', reason=reason, key=key[:12], seconds=round(time.perf_counter()-start, 4))
        self.events.append(event)
        print(label + ': BUILD (' + reason + ')', flush=True)
        return path

    def picture(self, shot):
        s = self.spec
        frames = round(shot['seconds'] * s['fps'])
        recipe = dict(version='picture-v1', tool=self.tools['ffmpeg'], width=s['width'], height=s['height'],
                      fps=s['fps'], frames=frames, motion=shot['motion'])
        def produce(out):
            if shot['motion'] == 'out':
                zoom = '1.08-0.08*on/' + str(max(1, frames-1))
            else:
                zoom = '1+0.08*on/' + str(max(1, frames-1))
            x = '(iw-iw/zoom)*0.5'
            if shot['motion'] == 'right':
                zoom = '1.08'
                x = '(iw-iw/zoom)*on/' + str(max(1, frames-1))
            vf = (f"scale={s['width']*2}:{s['height']*2}:force_original_aspect_ratio=increase,"
                  f"crop={s['width']*2}:{s['height']*2},"
                  f"zoompan=z='{zoom}':x='{x}':y='(ih-ih/zoom)*0.5':d={frames}:"
                  f"s={s['width']}x{s['height']}:fps={s['fps']},setsar=1,format=yuv420p")
            ffmpeg(['-i', ROOT / shot['image'], '-vf', vf, '-frames:v', str(frames), '-an',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-threads', '4', '-movflags', '+faststart', out])
        return self.node('picture/' + shot['id'], recipe, [ROOT/shot['image']], '.mp4', produce)

    def voice(self, shot):
        s = self.spec
        recipe = dict(version='voice-v1', os=self.tools['os'], tool=self.tools['ffmpeg'],
                      voice=s['voice'], rate=s['rate'], narration=shot['narration'],
                      seconds=shot['seconds'], lead=0.35, tail=0.35)
        measured = {}
        def produce(out):
            raw = out.with_suffix('.aiff')
            text = out.with_suffix('.txt')
            text.write_text(shot['narration'], encoding='utf-8')
            try:
                run(['say', '-v', s['voice'], '-r', str(s['rate']), '-f', text, '-o', raw])
                duration = float(probe(raw)['format'].get('duration', 0))
                if duration <= 0:
                    raise ValueError('TTS returned empty audio. Check that the selected macOS voice and speech service are available.')
                measured['tts_seconds'] = duration
                if duration + 0.7 > shot['seconds']:
                    raise ValueError(f"Narration overflows {shot['id']}: speech {duration:.2f}s + 0.70s padding > slot {shot['seconds']:.2f}s. Shorten text or change the shot duration.")
                ffmpeg(['-i', raw, '-af', 'loudnorm=I=-18:TP=-2:LRA=7,adelay=350:all=1,apad',
                        '-t', str(shot['seconds']), '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', out])
            finally:
                raw.unlink(missing_ok=True)
                text.unlink(missing_ok=True)
        path = self.node('voice/' + shot['id'], recipe, [], '.wav', produce)
        if measured:
            self.events[-1].update(measured)
        return path

    def overlay(self, shot, index):
        s = self.spec
        recipe = dict(version='overlay-v1', pillow=self.tools['pillow'], font=digest(FONT),
                      width=s['width'], height=s['height'], text=shot['narration'], index=index)
        def produce(out):
            w, h = s['width'], s['height']
            im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            for y in range(round(h*0.70), h):
                alpha = int(175 * (y/h-0.70)/0.30)
                draw.line((0, y, w, y), fill=(4, 7, 9, alpha))
            size = round(w / 48)
            font = ImageFont.truetype(str(FONT), size)
            # Wrap by measured pixels, not by Chinese/English character counts.
            lines, line = [], ''
            for char in shot['narration']:
                if draw.textbbox((0, 0), line+char, font=font)[2] > w*0.82:
                    lines.append(line)
                    line = char
                else:
                    line += char
            if line:
                lines.append(line)
            if len(lines) > 2:
                raise ValueError('Subtitle exceeds two lines: ' + shot['id'])
            top = h-round(h*0.11)-len(lines)*(size+12)
            for offset, text in enumerate(lines):
                box = draw.textbbox((0, 0), text, font=font)
                draw.text(((w-box[2])/2, top+offset*(size+12)), text, font=font,
                          fill=(250, 247, 237, 255), stroke_width=1, stroke_fill=(0, 0, 0, 180))
            small = ImageFont.truetype(str(FONT), max(12, round(w/90)))
            draw.text((w*0.055, h*0.055), 'THE CLOUD ARCHIVE  /  %02d' % (index+1), font=small,
                      fill=(247, 227, 183, 240), stroke_width=1, stroke_fill=(0, 0, 0, 130))
            im.save(out)
        return self.node('overlay/' + shot['id'], recipe, [], '.png', produce)

    def concat(self, label, paths, ext, audio=False):
        def produce(out):
            listing = out.with_suffix('.list')
            # Only generated hash filenames enter the concat list; no user shell strings.
            listing.write_text('\n'.join("file '" + p.name + "'" for p in paths)+'\n', encoding='utf-8')
            try:
                args = ['-f', 'concat', '-safe', '1', '-i', listing]
                if audio:
                    args += ['-c:a', 'pcm_s16le']
                else:
                    args += ['-c', 'copy', '-movflags', '+faststart']
                ffmpeg(args + [out])
            finally:
                listing.unlink(missing_ok=True)
        return self.node(label, dict(version='concat-v1', tool=self.tools['ffmpeg'], audio=audio), paths, ext, produce)

    def finish(self, video, audio, overlays):
        s = self.spec
        total = sum(x['seconds'] for x in s['shots'])
        recipe = dict(version='final-v1', tool=self.tools['ffmpeg'], seconds=[x['seconds'] for x in s['shots']],
                      subtitle_lead=0.25, subtitle_tail=0.25, bed='original-sine-55-82.4-110Hz-v1')
        def produce(out):
            args = ['-i', video, '-i', audio]
            for overlay in overlays:
                args += ['-loop', '1', '-i', overlay]
            graph, offset, previous = [], 0, '0:v'
            for i, shot in enumerate(s['shots']):
                end = offset + shot['seconds']
                target = f'v{i}'
                graph.append(f"[{previous}][{i+2}:v]overlay=0:0:enable='between(t,{offset+0.25},{end-0.25})'[{target}]")
                previous, offset = target, end
            graph += [f"aevalsrc=0.014*sin(2*PI*55*t)+0.009*sin(2*PI*82.4*t)+0.006*sin(2*PI*110*t):s=48000:d={total}[bed0]",
                      f"[bed0]afade=t=in:d=1.2,afade=t=out:st={total-1.5}:d=1.5[bed]",
                      '[1:a][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[a]']
            args += ['-filter_complex_threads', '1', '-filter_complex', ';'.join(graph),
                     '-map', '['+previous+']', '-map', '[a]', '-t', str(total),
                     '-r', str(s['fps']), '-c:v', 'libx264', '-preset', 'fast', '-crf', '19',
                     '-pix_fmt', 'yuv420p', '-threads', '4', '-c:a', 'aac', '-b:a', '192k',
                     '-movflags', '+faststart', out]
            ffmpeg(args)
            inspect_video(out, s, decode=True)
        return self.node('final', recipe, [video, audio] + overlays, '.mp4', produce)

    def execute(self, output):
        started = time.perf_counter()
        pictures, voices, overlays = [], [], []
        for i, shot in enumerate(self.spec['shots']):
            voices.append(self.voice(shot))
            pictures.append(self.picture(shot))
            overlays.append(self.overlay(shot, i))
        video = self.concat('join-picture', pictures, '.mp4')
        audio = self.concat('join-voice', voices, '.wav', audio=True)
        final = self.finish(video, audio, overlays)
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_name('.' + uuid.uuid4().hex + '.mp4')
        try:
            shutil.copyfile(final, temp)
            os.replace(temp, output)
        finally:
            temp.unlink(missing_ok=True)
        report = dict(elapsed_seconds=round(time.perf_counter()-started, 3), events=self.events,
                      video=inspect_video(output, self.spec), output_sha256=digest(output), tools=self.tools,
                      spec=self.spec)
        atomic_json(output.with_suffix('.json'), report)
        return report


def inspect_video(path, spec, decode=False):
    data = probe(path)
    videos = [s for s in data['streams'] if s['codec_type'] == 'video']
    audios = [s for s in data['streams'] if s['codec_type'] == 'audio']
    if len(videos) != 1 or len(audios) != 1:
        raise ValueError('Expected one video and one audio stream')
    v, a = videos[0], audios[0]
    expected = sum(s['seconds'] for s in spec['shots'])
    checks = [v['codec_name'] == 'h264', v['pix_fmt'] == 'yuv420p',
              (v['width'], v['height']) == (spec['width'], spec['height']),
              v['avg_frame_rate'] == str(spec['fps'])+'/1',
              abs(float(v['duration'])-expected) < 1/spec['fps']+0.001,
              abs(float(a['duration'])-expected) < 0.1, a['sample_rate'] == '48000']
    if not all(checks):
        raise ValueError('Output media contract failed: ' + str(checks))
    if decode:
        ffmpeg(['-xerror', '-i', path, '-f', 'null', '-'])
    return dict(width=v['width'], height=v['height'], fps=v['avg_frame_rate'],
                video_codec=v['codec_name'], audio_codec=a['codec_name'], pixel_format=v['pix_fmt'],
                video_seconds=float(v['duration']), audio_seconds=float(a['duration']),
                bytes=Path(path).stat().st_size, decoded=decode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, default=ROOT/'storyboard.json')
    parser.add_argument('--cache', type=Path, default=ROOT/'.cache')
    parser.add_argument('--output', type=Path, default=ROOT/'results/cloud-archive.mp4')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    validate(spec)
    if args.validate_only:
        print('Storyboard contract: PASS')
        return
    report = Build(args.cache, spec).execute(args.output)
    print(json.dumps(dict(elapsed_seconds=report['elapsed_seconds'], video=report['video']), ensure_ascii=False))


if __name__ == '__main__':
    main()
