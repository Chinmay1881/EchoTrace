"""Read-only pre-inference collection validation; never loads a tagger or records audio."""
import argparse
import json
import wave
from pathlib import Path
import _bootstrap  # noqa
from echotrace.eval.collection import check_wav, validate_collection

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'recordings/test/manifest.json')
    parser.add_argument('--development', type=Path, default=ROOT / 'recordings/eval')
    parser.add_argument('--checklist', type=Path, default=ROOT / 'docs/research/collection-checklist.csv')
    parser.add_argument('--wav', type=Path, help='format/QC only for one take; does not validate annotations')
    parser.add_argument('--evaluation-mode', choices=['localization', 'non-spatial'], default='localization',
                        help='file QC only; manifests declare evaluation_mode per recording')
    parser.add_argument('--dataset-role', choices=['pilot', 'development', 'independent-test'], default='pilot',
                        help='file QC provenance label only; never admits a recording to a dataset')
    parser.add_argument('--require-complete', action='store_true', help='reject a partial collection')
    args = parser.parse_args()
    try:
        if not args.wav and (args.evaluation_mode != 'localization' or args.dataset_role != 'pilot'):
            raise ValueError('mode/role options apply only to --wav; independent manifests declare recording modes')
        result = ({'status': 'format/QC only; annotations not checked', 'dataset_role': args.dataset_role, 'independent_admission': False,
                   'file': check_wav(args.wav, args.evaluation_mode),
                   'inference_performed': False} if args.wav else
                  validate_collection(args.manifest, args.development, args.checklist))
        if args.require_complete and (args.wav or result['missing_clip_ids']):
            raise ValueError('complete manifest with all 36 planned clips required')
    except (ValueError, TypeError, KeyError, OSError, EOFError, RuntimeError, wave.Error) as exc:
        print(json.dumps({'status': 'not ready', 'error': str(exc), 'inference_performed': False}))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
