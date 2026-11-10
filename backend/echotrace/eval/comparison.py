"""Predeclared incident alert accounting; independent of classifier dependencies."""
CONCERNING = {'IMPACT', 'DISTRESS', 'ALARM', 'GLASS'}


def compare_analyzer(messages, analyzer, record, cooldown_s=10.0, tolerance_s=1.0):
    """One replay feeds every system; persist stream times, never host capture clocks."""
    from dataclasses import asdict
    emissions = {m['data']['id']: m['data']['t'] for m in messages if m['type'] == 'event'}
    events = []
    for event in analyzer.events:
        item = asdict(event)
        item.pop('capture_time')  # monotonic host clock varies between identical offline runs
        item['emitted_s'] = emissions[event.id]
        events.append(item)
    systems = baselines(events, cooldown_s)
    systems['D_EchoTrace'] = [dict(a) for a in analyzer.alerts]
    return {'recording_id': record['recording_id'], 'events': events, 'alerts': systems,
            'metrics': {name: score(alerts, record['incidents'], record['duration_s'], tolerance_s)
                        for name, alerts in systems.items()}}


def baselines(events, cooldown_s=10.0):
    out = {'A_per_event': [], 'B_global_cooldown': [], 'C_category_cooldown': []}
    last_global, last_category = -float('inf'), {}
    for e in sorted(events, key=lambda e: (e['emitted_s'], e['id'])):
        if e['category'] not in CONCERNING:
            continue
        alert = {'t': e['emitted_s'], 'event_id': e['id']}
        out['A_per_event'].append(alert)
        if alert['t'] - last_global >= cooldown_s:
            out['B_global_cooldown'].append(alert)
            last_global = alert['t']
        if alert['t'] - last_category.get(e['category'], -float('inf')) >= cooldown_s:
            out['C_category_cooldown'].append(alert)
            last_category[e['category']] = alert['t']
    return out


def score(alerts, incidents, duration_s, tolerance_s=1.0):
    """Maximum cardinality interval matching; chronological greedy earliest deadline.

    Any alert is an incident alarm irrespective of category/risk; severity separately.
    Duplicate = unmatched alert in any incident acceptance interval; still FP.
    """
    assigned, tp, duplicate = set(), 0, 0
    for a in sorted(alerts, key=lambda a: a['t']):
        eligible = [j for j, i in enumerate(incidents)
                    if i['start_s'] - tolerance_s <= a['t'] <= i['end_s'] + tolerance_s]
        free = [j for j in eligible if j not in assigned]
        if free:
            j = min(free, key=lambda j: (incidents[j]['end_s'], j))
            assigned.add(j)
            tp += 1
        elif eligible:
            duplicate += 1
    fp, fn = len(alerts) - tp, len(incidents) - tp
    return {'tp': tp, 'fp': fp, 'fn': fn, 'duplicates': duplicate,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            'false_alarms_per_hour': fp * 3600 / duration_s if duration_s else None}
