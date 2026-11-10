"""Infrastructure checks; generated silence is a test fixture only."""
import copy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
import wave

from echotrace.eval.dataset import load_manifest, sha256
from echotrace.eval.comparison import baselines, score


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dev = self.root / 'dev'
        self.dev.mkdir()
        self.test = self.root / 'test'
        self.test.mkdir()
        self.wav = self.test / 'fixture.wav'
        with wave.open(str(self.wav), 'wb') as f:
            f.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            f.writeframes(b'\0' * 48000 * 4)
        self.record = {'recording_id': 'fixture', 'wav': 'fixture.wav', 'sha256': sha256(self.wav),
                       'source': 'unit test only', 'date': '2026-11-08', 'device': 'fixture',
                       'environment': 'temporary test', 'annotator': 'test', 'duration_s': 1.0,
                       'used_for_tuning': False, 'ground_truth_risk': 'GREEN', 'evaluation_mode': 'non-spatial',
                       'category_labels': [], 'events': [], 'incidents': []}

    def validate(self, records=None):
        p = self.test / 'manifest.json'
        p.write_text(json.dumps({'schema_version': 1, 'split': 'independent-test',
                                 'recordings': [self.record] if records is None else records}))
        return load_manifest(p, self.dev)

    def test_valid_benign(self):
        self.assertEqual(len(self.validate()['recordings']), 1)

    def test_missing_and_malformed(self):
        original = copy.deepcopy(self.record)
        for key in original:
            with self.subTest(key=key):
                self.record = copy.deepcopy(original)
                del self.record[key]
                with self.assertRaises((ValueError, TypeError)):
                    self.validate()
        self.record = original
        for change in [{'duration_s': float('nan')}, {'used_for_tuning': True},
                       {'wav': '../outside.wav'}, {'ground_truth_risk': 'RED'},
                       {'events': [{'id': 'e', 'start_s': 0, 'end_s': 2}]}]:
            self.record = {**original, **change}
            with self.assertRaises(ValueError):
                self.validate()

    def test_duplicate_development(self):
        (self.dev / 'original.wav').write_bytes(self.wav.read_bytes())
        with self.assertRaisesRegex(ValueError, 'duplicate audio'):
            self.validate()

    def test_missing_annotations(self):
        with self.assertRaisesRegex(ValueError, 'unannotated'):
            self.validate([])

    def test_benign_multi_event(self):
        self.record['events'] = [{'id': str(i), 'start_s': i / 2, 'end_s': i / 2 + .1,
                                 'category': cat, 'zone': None} for i, cat in enumerate(['GLASS', 'ALARM'])]
        self.record['category_labels'] = ['GLASS', 'ALARM']
        self.validate()

    def test_baseline_emission_clock_and_cooldowns(self):
        events = [{'id': str(i), 'category': cat, 'emitted_s': t}
                  for i, (cat, t) in enumerate([('GLASS', 0), ('ALARM', 1), ('GLASS', 2), ('GLASS', 10)])]
        b = baselines(events)
        self.assertEqual([len(v) for v in b.values()], [4, 2, 3])

    def test_incident_assignment_duplicates_and_misses(self):
        incidents = [{'start_s': 2, 'end_s': 4}, {'start_s': 8, 'end_s': 9}]
        m = score([{'t': t} for t in [1, 3, 15]], incidents, 20)
        self.assertEqual([m[k] for k in ('tp', 'fp', 'fn', 'duplicates')], [1, 2, 1, 1])
        self.assertEqual(m['precision'], 1 / 3)
        self.assertIsNone(score([], [], 20)['f1'])

    def test_cli_pending_and_freeze_rejection(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/research_eval.py'
        result = subprocess.run([sys.executable, str(script), 'validate'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['recordings'], 0)
        result = subprocess.run([sys.executable, str(script), 'freeze'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no recordings', result.stderr)

    def test_pcm_duplicates_ignore_container_metadata(self):
        # Append a harmless RIFF metadata chunk; byte hash differs, PCM identity stays equal.
        import struct
        raw = bytearray(self.wav.read_bytes())
        raw.extend(b'JUNK' + struct.pack('<I', 4) + b'test')
        struct.pack_into('<I', raw, 4, len(raw) - 8)
        (self.dev / 'with_metadata.wav').write_bytes(raw)
        self.assertNotEqual(sha256(self.wav), sha256(self.dev / 'with_metadata.wav'))
        with self.assertRaisesRegex(ValueError, 'duplicate audio'):
            self.validate()

    def test_overlapping_incidents_earliest_deadline(self):
        m = score([{'t': 2}, {'t': 5}], [{'start_s': 0, 'end_s': 8},
                                       {'start_s': 1, 'end_s': 2}], 10, 0)
        self.assertEqual(m['tp'], 2)

if __name__ == '__main__':
    unittest.main()
