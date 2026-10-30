#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real integration checks. Runs FFmpeg and macOS speech, not mocked outputs."""
from copy import deepcopy
import json
from pathlib import Path
import time
import uuid

from workbench import Build, ROOT, atomic_json, inspect_video, validate


def execute():
    spec = json.loads((ROOT/'storyboard.json').read_text(encoding='utf-8'))
    session = uuid.uuid4().hex[:8]
    cache = ROOT/'.cache'/('experiment-'+session)
    results = ROOT/'results'
    results.mkdir(exist_ok=True)
    reports = []
    def case(name, current):
        report = Build(cache, current).execute(results/(name+'.mp4'))
        report['case'] = name
        report['built'] = [e['node'] for e in report['events'] if e['status']=='BUILD']
        report['hits'] = [e['node'] for e in report['events'] if e['status']=='HIT']
        reports.append(report)
        return report

    cold = case('01-cold', spec)
    assert len(cold['built']) == 12
    warm = case('02-unchanged', spec)
    assert len(warm['built']) == 0 and len(warm['hits']) == 12
    assert cold['output_sha256'] == warm['output_sha256']

    changed = deepcopy(spec)
    changed['shots'][1]['narration'] = '让每一页留下光，也让记忆拥有自己的形状。'
    voice = case('03-change-narration', changed)
    assert set(voice['built']) == {'voice/memory', 'overlay/memory', 'join-voice', 'final'}
    assert all('picture/'+s['id'] in voice['hits'] for s in spec['shots'])

    changed = deepcopy(spec)
    changed['shots'][1]['image'] = spec['shots'][2]['image']
    picture = case('04-replace-one-image', changed)
    assert set(picture['built']) == {'picture/memory', 'join-picture', 'final'}
    assert all('voice/'+s['id'] in picture['hits'] for s in spec['shots'])

    # Damage a cached intermediate, then prove content verification rejects it.
    event = next(e for e in cold['events'] if e['node']=='picture/arrival')
    paths = list(cache.glob('picture-'+event['key']+'*.mp4'))
    assert len(paths) == 1
    with paths[0].open('ab') as stream:
        stream.write(b'INTENTIONAL-CACHE-CORRUPTION')
    repaired = case('05-repair-corrupt-cache', spec)
    repair = next(e for e in repaired['events'] if e['node']=='picture/arrival')
    assert repair['status']=='BUILD' and repair['reason']=='hash-mismatch'
    assert 'picture/memory' in repaired['hits'] and 'picture/future' in repaired['hits']

    errors = []
    def rejected(name, current, expected, build=False):
        begin = time.perf_counter()
        try:
            if build:
                Build(cache, current).execute(results/('should-not-exist-'+name+'.mp4'))
            else:
                validate(current)
        except ValueError as error:
            assert expected in str(error), str(error)
            errors.append(dict(case=name, status='PASS', error=str(error), seconds=round(time.perf_counter()-begin,3)))
        else:
            raise AssertionError('Expected rejection: '+name)
    missing = deepcopy(spec)
    missing['shots'][0]['image']='assets/missing.png'
    rejected('missing-asset', missing, 'Missing image')
    overflow = deepcopy(spec)
    overflow['shots'][0]['narration']='这是一段故意写得很长的旁白，用来验证程序会拒绝超出镜头时长的声音，而不是把它直接截掉。'*2
    rejected('narration-overflow', overflow, 'Narration overflows', build=True)
    invalid = deepcopy(spec)
    invalid['width'] = 1919
    rejected('odd-output-width', invalid, 'even width')

    final = results/'cloud-archive.mp4'
    # Final delivery uses the original three shots and original text.
    import shutil
    shutil.copyfile(results/'01-cold.mp4', final)
    decoded = inspect_video(final, spec, decode=True)
    summary = dict(session=session, scope='Single local run; excludes image generation, coding and dependency installation. No cost benchmark.',
                   reports=reports, rejection_checks=errors, final_validation=decoded,
                   scenarios_passed=8)
    atomic_json(results/'experiments.json', summary)
    print(json.dumps({'cases':[{k:r[k] for k in ('case','elapsed_seconds','built','hits')} for r in reports],
                      'rejection_checks':errors, 'final_validation':decoded}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    execute()
