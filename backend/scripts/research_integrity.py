"""Verify development file preservation, exact duplicate identities and inventory."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import _bootstrap  # noqa
from echotrace.eval.dataset import audio_identity, sha256

root = Path(__file__).resolve().parents[2]
files = sorted((root / 'recordings/eval').glob('*.wav'))
file_hashes = [sha256(p) for p in files]
pcm_hashes = [audio_identity(p)['pcm_sha256'] for p in files]
protected = files + sorted((root / 'recordings/eval/labels').glob('*.json'))
protected += [root / p for p in ['docs/metrics.json', 'docs/metrics.md',
                               'backend/echotrace/config.py', 'backend/echotrace/pipeline.py']]
unchanged = {str(p.relative_to(root)): hashlib.sha256(subprocess.check_output(
    ['git', 'show', f'HEAD:{p.relative_to(root)}'], cwd=root)).hexdigest() == sha256(p) for p in protected}
inventory = json.loads(subprocess.check_output([sys.executable, str(root / 'backend/scripts/research_inventory.py')]))
result = {'development_recordings': len(files), 'unique_file_hashes': len(set(file_hashes)),
          'unique_pcm_hashes': len(set(pcm_hashes)), 'protected_files_equal_HEAD': unchanged,
          'model_sha256': sha256(Path.home() / 'panns_data/Cnn14_mAP=0.431.pth'),
          'labels_sha256': sha256(Path.home() / 'panns_data/class_labels_indices.csv'),
          'inventory_matches': inventory == json.loads((root / 'docs/research/development-inventory.json').read_text())}
print(json.dumps(result, indent=2))
if not (len(files) == len(set(file_hashes)) == len(set(pcm_hashes)) == 10
        and all(unchanged.values()) and result['inventory_matches']):
    raise SystemExit(1)
