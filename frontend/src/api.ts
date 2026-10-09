import type { Metrics, ModeResponse, Source } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  let body: unknown = null;
  try {
    body = await r.json();
  } catch {
    /* non-JSON */
  }
  if (!r.ok) {
    const err = (body as { error?: string } | null)?.error ?? `${r.status} ${r.statusText}`;
    throw new Error(err);
  }
  return body as T;
}

export const setMode = (source: Source, opts: { file?: string; scenario?: string } = {}) =>
  call<ModeResponse>("/api/mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, ...opts }),
  });

export const getMode = () => call<ModeResponse>("/api/mode");

export const resetAll = () => call<{ ok: boolean }>("/api/reset", { method: "POST" });

export const getMetrics = () => call<Partial<Metrics>>("/api/metrics");
