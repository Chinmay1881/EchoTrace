"""Verify real scientific imports and report versions/hardware; no inference timing."""
import importlib
import importlib.metadata
import json
import os
import platform
import sys
import _bootstrap  # noqa


def main():
    result = {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
              'logical_cpus': os.cpu_count(), 'packages': {}, 'imports': {}}
    for package in ['numpy', 'scipy', 'torch', 'sounddevice', 'soundfile', 'librosa', 'numba',
                    'torchlibrosa', 'panns_inference', 'pytest', 'fastapi', 'pydantic', 'httpx']:
        try:
            result['packages'][package] = importlib.metadata.version(package)
            importlib.import_module(package)
            result['imports'][package] = 'ok'
        except Exception as e:
            result['imports'][package] = f'{type(e).__name__}: {e}'
    for module in ['echotrace.pipeline', 'echotrace.eval.metrics', 'echotrace.eval.dataset',
                   'echotrace.eval.comparison']:
        try:
            importlib.import_module(module)
            result['imports'][module] = 'ok'
        except Exception as e:
            result['imports'][module] = f'{type(e).__name__}: {e}'
    try:
        import torch
        result['cuda_available'] = torch.cuda.is_available()
        result['torch_cuda_version'] = torch.version.cuda
        result['torch_threads'] = torch.get_num_threads()
        import sounddevice
        result['audio_devices'] = str(sounddevice.query_devices())
    except Exception as e:
        result['hardware_error'] = str(e)
    print(json.dumps(result, indent=2))
    return int(any(value != 'ok' for value in result['imports'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
