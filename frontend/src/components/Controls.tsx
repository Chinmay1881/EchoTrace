import { useState } from "react";
import { resetAll, setMode } from "../api";
import type { Source } from "../types";

interface Props {
  current: Source | undefined;
  onCleared: () => void;
}

const BUTTONS: { source: Source; label: string }[] = [
  { source: "LIVE", label: "Live" },
  { source: "RECORDED", label: "Recorded" },
  { source: "SIMULATED", label: "Simulation" },
];

export function Controls({ current, onCleared }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState("demo_backup.wav");

  const switchTo = async (source: Source) => {
    setBusy(source);
    setError(null);
    try {
      await setMode(source, source === "RECORDED" && file.trim() ? { file: file.trim() } : {});
      onCleared();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const reset = async () => {
    setBusy("reset");
    setError(null);
    try {
      await resetAll();
      onCleared();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="controls">
      <div className="seg">
        {BUTTONS.map((b) => (
          <button
            key={b.source}
            className={`seg-btn ${current === b.source ? "active" : ""} sb-${b.source}`}
            disabled={busy !== null}
            onClick={() => switchTo(b.source)}
            title={b.source === "RECORDED" ? "Replay a clip (default: newest recordings/demo*.wav)" : undefined}
          >
            {busy === b.source ? "…" : b.label}
          </button>
        ))}
        <button className="seg-btn reset" disabled={busy !== null} onClick={reset}>
          {busy === "reset" ? "…" : "Reset"}
        </button>
      </div>
      <input
        className="file-input"
        value={file}
        onChange={(e) => setFile(e.target.value)}
        placeholder="clip for Recorded (optional, e.g. recordings\demo.wav)"
        spellCheck={false}
      />
      {error && (
        <div className="ctl-error" role="alert" onClick={() => setError(null)} title="click to dismiss">
          {error}
        </div>
      )}
    </div>
  );
}
