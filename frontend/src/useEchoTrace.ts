import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { Connection, EventData, FrameData, Message, SequenceData, StatusData } from "./types";

const MAX_EVENTS = 200;

export interface State {
  session: string | null; // id prefix of the current source session ("m2-"); a change clears the state
  events: EventData[]; // time-ordered, deduped by id, capped
  sequences: Record<string, SequenceData>; // upserted by id
  frame: FrameData | null;
  status: StatusData | null;
  now: number; // latest stream time seen (frame/status t)
}

const EMPTY: State = { session: null, events: [], sequences: {}, frame: null, status: null, now: 0 };

type Action = { kind: "msg"; msg: Message } | { kind: "clear" };

function sessionOf(id: string): string {
  const i = id.lastIndexOf("-");
  return i >= 0 ? id.slice(0, i + 1) : "";
}

function reducer(state: State, action: Action): State {
  if (action.kind === "clear") return { ...EMPTY, status: state.status, frame: state.frame, now: state.now };
  const { msg } = action;
  let s = state;
  // a new source session (mode switch) or a different source label: start from a clean slate
  if (s.status && msg.data.source !== s.status.source) s = { ...EMPTY };
  if (msg.type === "event" || msg.type === "sequence") {
    const sess = sessionOf(msg.data.id);
    if (s.session !== null && sess !== s.session) s = { ...EMPTY, status: s.status, frame: s.frame, now: s.now };
    if (s.session !== sess) s = { ...s, session: sess };
  }
  // stream time only moves forward, except when a new session restarts it from 0
  const now = msg.data.t < s.now - 5 ? msg.data.t : Math.max(s.now, msg.data.t);
  switch (msg.type) {
    case "frame":
      return { ...s, frame: msg.data, now };
    case "status":
      return { ...s, status: msg.data, now };
    case "event": {
      const others = s.events.filter((e) => e.id !== msg.data.id);
      const events = [...others, msg.data].sort((a, b) => a.t_start - b.t_start).slice(-MAX_EVENTS);
      return { ...s, events, now };
    }
    case "sequence":
      return { ...s, sequences: { ...s.sequences, [msg.data.id]: msg.data }, now };
  }
  return s;
}

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

/** WebSocket connection to the EchoTrace backend with auto-reconnect and the dashboard state. */
export function useEchoTrace() {
  const [state, dispatch] = useReducer(reducer, EMPTY);
  const [connection, setConnection] = useState<Connection>("connecting");
  const retry = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: number | undefined;
    let stopped = false;

    const connect = () => {
      setConnection("connecting");
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        retry.current = 0;
        setConnection("open");
      };
      ws.onmessage = (ev) => {
        try {
          dispatch({ kind: "msg", msg: JSON.parse(ev.data) as Message });
        } catch {
          /* ignore malformed */
        }
      };
      ws.onclose = () => {
        setConnection("closed");
        if (stopped) return;
        const delay = Math.min(5000, 500 * 2 ** retry.current++);
        timer = window.setTimeout(connect, delay);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      ws?.close();
    };
  }, []);

  const clear = useCallback(() => dispatch({ kind: "clear" }), []);
  return { state, connection, clear };
}
