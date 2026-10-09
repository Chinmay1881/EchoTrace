import type { EventData, SequenceData, Source } from "../types";
import { CATEGORY_COLOR, CATEGORY_NAME, ZONE_CENTRE_ANGLE, pct } from "../labels";

const W = 1000;
const H = 560;
const CX = 500;
const CY = 500;
const R = 445;
const FADE_S = 15;
const CENTRE_HALF = 20;

function polar(angleDeg: number, r: number): [number, number] {
  const a = (angleDeg * Math.PI) / 180;
  return [CX + r * Math.sin(a), CY - r * Math.cos(a)];
}

function wedge(a0: number, a1: number, r: number): string {
  const [x0, y0] = polar(a0, r);
  const [x1, y1] = polar(a1, r);
  return `M ${CX} ${CY} L ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1} Z`;
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

interface Placed {
  ev: EventData;
  x: number;
  y: number;
  unknown: boolean;
}

function place(events: EventData[]): Placed[] {
  let k = 0;
  return events.map((ev) => {
    const base = ev.angle_deg ?? ZONE_CENTRE_ANGLE[ev.zone];
    if (base === null || ev.zone === "UNKNOWN") {
      const x = W - 60 - (k++ % 12) * 44; // the greyed "direction unknown" tray, bottom right
      return { ev, x, y: H - 22, unknown: true };
    }
    const jitter = ev.angle_deg === null ? ((hash(ev.id) % 100) / 100) * 22 - 11 : 0;
    const angle = Math.max(-86, Math.min(86, base + jitter));
    const r = 150 + 280 * Math.max(0, Math.min(1, ev.confidence)) + ((hash(ev.id) >> 3) % 30);
    const [x, y] = polar(angle, r);
    return { ev, x, y, unknown: false };
  });
}

/** Consecutive same-category runs -> centroid points (like the backend's grouping): the possible acoustic
 *  trajectory. Footsteps keep one point per zone so their movement (e.g. LEFT -> CENTRE) stays visible. */
function trajectoryPoints(placed: Placed[]): { x: number; y: number; cat: string }[] {
  const pts: { x: number; y: number; cat: string; zone: string; n: number }[] = [];
  for (const p of placed) {
    if (p.unknown) continue;
    const last = pts[pts.length - 1];
    const same = last && last.cat === p.ev.category && (p.ev.category !== "FOOTSTEPS" || last.zone === p.ev.zone);
    if (last && same) {
      last.x = (last.x * last.n + p.x) / (last.n + 1);
      last.y = (last.y * last.n + p.y) / (last.n + 1);
      last.n += 1;
    } else pts.push({ x: p.x, y: p.y, cat: p.ev.category, zone: p.ev.zone, n: 1 });
  }
  return pts;
}

interface Props {
  events: EventData[];
  active: SequenceData | null;
  now: number;
  source: Source | undefined;
}

export function AcousticMap({ events, active, now, source }: Props) {
  const activeIds = new Set(active?.event_ids ?? []);
  const visible = events.filter((e) => now - e.t_end <= FADE_S || activeIds.has(e.id));
  const placed = place(visible);
  const seqPlaced = placed.filter((p) => activeIds.has(p.ev.id)).sort((a, b) => a.ev.t_start - b.ev.t_start);
  const traj = active && active.event_ids.length > 1 ? trajectoryPoints(seqPlaced) : [];
  const trajColor = active?.risk === "RED" ? "#ff3344" : active?.risk === "AMBER" ? "#ffb000" : "#9fb3c8";
  // label only the newest dot per category + zone, so repeats (e.g. 3 glass events on the LEFT) don't stack text
  const labelled = new Set<string>();
  const seen = new Set<string>();
  for (const p of [...placed].reverse()) {
    const k = `${p.ev.category}|${p.ev.zone}`;
    if (!seen.has(k)) {
      seen.add(k);
      labelled.add(p.ev.id);
    }
  }

  return (
    <div className="panel map-panel">
      <div className="panel-title">
        Acoustic map <span className="muted">· top-down, approximate zones · mic pair at the bottom · 2 mics:
        front/back can't be distinguished; sounds behind the laptop may read as low-confidence or unknown</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="map" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={trajColor} />
          </marker>
          <pattern id="stripes" width="24" height="24" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="12" height="24" fill="rgba(255,140,0,0.05)" />
          </pattern>
        </defs>

        {source && source !== "LIVE" && <rect x="0" y="0" width={W} height={H} fill="url(#stripes)" />}
        {source && source !== "LIVE" && (
          <text x={CX} y={300} className="watermark" textAnchor="middle">
            {source}
          </text>
        )}

        <path d={wedge(-90, -CENTRE_HALF, R)} className="zone zone-l" />
        <path d={wedge(-CENTRE_HALF, CENTRE_HALF, R)} className="zone zone-c" />
        <path d={wedge(CENTRE_HALF, 90, R)} className="zone zone-r" />
        {[150, 300, 455].map((r) => (
          <path key={r} d={`M ${CX - r} ${CY} A ${r} ${r} 0 0 1 ${CX + r} ${CY}`} className="ring" />
        ))}
        <text {...xy(polar(-55, 400))} className="zone-label" textAnchor="middle">LEFT</text>
        <text {...xy(polar(0, 420))} className="zone-label" textAnchor="middle">CENTRE</text>
        <text {...xy(polar(55, 400))} className="zone-label" textAnchor="middle">RIGHT</text>

        <g className="mic">
          <rect x={CX - 70} y={CY + 6} width="140" height="22" rx="5" />
          <circle cx={CX - 26} cy={CY + 17} r="6" />
          <circle cx={CX + 26} cy={CY + 17} r="6" />
          <text x={CX} y={CY + 50} textAnchor="middle" className="mic-label">laptop mic pair (6.5 cm apart)</text>
        </g>
        <text x={W - 20} y={H - 46} textAnchor="end" className="tray-label">direction unknown</text>

        {traj.length > 1 && (
          <g className="trajectory">
            {traj.slice(1).map((p, i) => (
              <line key={i} x1={traj[i].x} y1={traj[i].y} x2={p.x} y2={p.y} stroke={trajColor}
                markerEnd="url(#arrow)" />
            ))}
          </g>
        )}
        {traj.length > 1 && (
          <g className="traj-key">
            <line x1={24} y1={30} x2={84} y2={30} stroke={trajColor} />
            <text x={94} y={36} className="traj-label" fill={trajColor}>
              possible acoustic trajectory · {active?.trajectory.join(" → ")}
            </text>
          </g>
        )}

        {placed.map(({ ev, x, y, unknown }) => {
          const age = now - ev.t_end;
          const inSeq = activeIds.has(ev.id);
          const low = ev.zone_confidence === "low";
          const opacity = Math.max(inSeq ? 0.45 : 0, 1 - Math.max(0, age) / FADE_S) * (low ? 0.6 : 1);
          const color = unknown ? "#6b7785" : CATEGORY_COLOR[ev.category] ?? "#ccc";
          const r = 10 + 14 * ev.confidence;
          return (
            <g key={ev.id} opacity={opacity} className={unknown ? "dot unknown" : "dot"}>
              <circle cx={x} cy={y} r={r} className="pulse" stroke={color} />
              <circle cx={x} cy={y} r={r} fill={color} stroke={inSeq ? "#fff" : low ? color : "none"} strokeWidth={3}
                strokeDasharray={low && !inSeq ? "5 4" : undefined} fillOpacity={low ? 0.55 : 1} />
              {!unknown && labelled.has(ev.id) && (
                <text x={x} y={y - r - 8} textAnchor="middle" className="dot-label" fill={color}>
                  {CATEGORY_NAME[ev.category] ?? ev.category} {pct(ev.confidence)}{low ? " ?" : ""}
                </text>
              )}
              {low && (
                <title>{`${ev.zone} (low-confidence direction)`}</title>
              )}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {Object.entries(CATEGORY_NAME).map(([k, v]) => (
          <span key={k}><i style={{ background: CATEGORY_COLOR[k] }} />{v}</span>
        ))}
      </div>
    </div>
  );
}

function xy([x, y]: [number, number]) {
  return { x, y };
}
