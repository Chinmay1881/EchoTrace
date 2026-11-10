"""Strict held-out dataset admission. Never infers labels; scientific dependencies are deferred until audio admission."""
from __future__ import annotations

import hashlib
import json
import math
import wave
from datetime import date
from pathlib import Path

CATEGORIES = {'FOOTSTEPS', 'IMPACT', 'DISTRESS', 'ALARM', 'GLASS', 'DOOR'}
ZONES = {'LEFT', 'CENTRE', 'RIGHT'}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audio_identity(path):
    """Exact PCM equality ignores container metadata; no perceptual duplicate claim."""
    with wave.open(str(path), 'rb') as f:
        params = (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes())
        h = hashlib.sha256(repr(params).encode())
        while block := f.readframes(65536):
            h.update(block)
        return {'pcm_sha256': h.hexdigest(), 'duration_s': params[3] / params[2],
                'sample_rate': params[2], 'channels': params[0]}


def signal_identity(path):
    """Lossless PCM storage changes/channel duplication must not bypass leakage checks.

    Keep historical pcm_sha256 unchanged. This additional identity normalizes signed
    PCM to int32 and collapses exactly duplicated channels; no resampling occurs.
    """
    import numpy as np
    import soundfile as sf
    audio, rate = sf.read(path, dtype='int32', always_2d=True)
    if audio.shape[1] == 2 and np.array_equal(audio[:, 0], audio[:, 1]):
        audio = audio[:, :1]
    h = hashlib.sha256(repr((rate, audio.shape)).encode())
    h.update(audio.astype('<i4').tobytes())
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(x):
    return type(x) in (float, int) and math.isfinite(x)


def interval(item, duration):
    require(isinstance(item, dict), 'annotation must be an object')
    a, b = item.get('start_s'), item.get('end_s')
    require(number(a) and number(b) and 0 <= a <= b <= duration,
            'invalid annotation interval')


def load_manifest(path, development):
    path, development = Path(path).resolve(), Path(development).resolve()
    data = json.loads(path.read_text())
    require(isinstance(data, dict) and data.get('schema_version') == 1, 'unsupported manifest')
    require(data.get('split') == 'independent-test', 'expected independent-test split')
    records = data.get('recordings')
    require(isinstance(records, list), 'recordings must be a list')
    known = set()
    for p in sorted(development.glob('*.wav')):
        known.add(sha256(p))
        known.add(audio_identity(p)['pcm_sha256'])
        known.add(signal_identity(p))
    ids, files, hashes = set(), set(), set()
    for r in records:
        require(isinstance(r, dict), 'recording must be an object')
        rid = r.get('recording_id')
        require(isinstance(rid, str) and rid and rid not in ids, 'missing/duplicate recording ID')
        ids.add(rid)
        mode = r.get('evaluation_mode', 'localization')
        require(mode in {'localization', 'non-spatial'}, f'{rid}: invalid evaluation_mode')
        require(r.get('dataset_role', 'independent-test') == 'independent-test',
                f'{rid}: pilot/development recordings cannot enter independent-test')
        for key in ('source', 'device', 'environment', 'annotator'):
            require(isinstance(r.get(key), str) and bool(r[key].strip()), f'{rid}: missing {key}')
        require(isinstance(r.get('date'), str), f'{rid}: missing date')
        date.fromisoformat(r['date'])
        require(r.get('used_for_tuning') is False, f'{rid}: independence declaration required')
        require(isinstance(r.get('wav'), str), f'{rid}: missing wav')
        wav = (path.parent / r['wav']).resolve()
        require(wav.is_relative_to(path.parent) and wav.suffix == '.wav' and wav.is_file(),
                f'{rid}: missing/unsafe WAV path')
        require(wav not in files, f'{rid}: duplicate WAV path')
        files.add(wav)
        info = audio_identity(wav)
        from echotrace.eval.collection import check_wav
        check_wav(wav, mode, collection_duration=False)
        digest = sha256(wav)
        require(r.get('sha256') == digest, f'{rid}: file hash mismatch')
        identities = {digest, info['pcm_sha256'], signal_identity(wav)}
        require(not identities & (known | hashes), f'{rid}: duplicate audio')
        hashes.update(identities)
        duration = r.get('duration_s')
        require(number(duration) and duration > 0 and abs(duration - info['duration_s']) <= 1 / info['sample_rate'],
                f'{rid}: duration mismatch')
        require(r.get('ground_truth_risk') in {'GREEN', 'AMBER', 'RED'}, f'{rid}: invalid risk')
        labels, events, incidents = r.get('category_labels'), r.get('events'), r.get('incidents')
        require(isinstance(labels, list) and all(isinstance(c, str) for c in labels) and len(labels) == len(set(labels)) and set(labels) <= CATEGORIES,
                f'{rid}: invalid category labels')
        require(isinstance(events, list) and isinstance(incidents, list), f'{rid}: missing timed annotations')
        for items in (events, incidents):
            annotation_ids = set()
            for item in items:
                interval(item, duration)
                identity = item.get('id')
                require(isinstance(identity, str) and identity and identity not in annotation_ids,
                        f'{rid}: missing/duplicate annotation ID')
                annotation_ids.add(identity)
        for e in events:
            require(e.get('category') in CATEGORIES and (e.get('zone') in ZONES if mode == 'localization' else e.get('zone') is None), f'{rid}: invalid event label')
        require(set(labels) == {e['category'] for e in events}, f'{rid}: category/event mismatch')
        for i in incidents:
            require(i.get('risk') in {'AMBER', 'RED'}, f'{rid}: invalid incident risk')
        order = {'GREEN': 0, 'AMBER': 1, 'RED': 2}
        risk = max((i['risk'] for i in incidents), key=order.get, default='GREEN')
        require(risk == r['ground_truth_risk'], f'{rid}: risk/incident mismatch')
    supplied = {p.resolve() for p in path.parent.rglob('*.wav')}
    require(supplied == files, 'unannotated WAV files present')
    return data
