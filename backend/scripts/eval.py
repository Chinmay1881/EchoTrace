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
               "zone_confidence": e.zone_confidence if e.zone != "UNKNOWN" else None,
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
        f"**Sensitivity profile: `{m.get('sensitivity', config.SENSITIVITY)}`** (detection thresholds; see the "
        "disclosure section below). Tagger gain "
        f"+{m.get('gain_db', config.TAGGER_GAIN_DB):.0f} dB.",
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
        f"| ...of which low-confidence zones right / wrong (shown with \"?\") | {lc.get('low_correct', 0)} / "
        f"{lc.get('low_wrong', 0)} | |",
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


def profile_info(mode: str) -> dict:
    return {"sensitivity": mode, "gain_db": config.tagger_gain_db(mode),
            "thresholds": {c: list(config.thresholds(c, mode)) for c in config.CATEGORIES}}


DIRECTION = {True: "v2: 40-60% vote -> low-confidence zone", False: "v1: UNKNOWN below 60% vote"}


def evaluate(mode: str, labels: list[dict], tagger, low_tier: bool = True) -> tuple[list[ClipResult], dict]:
    """All labelled clips under one sensitivity profile (thresholds + gain) and direction logic."""
    config.set_sensitivity(mode)
    tagger.gain_db = config.tagger_gain_db()
    saved_low = config.LOC_LOW_VOTE
    config.LOC_LOW_VOTE = saved_low if low_tier else None
    try:
        results = []
        for label in labels:
            print(f"  [{mode}, direction {'v2' if low_tier else 'v1'}] {label['clip']} ...", flush=True)
            results.append(run_clip(label, tagger))
    finally:
        config.LOC_LOW_VOTE = saved_low
    m = build_metrics(results, {"mean": None, "p95": None, "n": 0, "sources": [], "note": ""})
    summary = {**profile_info(mode), "direction": DIRECTION[low_tier], "sequence_accuracy": m["sequence_accuracy"],
               "clips_ok": sum(r.ok for r in results), "clips": len(results), "lcr_accuracy": m["lcr_accuracy"],
               "lcr": m["lcr"], "detection": m["detection"], "false_alerts": m["false_alerts_detail"],
               "totals": m["totals"], "per_clip": m["per_clip"]}
    return results, summary


def comparison_md(main_key: str, summaries: dict[str, dict]) -> list[str]:
    keys = [main_key] + [k for k in summaries if k != main_key]
    S = summaries

    def thr(s):
        t = s["thresholds"]
        imp = t["IMPACT"]
        rest = sorted({tuple(v) for c, v in t.items() if c != "IMPACT"})
        return f"IMPACT {imp[0]:.2f}/{imp[1]:.2f}, others " + ", ".join(f"{a:.2f}/{b:.2f}" for a, b in rest)

    def row(name, fn):
        return f"| {name} | " + " | ".join(fn(S[k]) for k in keys) + " |"

    md = ["", "## Changes after the first evaluation (disclosure)", "",
          "Two changes were made **after** seeing earlier results on these same 10 clips, so they are no longer a "
          "fully independent test. Every version is re-run from code below.", "",
          "1. **Sensitivity** (`normal` -> `high`): detection thresholds were lowered because real sounds were often "
          "recognised below threshold in live use. Checked first on speech and silence only: 0 events on the "
          "background and chatter clips and in the BACKGROUND/CHATTER steps of three logged guided runs (highest "
          "speech/silence category score 0.03).",
          "2. **Direction logic** (v1 -> v2): a best-guess zone with 40-60% frame agreement is now reported as "
          "*low confidence* instead of UNKNOWN (shown faded with a \"?\" on the dashboard). Low-confidence zones "
          "count as normal predictions in L/C/R accuracy and are also reported separately. An inter-channel level "
          "difference (ILD) cue, a 300-3000 Hz GCC band and SNR-weighted voting over more frames were also measured "
          "on these clips and **rejected** (no gain, or more confident wrong zones on table impacts).", "",
          "| | " + " | ".join(f"{k}{' **(demo)**' if k == main_key else ''}" for k in keys) + " |",
          "|---|" + "---|" * len(keys),
          row("on/off thresholds", thr),
          row("direction logic", lambda s: s["direction"]),
          row("Sequence accuracy", lambda s: f"{fmt_pct(s['sequence_accuracy'])} ({s['clips_ok']}/{s['clips']})"),
          row("L/C/R accuracy", lambda s: f"{fmt_pct(s['lcr_accuracy'])} ({s['lcr']['correct']}/{s['lcr']['events']})"),
          row("UNKNOWN zones", lambda s: str(s["lcr"]["unknown"])),
          row("high-confidence zones right / wrong", lambda s: f"{s['lcr']['high_correct']} / {s['lcr']['high_wrong']}"),
          row("low-confidence zones right / wrong", lambda s: f"{s['lcr']['low_correct']} / {s['lcr']['low_wrong']}")]
    for c in S[main_key]["detection"]:
        md.append(row(f"Detection {c}", lambda s, c=c: f"{s['detection'].get(c, {}).get('detected', 0)}/"
                                                     f"{s['detection'].get(c, {}).get('labelled', 0)}"))
    md += [row("Alerts on no-incident clips (EchoTrace vs baseline)",
               lambda s: f"{s['false_alerts']['echotrace']} vs {s['false_alerts']['baseline']}"),
           row("Alerts on all clips (EchoTrace vs baseline)",
               lambda s: f"{s['totals']['echotrace_alerts']} vs {s['totals']['baseline_alerts']}"),
           row("Clips that fail", lambda s: ", ".join(p["clip"] for p in s["per_clip"] if not p["ok"]) or "none")]
    return md

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--no-write", action="store_true", help="print only, don't write docs/metrics.*")
    ap.add_argument("--sensitivity", choices=list(config.SENSITIVITY_PROFILES), default=config.SENSITIVITY,
                    help="profile whose results go into docs/metrics.* (default: %(default)s)")
    ap.add_argument("--no-compare", action="store_true", help="don't also evaluate the other profile(s)")
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
    label_docs = []
    for p in labels:
        label = json.loads(p.read_text(encoding="utf-8"))
        if not (EVAL_DIR / label["wav"]).is_file():
            print(f"  skip {label['clip']}: {label['wav']} missing")
            continue
        label_docs.append(label)

    main_key = f"{args.sensitivity}, direction v2"
    summaries: dict[str, dict] = {}
    if not args.no_compare:          # the history: first eval, after the sensitivity change, now
        summaries["normal, direction v1 (first eval)"] = evaluate("normal", label_docs, tagger, low_tier=False)[1]
        summaries["high, direction v1"] = evaluate("high", label_docs, tagger, low_tier=False)[1]
    results, summaries[main_key] = evaluate(args.sensitivity, label_docs, tagger)   # last: stays active

    latency = latency_from_logs(sorted(config.RECORDINGS_DIR.glob("run_*_events.jsonl")))
    m = build_metrics(results, latency)
    m.update(profile_info(args.sensitivity))
    if len(summaries) > 1:
        m["comparison"] = {k: {kk: vv for kk, vv in v.items() if kk != "per_clip"} for k, v in summaries.items()}
        m["comparison_note"] = ("thresholds (normal -> high) and direction logic (v1 -> v2) were changed after earlier evaluations; all versions shown")
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
    if len(summaries) > 1:
        print("\n".join(comparison_md(main_key, summaries)))
    if not args.no_write:
        config.DOCS_DIR.mkdir(exist_ok=True)
        (config.DOCS_DIR / "metrics.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
        md = markdown(m, results)
        if len(summaries) > 1:
            md = md.replace("\n## Per clip", "\n".join(comparison_md(main_key, summaries)) + "\n\n## Per clip", 1)
        (config.DOCS_DIR / "metrics.md").write_text(md, encoding="utf-8")
        print(f"wrote {config.DOCS_DIR / 'metrics.json'} and metrics.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
