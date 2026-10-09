import { useEffect, useRef, useState } from "react";
import type { FrameData } from "../types";
import { CATEGORIES, CATEGORY_COLOR, CATEGORY_NAME, CATEGORY_THRESHOLDS } from "../labels";

const LO = -70;
const HI = -10;
const frac = (db: number) => Math.max(0, Math.min(1, (db - LO) / (HI - LO)));
const PEAK_HOLD_MS = 4000;

/** Category scores vs their event thresholds, with a short peak-hold so brief sounds stay readable. */
function useHeldPeaks(frame: FrameData | null) {
  const [peaks, setPeaks] = useState<Record<string, number>>({});
  const at = useRef<Record<string, number>>({});
  useEffect(() => {
    if (!frame) return;
    const now = Date.now();
    setPeaks((prev) => {
      const next: Record<string, number> = {};
      for (const c of CATEGORIES) {
        const p = frame.categories[c] ?? 0;
        const held = prev[c] ?? 0;
        if (p >= held || now - (at.current[c] ?? 0) > PEAK_HOLD_MS) {
          next[c] = p;
          at.current[c] = now;
        } else next[c] = held;
      }
      return next;
    });
  }, [frame]);
  return peaks;
}

export function LiveMeters({ frame, sensitivity }: { frame: FrameData | null; sensitivity?: "normal" | "high" }) {
  const [l, r] = frame?.rms_db ?? [LO, LO];
  const peaks = useHeldPeaks(frame);
  return (
    <div className="panel meters-panel">
      <div className="panel-title">Live input <span className="muted">· level · category scores vs event threshold</span></div>
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
      <div className="cats" title="Current score (bar), 4 s peak (tick), event threshold (white line)">
        {CATEGORIES.map((c) => {
          const p = frame?.categories[c] ?? 0;
          const peak = peaks[c] ?? 0;
          const thr = CATEGORY_THRESHOLDS[sensitivity ?? "normal"][c];
          const over = peak >= thr;
          return (
            <div key={c} className={`cat-row ${over ? "over" : ""}`}>
              <span className="cat-name" style={{ color: CATEGORY_COLOR[c] }}>{CATEGORY_NAME[c]}</span>
              <div className="cat-bar">
                <div className="cat-fill" style={{ width: `${p * 100}%`, background: CATEGORY_COLOR[c] }} />
                <div className="cat-peak" style={{ left: `${peak * 100}%` }} />
                <div className="cat-thr" style={{ left: `${thr * 100}%` }} />
              </div>
              <span className="cat-p">{Math.round(peak * 100)}</span>
            </div>
          );
        })}
      </div>
      <div className="top5">
        {(frame?.top ?? []).slice(0, 2).map((t) => (
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
