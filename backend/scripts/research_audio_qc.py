"""Non-predictive recording quality check plus incomplete annotation scaffold.

Output is a collection aid, NOT a valid annotation or research finding.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import soundfile as sf
import _bootstrap  # noqa
from echotrace.audio.devices import channel_report
from echotrace.eval.dataset import sha256, audio_identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav', type=Path)
    args = parser.parse_args()
    x, rate = sf.read(args.wav, dtype='float32', always_2d=True)
    report = {'path': str(args.wav), **audio_identity(args.wav), 'sha256': sha256(args.wav),
              'finite': bool(np.isfinite(x).all()), 'peak': float(np.abs(x).max()) if x.size else None,
              'clipped_sample_fraction': float(np.mean(np.abs(x) >= .999)) if x.size else None}
    if x.shape[1] == 2 and len(x):
        channels = channel_report(x)
        report['channels_identical'] = bool(channels.identical)
        report['silent'] = bool(channels.silent)
        report['channel_correlation'] = float(channels.corr)
    report['annotation_scaffold_INCOMPLETE'] = {
        'recording_id': args.wav.stem, 'wav': args.wav.name, 'sha256': report['sha256'],
        'duration_s': report['duration_s'], 'source': None, 'date': None, 'device': None,
        'environment': None, 'annotator': None, 'used_for_tuning': False,
        'category_labels': [], 'ground_truth_risk': None, 'events': [], 'incidents': []}
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
