"""Evaluate EchoTrace on the labelled clips vs a classification-only baseline.

Every clip in recordings/eval/labels/*.json is replayed through the SAME pipeline as LIVE (same config, gain,
thresholds and calibration), faster than real time. Writes docs/metrics.json (served by /api/metrics) and
docs/metrics.md, and prints a table. Latency comes only from live runs (recordings/run_*_events.jsonl).

  python scripts/eval.py
  python scripts/eval.py --cpu --no-write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401
from echotrace import config
from echotrace.eval.metrics import ClipResult, build_metrics, latency_from_logs
from echotrace.pipeline import default_tagger, run_wav_detailed

EVAL_DIR = config.RECORDINGS_DIR / "eval"
LIMITATIONS = ("Small self-recorded dataset (10 x 25 s clips), one room, one laptop microphone array "
               "(6.5 cm spacing), clips played from a phone; LEFT/CENTRE/RIGHT zones only (no front/back); "
               "FOOTSTEPS and DISTRESS are not yet reliable and are not part of this set.")


def run_clip(label: dict, tagger) -> ClipResult:
    wav = EVAL_DIR / label["wav"]
    _, an = run_wav_detailed(wav, tagger, keep_frames=False, start_wall=datetime(2026, 1, 1))
    events = [{"id": e.id, "category": e.category, "zone": e.zone, "confidence": e.confidence,
               "label": e.label, "t_start": e.t_start, "t_end": e.t_end} for e in an.events]
    return ClipResult(label["clip"], label["expected_pattern"], label["expected_risk"], label["events"],
                      events, list(an.alerts), len(an.baseline.alerts))


def fmt_pct(v) -> str:
    return "n/a" if v is None else f"{v * 100:.0f}%"


def table(results: list[ClipResult]) -> list[str]:
    rows = [("clip", "expected", "got", "events (category@zone)", "Echo", "Base", "ok")]
    for r in results:
        evs = ", ".join(f"{e['category']}@{e['zone']}" for e in r.events) or "-"
        rows.append((r.clip, r.expected, r.got_str, evs, str(len(r.alerts)), str(r.baseline_alerts),
                     "OK" if r.ok else "FAIL"))
    w = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    w[3] = min(w[3], 60)
    out = []
    for i, row in enumerate(rows):
        cells = [c if j != 3 or len(c) <= 60 else c[:57] + "..." for j, c in enumerate(row)]
        out.append("  ".join(c.ljust(w[j]) for j, c in enumerate(cells)))
        if i == 0:
            out.append("  ".join("-" * x for x in w))
    return out


def failure_reason(r: ClipResult) -> str:
    """Plain explanation of a failed clip, derived from what was detected (not hand-written)."""
    found = {e["category"] for e in r.events}
    missing = [lab["category"] for lab in r.labelled if lab["category"] not in found]
    if r.expected_risk == "GREEN":
        return f"expected no alert, got {r.got_str} (spurious alert)"
    if missing:
        return (f"labelled {', '.join(missing)} not detected (no event above threshold), so the "
                f"{r.expected_pattern} chain could not form; got {r.got_str}")
    order = " -> ".join(e["category"] for e in sorted(r.events, key=lambda e: e["t_start"]))
    return (f"all labelled categories detected, but not in the labelled order within the pattern's gap limit "
            f"(detected order: {order}); got {r.got_str}")


def misses_are_detection_misses(results: list[ClipResult]) -> bool:
    """True only if, for every failed clip, the expected pattern genuinely cannot be formed from what was
    detected (re-checked here with the pattern matcher on the detected events, ignoring sequence boundaries).
    If the detections did contain the chain, the miss would be the correlation logic's fault -> False."""
    from echotrace.correlation.patterns import PATTERNS, match_pattern
    from echotrace.events import Event
    by_name = {p.name: p for p in PATTERNS}
    for r in results:
        if r.ok:
            continue
        if r.expected_pattern not in by_name:            # expected NONE but got an alert: not a detection miss
            return False
        evs = [Event(e["id"], e["t_start"], e["t_end"], e["category"], e["label"], e["confidence"], e["zone"], None)
               for e in r.events]
        if match_pattern(evs, by_name[r.expected_pattern]) is not None:
            return False
    return True


def safer_line(m: dict, results: list[ClipResult]) -> str:
    fa, tot = m["false_alerts_detail"], m["totals"]
    line = (f"Across {m['clips']} self-recorded clips, EchoTrace raised {tot['echotrace_alerts']} alerts vs "
            f"{tot['baseline_alerts']} for a classification-only baseline; on the {fa['clips']} no-incident clips, "
            f"{fa['echotrace']} vs {fa['baseline']}.")
    if any(not r.ok for r in results) and misses_are_detection_misses(results):
        line += " Every miss was a detection miss; the correlation logic was correct on everything detected."
    return line


def headline(m: dict) -> str:
    fa = m["false_alerts"]
    lat = m["latency_ms"]["mean"]
    red = "n/a" if fa["reduction_pct"] is None else f"-{fa['reduction_pct']:.0f}%"
    return (f"Across {m['clips']} clips: {fmt_pct(m['sequence_accuracy'])} sequence accuracy, "
            f"{fmt_pct(m['lcr_accuracy'])} L/C/R accuracy, EchoTrace raised {fa['echotrace']} false alerts vs "
            f"{fa['baseline']} for the classification-only baseline ({red}), "
            + (f"~{lat:.0f} ms latency (live, mean)." if lat is not None else "latency not measured in this run."))


def markdown(m: dict, results: list[ClipResult]) -> str:
    fa, lc, lat = m["false_alerts_detail"], m["lcr"], m["latency_detail"]
    tot = m["totals"]
    md = [
        "# EchoTrace evaluation",
        "",
        f"Generated {m['generated_at']} by `backend/scripts/eval.py` on {m['clips']} labelled clips "
        "(`recordings/eval/`), replayed through the same pipeline as live mode.",
        "",
        f"**{safer_line(m, results)}**",
        "",
        f"Sequence recognition accuracy {fmt_pct(m['sequence_accuracy'])} "
        f"({sum(r.ok for r in results)}/{len(results)} clips); L/C/R accuracy {fmt_pct(m['lcr_accuracy'])}; "
        + ("latency not measured yet (no live-run log)." if m['latency_ms']['mean'] is None else
           f"latency {m['latency_ms']['mean']:.0f} ms mean, {m['latency_ms']['p95']:.0f} ms p95 (live)."),
        "",
        "| Metric | EchoTrace | Classification-only baseline |",
        "|---|---|---|",
        f"| Sequence recognition accuracy (risk + pattern) | {fmt_pct(m['sequence_accuracy'])} | n/a (no sequences) |",
        f"| False alerts on {fa['clips']} non-incident clips | {fa['echotrace']} | {fa['baseline']} |",
        f"| False-alert reduction | {'n/a' if fa['reduction_pct'] is None else str(fa['reduction_pct']) + '%'} | |",
        f"| Total alerts, all clips | {tot['echotrace_alerts']} | {tot['baseline_alerts']} |",
        f"| L/C/R accuracy ({lc['events']} events, {lc['unknown']} UNKNOWN counted wrong) | "
        f"{fmt_pct(lc['accuracy'])} | n/a |",
        f"| Latency mean / p95 | {'not measured' if lat['mean'] is None else f'{lat['mean']:.0f} / {lat['p95']:.0f} ms'} | |",
        "",
        "## Per clip",
        "",
        "| Clip | Expected | Got | Events (category@zone) | EchoTrace alerts | Baseline alerts | OK |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        evs = ", ".join(f"{e['category']}@{e['zone']}" for e in r.events) or "-"
        md.append(f"| {r.clip} | {r.expected} | {r.got_str} | {evs} | {len(r.alerts)} | {r.baseline_alerts} | "
                  f"{'yes' if r.ok else '**no**'} |")
    failed = [r for r in results if not r.ok]
    if failed:
        md += ["", "## Failed clips (why)", ""]
        for r in failed:
            md.append(f"- **{r.clip}**: {failure_reason(r)}")
    md += ["", "## Detection per category (labelled events with at least one detection)", "",
           "| Category | Detected / labelled |", "|---|---|"]
    for cat, d in m["detection"].items():
        md.append(f"| {cat} | {d['detected']} / {d['labelled']} |")
    md += ["", "## How it is measured", "",
           "- *Expected/Got*: pattern/risk. Got = the highest risk any EchoTrace alert reached in the clip; "
           "no alert = NONE/GREEN.",
           "- *EchoTrace alerts*: risk step-ups of a sequence (GREEN->AMBER, AMBER->RED); later events do not re-alert.",
           "- *Baseline alerts*: one alert per detected IMPACT, DISTRESS, ALARM or GLASS event (what a plain audio "
           "classifier would raise). Both see the same detected events.",
           "- *L/C/R accuracy*: detected events of a labelled category whose zone matches the label.",
           f"- *Latency*: {lat['note']}" + (f" ({lat['n']} events)." if lat["n"] else "."),
           "", f"**Limitations:** {LIMITATIONS}", ""]
    return "\n".join(md)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="print only, don't write docs/metrics.*")
    args = ap.parse_args()

    # only clips with a label file are evaluated (e.g. demo_fallback.wav is a demo clip, not eval data)
    labels = sorted((EVAL_DIR / "labels").glob("*.json"))
    if not labels:
        print(f"no labels in {EVAL_DIR / 'labels'}")
        return 1
    labelled = {json.loads(p.read_text(encoding="utf-8"))["wav"] for p in labels}
    unlabelled = sorted(w.name for w in EVAL_DIR.glob("*.wav") if w.name not in labelled)
    if unlabelled:
        print(f"not evaluated (no label file): {', '.join(unlabelled)}")
    print(f"Loading CNN14 ({'cpu' if args.cpu else 'auto'}) ...", flush=True)
    tagger = default_tagger(args.cpu)
    results = []
    for p in labels:
        label = json.loads(p.read_text(encoding="utf-8"))
        if not (EVAL_DIR / label["wav"]).is_file():
            print(f"  skip {label['clip']}: {label['wav']} missing")
            continue
        print(f"  {label['clip']} ...", flush=True)
        results.append(run_clip(label, tagger))

    latency = latency_from_logs(sorted(config.RECORDINGS_DIR.glob("run_*_events.jsonl")))
    m = build_metrics(results, latency)
    print()
    print("\n".join(table(results)))
    print()
    fa, lc = m["false_alerts_detail"], m["lcr"]
    print(f"sequence accuracy  {fmt_pct(m['sequence_accuracy'])}  ({sum(r.ok for r in results)}/{len(results)})")
    print(f"false alerts       EchoTrace {fa['echotrace']} vs baseline {fa['baseline']} on {fa['clips']} non-incident "
          f"clips (reduction {fa['reduction_pct']}%); all clips: {m['totals']['echotrace_alerts']} vs "
          f"{m['totals']['baseline_alerts']}")
    print(f"L/C/R accuracy     {fmt_pct(lc['accuracy'])}  ({lc['correct']}/{lc['events']}, {lc['unknown']} UNKNOWN)")
    print("detection          " + ", ".join(f"{c} {d['detected']}/{d['labelled']}" for c, d in m["detection"].items()))
    lat = m["latency_detail"]
    print(f"latency            " + (f"mean {lat['mean']} ms, p95 {lat['p95']} ms ({lat['n']} live events)"
                                    if lat["mean"] is not None else lat["note"]))
    for r in results:
        if not r.ok:
            print(f"FAILED {r.clip}: {failure_reason(r)}")
    print(f"\n{headline(m)}\n{safer_line(m, results)}")
    if not args.no_write:
        config.DOCS_DIR.mkdir(exist_ok=True)
        (config.DOCS_DIR / "metrics.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
        (config.DOCS_DIR / "metrics.md").write_text(markdown(m, results), encoding="utf-8")
        print(f"wrote {config.DOCS_DIR / 'metrics.json'} and metrics.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
