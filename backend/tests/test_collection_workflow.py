"""Temporary scripted fixtures for collection checks; never scientific recordings."""
import csv
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

from echotrace.eval.collection import RUBRIC, check_wav, validate_collection
from echotrace.eval.dataset import sha256

CHECKLIST = Path(__file__).resolve().parents[2] / 'docs/research/collection-checklist.csv'


@pytest.fixture
def collection(tmp_path):
    test = tmp_path / 'test'
    test.mkdir()
    dev = tmp_path / 'dev'
    dev.mkdir()
    rid = 's01_take02_isolated_glass_l'
    wav = test / f'{rid}.wav'
    # Distinct low-amplitude noise is a software fixture, not an acoustic category claim.
    audio = np.random.default_rng(0).uniform(-.02, .02, (30 * 48000, 2)).astype('float32')
    sf.write(wav, audio, 48000, subtype='PCM_24')
    record = {'recording_id': rid, 'wav': wav.name, 'sha256': sha256(wav), 'duration_s': 30,
              'source': 'unit test fixture only', 'date': '2026-11-08', 'device': 'fixture',
              'environment': 'fixture', 'annotator': 'fixture', 'used_for_tuning': False,
              'ground_truth_risk': 'GREEN', 'category_labels': ['GLASS'],
              'events': [{'id': 'e1', 'start_s': 4, 'end_s': 5, 'category': 'GLASS', 'zone': 'LEFT'}],
              'incidents': [], 'rubric_id': RUBRIC, 'scenario': 'isolated_glass', 'session_id': 's01',
              'room_id': 'fixture', 'capture_app_version': 'fixture', 'processing_settings': 'none',
              'context_log': 'fixture only', 'hardware_qualification': 'fixture only',
              'source_mode': 'direct', 'dropped_blocks': 0, 'overflows': 0}
    manifest = test / 'manifest.json'

    def write():
        manifest.write_text(json.dumps({'schema_version': 1, 'split': 'independent-test',
                                        'recordings': [record]}))
        return manifest

    return wav, record, write, dev


def test_manifest_format_read_only_and_partial(collection):
    wav, record, write, dev = collection
    path = write()
    before = (wav.read_bytes(), path.read_bytes())
    result = validate_collection(path, dev, CHECKLIST)
    assert result['recordings'] == 1 and len(result['missing_clip_ids']) == 35
    assert result['inference_performed'] is False
    assert before == (wav.read_bytes(), path.read_bytes())


@pytest.mark.parametrize('change', [{'rubric_id': 'wrong'}, {'ground_truth_risk': 'RED'},
                                   {'source_mode': 'playback'}, {'overflows': 1}, {'context_log': ''}])
def test_reject_protocol_annotation_errors(collection, change):
    _, record, write, dev = collection
    record.update(change)
    with pytest.raises(ValueError):
        validate_collection(write(), dev, CHECKLIST)


@pytest.mark.parametrize('rate,channels,subtype,seconds', [(44100, 2, 'PCM_24', 30),
                                                          (48000, 1, 'PCM_24', 30),
                                                          (48000, 2, 'FLOAT', 30),
                                                          (48000, 2, 'PCM_24', 1)])
def test_reject_wrong_formats(tmp_path, rate, channels, subtype, seconds):
    wav = tmp_path / 'fixture.wav'
    sf.write(wav, np.zeros((seconds * rate, channels)), rate, subtype=subtype)
    with pytest.raises(ValueError):
        check_wav(wav)


def test_reject_duplicated_mono_and_clipping(tmp_path):
    wav = tmp_path / 'fixture.wav'
    mono = np.random.default_rng(0).uniform(-.02, .02, 48000 * 30)
    sf.write(wav, np.column_stack([mono, mono]), 48000, subtype='PCM_24')
    with pytest.raises(ValueError, match='mono'):
        check_wav(wav)
    sf.write(wav, np.ones((48000 * 30, 2)), 48000, subtype='PCM_24')
    with pytest.raises(ValueError, match='clipping'):
        check_wav(wav)


def test_complete_requirement_and_no_inference_import(collection):
    _, _, write, dev = collection
    script = Path(__file__).resolve().parents[1] / 'scripts/research_validate.py'
    path = write()
    result = subprocess.run([sys.executable, str(script), '--manifest', str(path),
                             '--development', str(dev), '--require-complete'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)['inference_performed'] is False
    assert '36' in result.stdout


def test_checklist_balanced_and_unique():
    with CHECKLIST.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len({r['clip_id'] for r in rows}) == 36
    assert [int(r['order']) for r in rows] == list(range(1, 37))
    assert {risk: sum(r['risk'] == risk for r in rows) for risk in ['GREEN', 'AMBER', 'RED']} == {
        'GREEN': 24, 'AMBER': 6, 'RED': 6}
    assert all(sum(r['session'] == s for r in rows) == 12 for s in ['s01', 's02', 's03'])
    kitchen = [r for r in rows if r['scenario'] == 'benign_routine_kitchen']
    assert len(kitchen) == 2 and all(r['risk'] == 'GREEN' for r in kitchen)


def test_positive_causal_event_endpoints(collection):
    wav, record, write, dev = collection
    rid = 's01_take01_gi_l'
    new = wav.with_name(rid + '.wav')
    wav.rename(new)
    record.update(recording_id=rid, wav=new.name, scenario='positive_glass_impact',
                  ground_truth_risk='AMBER', category_labels=['GLASS', 'IMPACT'])
    record['events'].append({'id': 'e2', 'start_s': 8, 'end_s': 9, 'category': 'IMPACT', 'zone': 'LEFT'})
    record['incidents'] = [{'id': 'i1', 'start_s': 4, 'end_s': 9, 'risk': 'AMBER', 'event_ids': ['e1', 'e2']}]
    validate_collection(write(), dev, CHECKLIST)
    record['incidents'][0]['start_s'] = 0
    with pytest.raises(ValueError, match='endpoints'):
        validate_collection(write(), dev, CHECKLIST)


def test_truncated_pcm_is_rejected(collection):
    wav, _, _, _ = collection
    raw = wav.read_bytes()
    wav.write_bytes(raw[:-48000 * 6])  # still 29 seconds if decoder ignores stale header
    with pytest.raises(ValueError, match='truncated'):
        check_wav(wav)


@pytest.mark.parametrize('subtype', ['PCM_16', 'PCM_24'])
@pytest.mark.parametrize('modality', ['mono', 'dual-mono', 'stereo-candidate'])
def test_non_spatial_formats_preserve_source(tmp_path, subtype, modality):
    wav = tmp_path / 'pilot_fixture.wav'
    mono = np.random.default_rng(12).uniform(-.01, .01, 48000 * 25)
    audio = mono if modality == 'mono' else np.column_stack(
        [mono, mono if modality == 'dual-mono' else mono * .9 + .00001])
    sf.write(wav, audio, 48000, subtype=subtype)
    before = wav.read_bytes()
    result = check_wav(wav, 'non-spatial')
    assert result['modality'] == modality
    assert result['subtype'] == subtype
    assert result['spatial_eligible'] is False
    assert wav.read_bytes() == before
    if modality != 'stereo-candidate':
        with pytest.raises(ValueError, match='mono'):
            check_wav(wav, 'localization')


@pytest.mark.parametrize('subtype', ['PCM_16', 'PCM_24'])
def test_independent_stereo_formats(collection, subtype):
    wav, _, write, dev = collection
    audio, rate = sf.read(wav)
    sf.write(wav, audio, rate, subtype=subtype)
    # Hash is provenance, not a request for automatic conversion during admission.
    _, record, _, _ = collection
    record['sha256'] = sha256(wav)
    result = validate_collection(write(), dev, CHECKLIST)
    assert result['files'][0]['modality'] == 'stereo-candidate'
    assert result['files'][0]['spatial_signal_candidate'] is True


def test_non_spatial_manifest_zones_and_pilot_exclusion(collection):
    wav, record, write, dev = collection
    audio, rate = sf.read(wav)
    sf.write(wav, audio[:, 0], rate, subtype='PCM_16')
    record.update(sha256=sha256(wav), evaluation_mode='non-spatial')
    record['events'][0]['zone'] = None
    assert validate_collection(write(), dev, CHECKLIST)['files'][0]['modality'] == 'mono'
    record['events'][0]['zone'] = 'LEFT'
    with pytest.raises(ValueError, match='event label'):
        validate_collection(write(), dev, CHECKLIST)
    record['events'][0]['zone'] = None
    record['dataset_role'] = 'pilot'
    with pytest.raises(ValueError, match='pilot/development'):
        validate_collection(write(), dev, CHECKLIST)


@pytest.mark.parametrize('name,subtype', [('pilot_background_01.wav', 'PCM_16'),
                                        ('pilot_background_01_24bit.wav', 'PCM_24')])
def test_local_genuine_pilot_read_only(name, subtype):
    # Optional local assets; portable fixture coverage above always runs.
    wav = Path(__file__).resolve().parents[2] / name
    if not wav.exists():
        pytest.skip('local genuine pilot is not distributed with source')
    before = sha256(wav)
    result = check_wav(wav, 'non-spatial')
    assert result['subtype'] == subtype and result['modality'] == 'dual-mono'
    assert result['spatial_eligible'] is False
    with pytest.raises(ValueError, match='dual-mono'):
        check_wav(wav)
    assert sha256(wav) == before


def test_lossless_conversion_cannot_bypass_leakage(collection):
    from echotrace.eval.dataset import load_manifest
    wav, record, write, dev = collection
    mono = np.random.default_rng(3).uniform(-.01, .01, 48000 * 30)
    source = dev / 'previous-pilot.wav'
    sf.write(source, mono, 48000, subtype='PCM_16')
    samples, rate = sf.read(source)
    sf.write(wav, np.column_stack([samples, samples]), rate, subtype='PCM_24')
    record.update(sha256=sha256(wav), evaluation_mode='non-spatial')
    record['events'][0]['zone'] = None
    with pytest.raises(ValueError, match='duplicate audio'):
        load_manifest(write(), dev)
