"""Read-only, model-free checks for the prespecified 36-clip collection."""
import csv
import wave
from pathlib import Path

from echotrace.eval.dataset import load_manifest, require, sha256

RUBRIC = 'echotrace-contextual-proxy-v1'


def check_wav(path, evaluation_mode="localization", *, collection_duration=True):
    """Full decode detects truncation; format requirements apply before inference."""
    import numpy as np
    import soundfile as sf
    from echotrace.audio.devices import channel_report

    require(evaluation_mode in {'localization', 'non-spatial'}, 'invalid evaluation_mode')
    info = sf.info(path)
    require(info.format in {'WAV', 'WAVEX'} and info.subtype in {'PCM_16', 'PCM_24'}, 'expected PCM_16 or PCM_24 WAV')
    require(info.samplerate == 48000 and info.channels in {1, 2}, 'expected 48000 Hz, one or two channels')
    require(info.frames > 0, 'empty audio')
    if collection_duration:
        require(25 <= info.duration <= 35, 'expected 25–35 seconds')
    audio, _ = sf.read(path, dtype='float32', always_2d=True)
    require(len(audio) == info.frames, 'truncated audio')
    with wave.open(str(path), 'rb') as stream:
        require(stream.getnframes() == len(audio), 'truncated PCM payload/header mismatch')
    require(bool(np.isfinite(audio).all()), 'nonfinite audio')
    peak = float(np.abs(audio).max())
    require(peak < .999, 'clipping/full-scale samples; review take before admission')
    exact_duplicate = info.channels == 2 and bool(np.array_equal(audio[:, 0], audio[:, 1]))
    channels = channel_report(audio) if info.channels == 2 else None
    silent = bool(np.max(np.sqrt(np.mean(audio.astype('float64') ** 2, axis=0))) < 1e-6)
    modality = 'mono' if info.channels == 1 else 'dual-mono' if exact_duplicate else 'stereo-candidate'
    # Correlation is a diagnostic, never proof of exact duplication or physical stereo.
    candidate = modality == 'stereo-candidate' and not silent
    if evaluation_mode == 'localization':
        require(info.channels == 2, 'localization requires two channels; mono is non-spatial only')
        require(not exact_duplicate, 'dual-mono is non-spatial only')
        require(silent or not channels.identical, 'processed/near-identical channels require spatial review')
    return {'wav': str(path), 'sha256': sha256(path),
            'sample_rate': info.samplerate, 'channels': info.channels,
            'subtype': info.subtype, 'duration_s': info.duration, 'peak': peak,
            'silent': silent, 'modality': modality, 'exact_channel_duplication': exact_duplicate,
            'channel_correlation': channels.corr if channels else None,
            'evaluation_mode': evaluation_mode,
            'spatial_signal_candidate': candidate and not channels.identical if channels else False,
            'spatial_eligible': False,  # file QC cannot establish physical geometry or human review
            'directional_scoring': 'not implemented; non-spatial recordings must never enter its denominator',
            'stereo_evidence': 'unverified; distinct channels do not establish physical microphone geometry'}


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
        reports.append(check_wav(Path(manifest).parent / record['wav'], record.get('evaluation_mode', 'localization')))
    return {'status': 'format and manifest valid; human review still required',
            'recordings': len(reports), 'planned': len(planned),
            'missing_clip_ids': sorted(set(planned) - {r['recording_id'] for r in data['recordings']}),
            'rubric_id': RUBRIC, 'files': reports, 'inference_performed': False}
