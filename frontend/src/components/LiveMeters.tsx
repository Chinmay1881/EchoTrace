import type { FrameData } from "../types";

const LO = -70;
const HI = -10;
const frac = (db: number) => Math.max(0, Math.min(1, (db - LO) / (HI - LO)));

export function LiveMeters({ frame }: { frame: FrameData | null }) {
  const [l, r] = frame?.rms_db ?? [LO, LO];
  return (
    <div className="panel meters-panel">
      <div className="panel-title">Live input <span className="muted">· level & what CNN14 hears</span></div>
      <div className="meters">
        {[["L", l], ["R", r]].map(([name, db]) => (
          <div key={name as string} className="meter-row">
            <span className="meter-name">{name}</span>
            {/* gradient spans the full scale (-70..-10 dBFS); the unfilled part is covered */}
            <div className="meter"><div className="meter-cover" style={{ width: `${(1 - frac(db as number)) * 100}%` }} /></div>
            <span className="meter-db">{Number(db).toFixed(0)} dB</span>
          </div>
        ))}
      </div>
      <div className="top5">
        {(frame?.top ?? []).slice(0, 5).map((t) => (
          <div key={t.label} className="top-row">
            <span className="top-label" title={t.label}>{t.label}</span>
            <div className="top-bar"><div style={{ width: `${Math.round(t.p * 100)}%` }} /></div>
            <span className="top-p">{Math.round(t.p * 100)}</span>
          </div>
        ))}
        {!frame && <div className="empty">no audio frames yet</div>}
      </div>
    </div>
  );
}
