"""Preserve a fresh ten-clip development reproduction, including confidence evidence.

Never assigns incident timing to legacy labels or writes docs/metrics.*.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import _bootstrap  # noqa
import eval as legacy
from echotrace import config
from echotrace.eval.metrics import build_metrics
from research_eval import snapshot, environment, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new JSON file (exclusive creation)')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; preserve previous evidence')
    labels = [json.loads(p.read_text()) for p in sorted(legacy.EVAL_DIR.glob('labels/*.json'))]
    tagger = legacy.default_tagger(force_cpu=True)
    results, profile = legacy.evaluate(config.SENSITIVITY, labels, tagger)
    metrics = build_metrics(results, {'mean': None, 'p95': None, 'n': 0, 'sources': [],
                                     'note': 'offline replay; no latency measured'})
    archived = json.loads((config.DOCS_DIR / 'metrics.json').read_text())
    data = {'split': 'development', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'environment': environment(), 'sha256': snapshot(), 'profile': profile,
            'metrics': metrics, 'per_event': {r.clip: r.events for r in results},
            'comparison_to_archive': {k: {'archived': archived[k], 'reproduced': metrics[k],
                                          'equal': archived[k] == metrics[k]}
                                      for k in ['sequence_accuracy', 'totals', 'lcr', 'detection', 'per_clip']}}
    write_new(args.output, data)
    print(json.dumps(data['comparison_to_archive'], indent=2))


if __name__ == '__main__':
    main()
