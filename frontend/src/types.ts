// Mirrors backend/echotrace/schemas.py (the source of truth) and the contract in CLAUDE.md.

export type Source = "LIVE" | "RECORDED" | "SIMULATED";
export type Zone = "LEFT" | "CENTRE" | "RIGHT" | "UNKNOWN";
export type Risk = "GREEN" | "AMBER" | "RED";

export interface Base {
  source: Source;
  t: number; // seconds since the source session started (stream time)
  wall: string; // ISO wall time
}

export interface TopLabel {
  label: string;
  p: number;
}

export interface FrameData extends Base {
  top: TopLabel[];
  categories: Record<string, number>;
  rms_db: [number, number] | number[];
}

export interface EventData extends Base {
  id: string; // e.g. "m2-e1": unique per source session
  t_start: number;
  t_end: number;
  category: string;
  label: string;
  confidence: number;
  zone: Zone;
  angle_deg: number | null; // + = RIGHT, - = LEFT
}

export interface SequenceData extends Base {
  id: string; // e.g. "m2-s1"; RE-SENT with the same id on every update (upsert)
  event_ids: string[];
  pattern: string; // template name, "ISOLATED_EVENT" or "NONE"
  risk: Risk;
  explanation: string[];
  summary: string;
  trajectory: Zone[];
}

export interface StatusData extends Base {
  risk: Risk;
  latency_ms: number; // 0 until the first event
  device: string;
  host_api: string;
  sample_rate: number;
  channels: number;
  localization: "ON" | "OFF";
  model_device: "cpu" | "cuda";
  dropped_blocks: number;
  // extras only present on GET /api/status
  error?: string | null;
  tagger?: string;
}

export type Message =
  | { type: "frame"; data: FrameData }
  | { type: "event"; data: EventData }
  | { type: "sequence"; data: SequenceData }
  | { type: "status"; data: StatusData };

export interface ModeResponse extends Base {
  device: string | null;
  file: string | null;
  scenario: string | null;
}

export interface Metrics {
  generated_at: string;
  clips: number;
  sequence_accuracy: number;
  false_alerts: { echotrace: number; baseline: number; reduction_pct: number };
  lcr_accuracy: number;
  latency_ms: { mean: number; p95: number };
  per_clip: { clip: string; expected: string; got: string; ok: boolean }[];
}

export type Connection = "connecting" | "open" | "closed";
