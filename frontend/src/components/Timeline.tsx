import type { EventData, SequenceData } from "../types";
import { CATEGORIES, CATEGORY_COLOR, CATEGORY_NAME, pct } from "../labels";

const SPAN = 60; // seconds shown
const W = 1000;
const LABEL_W = 110;
const LANE_H = 22;

interface Props {
  events: EventData[];
  now: number;
  highlight: SequenceData | null;
}

export function Timeline({ events, now, highlight }: Props) {
  const H = LANE_H * CATEGORIES.length + 18;
  const t0 = now - SPAN;
  const x = (t: number) => LABEL_W + ((t - t0) / SPAN) * (W - LABEL_W - 10);
  const hi = new Set(highlight?.event_ids ?? []);
  const lane = (c: string) => Math.max(0, CATEGORIES.indexOf(c as (typeof CATEGORIES)[number]));
  const shown = events.filter((e) => e.t_end >= t0);
  const linked = shown.filter((e) => hi.has(e.id)).sort((a, b) => a.t_start - b.t_start);

  return (
    <div className="panel timeline-panel">
      <div className="panel-title">Timeline <span className="muted">· last {SPAN} s · bars show confidence</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} className="timeline" preserveAspectRatio="none">
        {CATEGORIES.map((c, i) => (
          <g key={c}>
            <rect x={0} y={i * LANE_H} width={W} height={LANE_H} className={i % 2 ? "lane odd" : "lane"} />
            <text x={8} y={i * LANE_H + 15} className="lane-label" fill={CATEGORY_COLOR[c]}>{CATEGORY_NAME[c]}</text>
          </g>
        ))}
        {[0, 15, 30, 45, 60].map((s) => (
          <g key={s}>
            <line x1={x(now - s)} x2={x(now - s)} y1={0} y2={H - 16} className="tick" />
            <text x={x(now - s)} y={H - 4} textAnchor="middle" className="tick-label">{s === 0 ? "now" : `-${s}s`}</text>
          </g>
        ))}
        {linked.slice(1).map((e, i) => {
          const a = linked[i];
          return (
            <line key={e.id} x1={x(a.t_end)} y1={lane(a.category) * LANE_H + LANE_H / 2}
              x2={x(e.t_start)} y2={lane(e.category) * LANE_H + LANE_H / 2} className="tl-link" />
          );
        })}
        {shown.map((e) => {
          const x0 = Math.max(LABEL_W, x(e.t_start));
          const w = Math.max(5, x(e.t_end) - x0);
          const y = lane(e.category) * LANE_H + 3;
          const on = hi.has(e.id);
          return (
            <g key={e.id}>
              <rect x={x0} y={y} width={w} height={LANE_H - 6} rx={3} fill={CATEGORY_COLOR[e.category] ?? "#ccc"}
                opacity={0.35 + 0.65 * e.confidence} className={on ? "bar on" : "bar"} />
              {w > 30 && (
                <text x={x0 + 4} y={y + 12} className="bar-label">{pct(e.confidence)}</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
