import type { Connection, SequenceData, StatusData } from "../types";
import { RISK_TEXT, SOURCE_TEXT, patternName } from "../labels";

interface Props {
  status: StatusData | null;
  connection: Connection;
  headline: SequenceData | null; // the sequence driving the current risk
  children?: React.ReactNode; // controls
}

export function StatusBanner({ status, connection, headline, children }: Props) {
  const risk = status?.risk ?? "GREEN";
  const source = status?.source;
  return (
    <header className={`banner risk-${risk}`}>
      <div className="risk-block">
        <div className="risk-word">{risk}</div>
        <div className="risk-text">
          <div className="risk-caption">{RISK_TEXT[risk]}</div>
          <div className="risk-sub">
            {risk !== "GREEN" && headline ? patternName(headline.pattern) : "Monitoring - every alert shows why"}
          </div>
        </div>
      </div>

      <div className="banner-mid">
        {source ? (
          <div className={`source-badge src-${source}`} title="Where the data comes from">
            {SOURCE_TEXT[source]}
          </div>
        ) : (
          <div className="source-badge src-NONE">NO DATA</div>
        )}
        <div className="chips">
          <span className={`chip conn-${connection}`}>
            <span className="dot" /> {connection === "open" ? "connected" : connection}
          </span>
          <span className="chip" title="capture of the triggering audio -> sent to this screen">
            latency {status && status.latency_ms > 0 ? `${Math.round(status.latency_ms)} ms` : "-"}
          </span>
          <span className={`chip ${status?.localization === "ON" ? "ok" : "warn"}`}>
            localization {status?.localization ?? "-"}
          </span>
          <span className="chip">{status ? (status.model_device === "cuda" ? "GPU" : "CPU") : "-"}</span>
          {status?.sensitivity && (
            <span className={`chip ${status.sensitivity === "high" ? "sens-high" : ""}`}
              title="detection threshold profile (see docs/metrics.md for both results)">
              sensitivity {status.sensitivity.toUpperCase()}
            </span>
          )}
          {status && status.dropped_blocks > 0 && <span className="chip warn">dropped {status.dropped_blocks}</span>}
        </div>
        <div className="device" title={status?.host_api}>
          {status ? `${status.device} · ${status.host_api}` : "waiting for backend..."}
        </div>
      </div>

      <div className="banner-controls">{children}</div>
    </header>
  );
}
