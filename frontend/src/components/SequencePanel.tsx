import type { EventData, SequenceData } from "../types";
import { CATEGORY_COLOR, CATEGORY_NAME, RISK_COLOR, clock, patternName, pct } from "../labels";

interface Props {
  sequences: SequenceData[]; // newest first
  events: EventData[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}

export function SequencePanel({ sequences, events, selected, onSelect }: Props) {
  const seq = selected ? sequences.find((s) => s.id === selected) ?? null : null;
  if (seq) return <DetailPanel seq={seq} events={events} onBack={() => onSelect(null)} />;
  const alerts = sequences.filter((s) => s.risk !== "GREEN").length;
  return (
    <div className="panel seq-panel">
      <div className="panel-title">
        Sequences <span className="muted">· {sequences.length} total · {alerts} alerting · click for why</span>
      </div>
      <div className="seq-list">
        {sequences.length === 0 && <div className="empty">No events yet. Listening…</div>}
        {sequences.map((s) => (
          <button key={s.id} className={`seq-item seq-${s.risk}`} onClick={() => onSelect(s.id)}>
            <span className="seq-bar" style={{ background: RISK_COLOR[s.risk] }} />
            <span className="seq-body">
              <span className="seq-head">
                <b style={{ color: RISK_COLOR[s.risk] }}>{s.risk}</b>
                <span className="seq-pattern">{patternName(s.pattern)}</span>
                <span className="muted">{s.event_ids.length} ev · {clock(s.wall)}</span>
              </span>
              <span className="seq-summary">{s.summary}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function DetailPanel({ seq, events, onBack }: { seq: SequenceData; events: EventData[]; onBack: () => void }) {
  const byId = new Map(events.map((e) => [e.id, e]));
  const evs = seq.event_ids.map((id) => byId.get(id)).filter((e): e is EventData => !!e);
  return (
    <div className="panel seq-panel detail">
      <div className="panel-title">
        <button className="back" onClick={onBack}>← all sequences</button>
        <span className="muted">{seq.id}</span>
      </div>
      <div className="detail-scroll">
        <div className="detail-risk" style={{ borderColor: RISK_COLOR[seq.risk], color: RISK_COLOR[seq.risk] }}>
          {seq.risk} · {patternName(seq.pattern)}
        </div>
        {seq.trajectory.length > 0 && (
          <div className="detail-traj">possible acoustic trajectory: <b>{seq.trajectory.join(" → ")}</b></div>
        )}
        <p className="detail-summary">{seq.summary}</p>
        <div className="detail-h">Why</div>
        <ul className="why">
          {seq.explanation.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
        <div className="detail-h">Contributing events ({seq.event_ids.length})</div>
        <table className="ev-table">
          <thead>
            <tr><th>time</th><th>category</th><th>label</th><th>conf.</th><th>zone</th></tr>
          </thead>
          <tbody>
            {evs.map((e) => (
              <tr key={e.id}>
                <td>{clock(e.wall)} <span className="muted">{e.t_start.toFixed(1)}s</span></td>
                <td style={{ color: CATEGORY_COLOR[e.category] }}>{CATEGORY_NAME[e.category] ?? e.category}</td>
                <td>{e.label}</td>
                <td>{pct(e.confidence)}</td>
                <td className={e.zone === "UNKNOWN" || e.zone_confidence === "low" ? "muted" : ""}>
                  {e.zone}
                  {e.zone_confidence === "low"
                    ? " (low confidence)"
                    : e.angle_deg !== null && e.zone !== "UNKNOWN"
                      ? ` (${e.angle_deg > 0 ? "+" : ""}${Math.round(e.angle_deg)}°)`
                      : ""}
                </td>
              </tr>
            ))}
            {evs.length < seq.event_ids.length && (
              <tr><td colSpan={5} className="muted">{seq.event_ids.length - evs.length} older event(s) no longer in view</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
