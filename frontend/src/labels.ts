import type { Risk, Source, Zone } from "./types";

export const CATEGORIES = ["FOOTSTEPS", "IMPACT", "DISTRESS", "ALARM", "GLASS", "DOOR"] as const;

export const CATEGORY_COLOR: Record<string, string> = {
  FOOTSTEPS: "#4fc3f7",
  IMPACT: "#ff8a65",
  DISTRESS: "#f06292",
  ALARM: "#ffee58",
  GLASS: "#b388ff",
  DOOR: "#a1c4a5",
};

// Event (on) thresholds per sensitivity profile - mirror backend/echotrace/config.py SENSITIVITY_PROFILES.
export const CATEGORY_THRESHOLDS: Record<"normal" | "high", Record<string, number>> = {
  normal: { FOOTSTEPS: 0.3, IMPACT: 0.2, DISTRESS: 0.3, ALARM: 0.3, GLASS: 0.3, DOOR: 0.3 },
  high: { FOOTSTEPS: 0.2, IMPACT: 0.12, DISTRESS: 0.2, ALARM: 0.2, GLASS: 0.2, DOOR: 0.2 },
};

export const CATEGORY_NAME: Record<string, string> = {
  FOOTSTEPS: "Footsteps",
  IMPACT: "Impact",
  DISTRESS: "Distress",
  ALARM: "Alarm",
  GLASS: "Glass",
  DOOR: "Door",
};

export const RISK_COLOR: Record<Risk, string> = { GREEN: "#22c55e", AMBER: "#ffb000", RED: "#ff3344" };

// Cautious wording: never "confirmed emergency".
export const RISK_TEXT: Record<Risk, string> = {
  GREEN: "No correlated pattern",
  AMBER: "Possible pattern - monitor",
  RED: "Potentially significant sequence - verify",
};

export const PATTERN_NAME: Record<string, string> = {
  MOVEMENT_IMPACT_DISTRESS: "Movement → impact → distress",
  BREAKIN_ALARM: "Glass → impact → alarm (possible break-in)",
  IMPACT_DISTRESS: "Impact → distress",
  ALARM_EVACUATION: "Alarm → movement (possible evacuation)",
  GLASS_INTRUSION: "Glass → movement",
  GLASS_IMPACT: "Glass → impact",
  ISOLATED_EVENT: "Isolated event (logged, no alert)",
  NONE: "No known pattern (logged, no alert)",
};

export const patternName = (p: string) => PATTERN_NAME[p] ?? p.replace(/_/g, " ").toLowerCase();

export const SOURCE_TEXT: Record<Source, string> = {
  LIVE: "LIVE MIC",
  RECORDED: "RECORDED CLIP",
  SIMULATED: "SIMULATED DATA",
};

export const ZONE_CENTRE_ANGLE: Record<Zone, number | null> = { LEFT: -55, CENTRE: 0, RIGHT: 55, UNKNOWN: null };

export const pct = (p: number) => `${Math.round(p * 100)}%`;

export const clock = (wall: string) => (wall.length >= 19 ? wall.slice(11, 19) : wall);
