"""End-to-end evaluation CLI with temporary noise and a scripted tagger.

These are infrastructure fixtures, never independent scientific recordings.
"""
import importlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest
import soundfile as sf

from echotrace import config
from echotrace.eval.dataset import sha256


def test_freeze_replay_drift_and_preserve_outputs(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    cli = importlib.import_module('research_eval')
    import echotrace.pipeline as pipeline
    test = tmp_path / 'recordings/test'
    test.mkdir(parents=True)
    (tmp_path / 'backend').mkdir()
    (tmp_path / 'backend/requirements.txt').write_text('unit fixture')
    (tmp_path / 'docs/research').mkdir(parents=True)
    model = tmp_path / 'panns_data'
    model.mkdir()
    weights = model / 'Cnn14_mAP=0.431.pth'
    labels_file = model / 'class_labels_indices.csv'
    weights.write_bytes(b'not a model: never loaded')
    labels_file.write_text('not real labels: never loaded')
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(config, 'WEIGHTS_FILE', weights)
    monkeypatch.setattr(config, 'LABELS_FILE', labels_file)
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'MANIFEST', test / 'manifest.json')
    monkeypatch.setattr(cli, 'environment', lambda: {'unit_fixture': True})
    wav = test / 'fixture.wav'
    sf.write(wav, np.random.default_rng(0).normal(0, .01, (48000 * 10, 2)), 48000, subtype='PCM_16')
    record = {'recording_id': 'unit-fixture', 'wav': wav.name, 'sha256': sha256(wav),
              'source': 'unit fixture only', 'date': '2026-11-08', 'device': 'unit fixture',
              'environment': 'unit fixture', 'annotator': 'test code', 'duration_s': 10.0,
              'used_for_tuning': False, 'category_labels': ['GLASS', 'ALARM'],
              'ground_truth_risk': 'GREEN', 'incidents': [],
              'events': [{'id': str(n), 'start_s': a, 'end_s': b, 'category': c, 'zone': 'LEFT'}
                         for n, (a, b, c) in enumerate([(0, 3, 'GLASS'), (5, 8, 'ALARM')])]}
    cli.MANIFEST.write_text(json.dumps({'schema_version': 1, 'split': 'independent-test',
                                       'recordings': [record]}))

    class ScriptedTagger:
        device = 'cpu'
        labels = list(dict.fromkeys(label for labels in config.CATEGORIES.values() for label in labels))

        def __init__(self):
            self.n = 0

        def tag(self, window):
            probs = np.zeros(len(self.labels), np.float32)
            cat = 'Glass' if self.n < 4 else 'Alarm' if 10 <= self.n < 14 else None
            if cat:
                probs[self.labels.index(cat)] = .95
            self.n += 1
            return probs

    monkeypatch.setattr(pipeline, 'default_tagger', lambda **kwargs: ScriptedTagger())
    lock = tmp_path / 'docs/research/lock.json'

    def invoke(action, run_id=None):
        argv = ['research_eval.py', action, '--lock', str(lock)]
        if run_id:
            argv += ['--run-id', run_id]
        monkeypatch.setattr(sys, 'argv', argv)
        cli.main()

    invoke('freeze')
    invoke('run', 'first')
    invoke('run', 'second')
    outputs = tmp_path / 'docs/research/runs/independent-test'
    first = (outputs / 'first/results.json').read_text()
    assert first == (outputs / 'second/results.json').read_text()
    result = json.loads(first)
    metrics = result['per_recording'][0]['metrics']
    assert metrics['A_per_event']['fp'] > 0
    assert metrics['D_EchoTrace']['fp'] == 0
    assert len(metrics) == 4
    with pytest.raises(FileExistsError):
        invoke('run', 'first')
    with pytest.raises(FileExistsError):
        invoke('freeze')
    # Dataset/config drift invalidates a lock before another inference run.
    (tmp_path / 'backend/requirements.txt').write_text('changed fixture environment')
    with pytest.raises(SystemExit) as error:
        invoke('run', 'drift')
    assert error.value.code == 2
    assert not (outputs / 'drift').exists()
