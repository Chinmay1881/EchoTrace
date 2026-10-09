import { useMemo, useState } from "react";
import { useEchoTrace } from "./useEchoTrace";
import { StatusBanner } from "./components/StatusBanner";
import { Controls } from "./components/Controls";
import { AcousticMap } from "./components/AcousticMap";
import { SequencePanel } from "./components/SequencePanel";
import { Timeline } from "./components/Timeline";
import { LiveMeters } from "./components/LiveMeters";
import { MetricsPanel } from "./components/MetricsPanel";
import type { SequenceData } from "./types";

const ACTIVE_WINDOW_S = 30;

export default function App() {
  const { state, connection, clear } = useEchoTrace();
  const [selected, setSelected] = useState<string | null>(null);

  const sequences = useMemo(
    () => Object.values(state.sequences).sort((a, b) => b.t - a.t),
    [state.sequences],
  );

  // the sequence whose trajectory is drawn: the clicked one, else the latest alerting one, else the latest linked one
  const active: SequenceData | null = useMemo(() => {
    if (selected && state.sequences[selected]) return state.sequences[selected];
    const recent = sequences.filter((s) => state.now - s.t <= ACTIVE_WINDOW_S);
    return recent.find((s) => s.risk !== "GREEN") ?? recent.find((s) => s.event_ids.length > 1) ?? null;
  }, [selected, state.sequences, sequences, state.now]);

  const headline = sequences.find((s) => s.risk !== "GREEN" && state.now - s.t <= ACTIVE_WINDOW_S) ?? null;

  const onCleared = () => {
    setSelected(null);
    clear();
  };

  return (
    <div className="app">
      <StatusBanner status={state.status} connection={connection} headline={headline}>
        <Controls current={state.status?.source} onCleared={onCleared} />
      </StatusBanner>

      <main className="main">
        <AcousticMap events={state.events} active={active} now={state.now} source={state.status?.source} />
        <div className="side">
          <SequencePanel sequences={sequences} events={state.events} selected={selected} onSelect={setSelected} />
          <MetricsPanel />
        </div>
      </main>

      <section className="bottom">
        <Timeline events={state.events} now={state.now} highlight={active} />
        <LiveMeters frame={state.frame} sensitivity={state.status?.sensitivity} />
      </section>

      <footer className="footer">
        EchoTrace - supplements responders, never replaces them. Possible acoustic trajectory only; no identity
        tracking. Local inference, open weights (PANNs CNN14).
      </footer>
    </div>
  );
}
