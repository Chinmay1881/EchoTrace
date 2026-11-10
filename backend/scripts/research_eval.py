"""Independent evaluation: validate, freeze protocol, then replay unchanged pipeline."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

import _bootstrap  # noqa
from echotrace.eval.dataset import load_manifest, sha256
from echotrace.eval.comparison import compare_analyzer

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'recordings/test/manifest.json'
PROTOCOL = {'cooldown_s': 10.0, 'matching_tolerance_s': 1.0,
            'unit': 'any incident alarm; severity and pattern not required for binary matching',
            'assignment': 'chronological alerts, earliest-ending unmatched eligible incident',
            'duplicates': 'unmatched alerts inside an incident interval remain false positives'}


def snapshot():
    paths = sorted((ROOT / 'backend/echotrace').rglob('*.py'))
    paths += [Path(__file__), MANIFEST]
    paths += sorted((ROOT / 'recordings/eval/labels').glob('*.json'))
    paths += sorted((ROOT / 'recordings/eval').glob('*.wav'))
    paths += sorted((ROOT / 'recordings/test').rglob('*.wav'))
    paths += [ROOT / 'backend/requirements.txt']
    # Collection definitions must not drift after a future dataset lock either.
    for relative in ('docs/research/collection-protocol.md', 'docs/research/collection-checklist.csv',
                     'backend/scripts/research_validate.py'):
        if (ROOT / relative).exists():
            paths.append(ROOT / relative)
    for p in [ROOT / 'backend/calibration.json', Path.home() / 'panns_data/Cnn14_mAP=0.431.pth',
              Path.home() / 'panns_data/class_labels_indices.csv']:
        if p.exists():
            paths.append(p)
    return {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): sha256(p) for p in paths}


def environment():
    return {'python': sys.version, 'packages': subprocess.check_output(
        [sys.executable, '-m', 'pip', 'freeze'], text=True)}


def write_new(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['validate', 'freeze', 'run'])
    p.add_argument('--lock', type=Path, default=ROOT / 'docs/research/protocol-lock.json')
    p.add_argument('--run-id', help='new directory name; existing outputs are never overwritten')
    args = p.parse_args()
    data = load_manifest(MANIFEST, ROOT / 'recordings/eval')
    if args.action == 'validate':
        print(json.dumps({'status': 'ready' if data['recordings'] else 'pending independent recordings',
                          'recordings': len(data['recordings'])}))
        return
    if not data['recordings']:
        p.error('independent testing pending: no recordings; cannot freeze or evaluate an empty dataset')
    if args.action == 'freeze':
        if not (Path.home() / 'panns_data/Cnn14_mAP=0.431.pth').is_file() or not (
                Path.home() / 'panns_data/class_labels_indices.csv').is_file():
            p.error('supply model weights and AudioSet labels before freezing')
        write_new(args.lock, {'protocol': PROTOCOL, 'sha256': snapshot(),
                              'environment': environment(),
                              'frozen_at': datetime.now(timezone.utc).isoformat()})
        print(args.lock)
        return
    lock = json.loads(args.lock.read_text())
    if (lock['protocol'] != PROTOCOL or lock['sha256'] != snapshot()
            or lock.get('environment') != environment()):
        p.error('protocol/source/data/model drift: restore frozen inputs; do not re-freeze to tune test results')
    if not args.run_id or Path(args.run_id).name != args.run_id or args.run_id in {'.', '..'}:
        p.error('--run-id must be a new simple directory name')
    # Imports deferred: annotation validation needs no model or scientific dependencies.
    from echotrace.pipeline import default_tagger, run_wav_detailed
    from echotrace import config
    if not config.WEIGHTS_FILE.exists() or not config.LABELS_FILE.exists():
        p.error('model weights and AudioSet labels must exist before freezing/running')
    output = ROOT / 'docs/research/runs/independent-test' / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    tagger = default_tagger(force_cpu=True)
    rows = []
    for record in data['recordings']:
        messages, analyzer = run_wav_detailed(MANIFEST.parent / record['wav'], tagger, keep_frames=False)
        rows.append(compare_analyzer(messages, analyzer, record, PROTOCOL['cooldown_s'],
                                     PROTOCOL['matching_tolerance_s']))
    totals = {}
    for system in rows[0]['metrics']:
        counts = {k: sum(r['metrics'][system][k] for r in rows) for k in ('tp', 'fp', 'fn', 'duplicates')}
        tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
        totals[system] = {**counts, 'precision': tp / (tp + fp) if tp + fp else None,
                          'recall': tp / (tp + fn) if tp + fn else None,
                          'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
                          'false_alarms_per_recording': fp / len(rows),
                          'false_alarms_per_hour': fp * 3600 / sum(r['duration_s'] for r in data['recordings'])}
    result = {'split': 'independent-test', 'protocol_lock': lock, 'per_recording': rows, 'aggregate': totals,
              'python': sys.version, 'platform': platform.platform(),
              'software': subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True),
              'latency': None, 'latency_note': 'offline replay; no real-time latency measurement'}
    write_new(output / 'results.json', result)
    lines = ['# Independent test', '', '| System | TP | FP | FN | Duplicate | Precision | Recall | F1 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, m in totals.items():
        values = [str(m[k]) if m[k] is not None else 'undefined' for k in
                  ('tp', 'fp', 'fn', 'duplicates', 'precision', 'recall', 'f1')]
        lines.append('| ' + ' | '.join([name] + values) + ' |')
    (output / 'summary.md').write_text('\n'.join(lines) + '\n')
    print(output)

if __name__ == '__main__':
    main()
