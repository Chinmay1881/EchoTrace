import { useEffect, useState } from "react";
import { getMetrics } from "../api";
import type { Metrics } from "../types";

const fmtAcc = (v: number | undefined) =>
  v === undefined || v === null ? "-" : v <= 1 ? `${Math.round(v * 100)}%` : `${Math.round(v)}%`;

export function MetricsPanel() {
  const [m, setM] = useState<Partial<Metrics> | null>(null);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = () => getMetrics().then((x) => alive && setM(x)).catch(() => alive && setM(null));
    load();
    const id = window.setInterval(load, 30000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const has = m && Object.keys(m).length > 0 && m.false_alerts;
  return (
    <div className="panel metrics-panel">
      <button className="panel-title collapse" onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} Evaluation vs classification-only baseline
      </button>
      {open && (
        <div className="metrics">
          {!has && <div className="empty">No evaluation results yet (docs/metrics.json).</div>}
          {has && m && m.false_alerts && (
            <>
              <div className="metric big">
                False alerts: <b>EchoTrace {m.false_alerts.echotrace}</b> vs baseline {m.false_alerts.baseline}
                <span className="good"> (−{Math.round(m.false_alerts.reduction_pct)}%)</span>
              </div>
              <div className="metric-row">
                <span>Sequence accuracy <b>{fmtAcc(m.sequence_accuracy)}</b></span>
                <span>L/C/R accuracy <b>{fmtAcc(m.lcr_accuracy)}</b></span>
                {m.latency_ms && <span>Latency <b>{Math.round(m.latency_ms.mean)}</b> ms (p95 {Math.round(m.latency_ms.p95)})</span>}
                <span className="muted">{m.clips} clips</span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
