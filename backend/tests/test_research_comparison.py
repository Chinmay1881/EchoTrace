"""Handcrafted infrastructure fixtures only: no scientific accuracy claims."""
import copy
from datetime import datetime
import json

import pytest

from echotrace.audio.sources import SourceInfo, SimSource
from echotrace.events import Event
from echotrace.pipeline import Analyzer, Pipeline
from echotrace.eval.comparison import compare_analyzer, score


def replay_fixture(categories):
    an = Analyzer(SourceInfo('RECORDED', 'unit fixture', 'none', 48000, 2),
                  start_wall=datetime(2000, 1, 1))
    messages = []
    for n, (category, time) in enumerate(categories):
        ev = Event(f'e{n}', time - .5, time, category, category, .9, 'LEFT', -30,
                   capture_time=12345 + n, zone_confidence='high')
        messages.extend(m for m, _ in an.add_event(ev))
    return messages, an


def test_all_systems_share_upstream_and_common_ground_truth():
    messages, an = replay_fixture([('GLASS', 2), ('IMPACT', 4), ('ALARM', 6)])
    record = {'recording_id': 'unit-positive', 'duration_s': 20,
              'incidents': [{'id': 'i', 'start_s': 1, 'end_s': 8, 'risk': 'RED'}]}
    before = copy.deepcopy(an.events)
    result = compare_analyzer(messages, an, record)
    assert an.events == before
    assert len(result['events']) == 3
    assert len(result['alerts']) == 4
    for name, alerts in result['alerts'].items():
        assert all(a['event_id'] in {e.id for e in an.events} for a in alerts)
        assert result['metrics'][name] == score(alerts, record['incidents'], 20)
        assert result['metrics'][name]['tp'] == 1
    assert len(result['alerts']['A_per_event']) == len(an.baseline.alerts) == 3
    assert len(result['alerts']['D_EchoTrace']) == 2  # escalation counts once TP, once duplicate FP
    assert result['metrics']['D_EchoTrace']['duplicates'] == 1
    assert result['metrics']['D_EchoTrace']['fp'] == 1


def test_benign_multi_event_negative_uses_incidents_not_categories():
    messages, an = replay_fixture([('GLASS', 2), ('ALARM', 4)])
    record = {'recording_id': 'unit-benign', 'duration_s': 20, 'incidents': []}
    result = compare_analyzer(messages, an, record)
    assert result['metrics']['A_per_event']['fp'] == 2
    assert result['metrics']['D_EchoTrace']['fp'] == 0
    assert all(m['tp'] == 0 and m['fn'] == 0 for m in result['metrics'].values())
    assert all(m['recall'] is None for m in result['metrics'].values())


def test_machine_readable_results_ignore_host_clock():
    messages, an = replay_fixture([('GLASS', 2), ('ALARM', 4)])
    record = {'recording_id': 'fixture', 'duration_s': 20, 'incidents': []}
    first = json.dumps(compare_analyzer(messages, an, record), sort_keys=True, allow_nan=False)
    for event in an.events:
        event.capture_time += 1000
    second = json.dumps(compare_analyzer(messages, an, record), sort_keys=True, allow_nan=False)
    assert first == second
    assert 'capture_time' not in first


def test_full_simulated_pipeline_comparison_is_repeatable():
    record = {'recording_id': 'simulated-unit-fixture', 'duration_s': 60,
              'incidents': [{'id': 'fixture-incident', 'start_s': 0, 'end_s': 35, 'risk': 'RED'}]}
    results = []
    for _ in range(2):
        pipeline = Pipeline(SimSource(realtime=False, loops=1, scenario='breakin'),
                            start_wall=datetime(2000, 1, 1), record_latency=False)
        messages = pipeline.run_to_end()
        results.append(compare_analyzer(messages, pipeline.analyzer, record))
    assert results[0] == results[1]
    assert results[0]['alerts']['D_EchoTrace']


@pytest.mark.parametrize('time,expected', [(0.999, 0), (1, 1), (5, 1), (5.001, 0)])
def test_matching_tolerance_boundary(time, expected):
    assert score([{'t': time}], [{'start_s': 2, 'end_s': 4}], 10)['tp'] == expected
