"""Read-only, model-free checks for the prespecified 36-clip collection."""
import csv
import wave
from pathlib import Path

from echotrace.eval.dataset import load_manifest, require

RUBRIC = 'echotrace-contextual-proxy-v1'


def check_wav(path):
    """Full decode detects truncation; format requirements apply before inference."""
    import numpy as np
    import soundfile as sf
    from echotrace.audio.devices import channel_report

    info = sf.info(path)
    require(info.format in {'WAV', 'WAVEX'} and info.subtype == 'PCM_24', 'expected PCM_24 WAV')
    require(info.samplerate == 48000 and info.channels == 2, 'expected 48000 Hz, two channels')
    require(25 <= info.duration <= 35, 'expected 25–35 seconds')
    audio, _ = sf.read(path, dtype='float32', always_2d=True)
    require(len(audio) == info.frames, 'truncated audio')
    with wave.open(str(path), 'rb') as stream:
        require(stream.getnframes() == len(audio), 'truncated PCM payload/header mismatch')
    require(bool(np.isfinite(audio).all()), 'nonfinite audio')
    peak = float(np.abs(audio).max())
    require(peak < .999, 'clipping/full-scale samples; review take before admission')
    channels = channel_report(audio)
    # Quiet clips can be silent; hardware qualification comes from separate practice takes.
    require(channels.silent or not channels.identical, 'duplicated/processed mono channels')
    return {'wav': str(path), 'sample_rate': info.samplerate, 'channels': info.channels,
            'subtype': info.subtype, 'duration_s': info.duration, 'peak': peak,
            'silent': bool(channels.silent), 'stereo_evidence': 'unassessable on silence' if channels.silent
            else 'distinct channels; physical microphone geometry still requires human verification'}


def validate_collection(manifest, development, checklist):
    data = load_manifest(manifest, development)
    require(bool(data['recordings']), 'pending: no independent recordings')
    with Path(checklist).open(newline='') as stream:
        planned = {row['clip_id']: row for row in csv.DictReader(stream)}
    require(len(planned) == 36, 'expected the prespecified 36-clip checklist')
    reports = []
    for record in data['recordings']:
        rid = record['recording_id']
        require(rid in planned, f'{rid}: not in ordered collection checklist')
        plan = planned[rid]
        require(record.get('rubric_id') == RUBRIC, f'{rid}: missing/future rubric ID')
        require(record['ground_truth_risk'] == plan['risk'], f'{rid}: risk conflicts with prespecified script')
        require(record.get('scenario') == plan['scenario'], f'{rid}: scenario mismatch')
        require(record.get('session_id') == plan['session'], f'{rid}: session mismatch')
        for key in ('room_id', 'capture_app_version', 'processing_settings', 'context_log', 'hardware_qualification'):
            require(isinstance(record.get(key), str) and bool(record[key].strip()), f'{rid}: missing {key}')
        require(record.get('source_mode') in {'direct', 'playback', 'mixed'}, f'{rid}: invalid source_mode')
        require(record.get('dropped_blocks') == 0 and type(record.get('dropped_blocks')) is int,
                f'{rid}: zero dropped blocks must be documented')
        require(record.get('overflows') == 0 and type(record.get('overflows')) is int,
                f'{rid}: zero overflows must be documented')
        if record['source_mode'] in {'playback', 'mixed'}:
            require(isinstance(record.get('source_assets'), list) and bool(record['source_assets']),
                    f'{rid}: playback requires source_assets')
            for asset in record['source_assets']:
                require(isinstance(asset, dict) and all(isinstance(asset.get(k), str) and asset[k].strip()
                        for k in ('id', 'origin', 'rights', 'speaker', 'volume')),
                        f'{rid}: incomplete playback provenance')
        expected_incidents = 0 if plan['risk'] == 'GREEN' else 1
        require(len(record['incidents']) == expected_incidents, f'{rid}: expected {expected_incidents} incidents')
        for event in record['events']:
            require(event['start_s'] < event['end_s'], f'{rid}: physical event must have positive duration')
        if expected_incidents:
            incident = record['incidents'][0]
            linked = incident.get('event_ids')
            events = {e['id']: e for e in record['events']}
            require(isinstance(linked, list) and bool(linked) and all(isinstance(i, str) for i in linked)
                    and len(linked) == len(set(linked)) and set(linked) <= events.keys(),
                    f'{rid}: incident needs unique causal event_ids')
            require(incident['start_s'] == min(events[i]['start_s'] for i in linked)
                    and incident['end_s'] == max(events[i]['end_s'] for i in linked),
                    f'{rid}: incident endpoints must span its annotated causal sounds')
            causal = sorted((events[i] for i in linked), key=lambda e: e['start_s'])
            require([e['category'] for e in causal] == plan['intended_sequence'].split('>'),
                    f'{rid}: causal categories differ from the staged script; review before admission')
        reports.append(check_wav(Path(manifest).parent / record['wav']))
    return {'status': 'format and manifest valid; human review still required',
            'recordings': len(reports), 'planned': len(planned),
            'missing_clip_ids': sorted(set(planned) - {r['recording_id'] for r in data['recordings']}),
            'rubric_id': RUBRIC, 'files': reports, 'inference_performed': False}
