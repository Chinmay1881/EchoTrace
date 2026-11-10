"""Inventory original evidence without filling missing provenance or annotations."""
import json
from pathlib import Path
import _bootstrap  # noqa
from echotrace.eval.dataset import audio_identity, sha256

root = Path(__file__).resolve().parents[2]
records = []
for label in sorted((root / 'recordings/eval/labels').glob('*.json')):
    d = json.loads(label.read_text())
    wav = root / 'recordings/eval' / d['wav']
    records.append({'recording_id': d['clip'], 'wav': str(wav.relative_to(root)),
                    'sha256': sha256(wav), **audio_identity(wav),
                    'source': 'self-recorded staged playback (aggregate docs/metrics.md description)',
                    'date': None, 'device': None, 'environment': None,
                    'category_labels': [e['category'] for e in d['events']],
                    'event_timing': None, 'ground_truth_risk': d['expected_risk'],
                    'legacy_annotation': d, 'annotation_sha256': sha256(label),
                    'used_for_tuning': True})
print(json.dumps({'schema_version': 1, 'split': 'development', 'recordings': records,
                  'missing_fields_note': 'Unknown per-recording provenance/timing remains null; not a held-out manifest.'}, indent=2))
