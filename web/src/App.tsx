import { useCallback, useEffect, useState } from "react";
import { fetchDemo, fetchStatus, recommend, type PipelineResult } from "./api";
import { applyAccent } from "./theme";
import { Dropzone } from "./components/Dropzone";
import { Recommendation } from "./components/Recommendation";
import { AgentTrace } from "./components/AgentTrace";
import { CostLog } from "./components/CostLog";

export default function App() {
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveAvailable, setLiveAvailable] = useState(false);
  const [useLive, setUseLive] = useState(false);

  // Ask the backend whether real models are available (a key is configured).
  useEffect(() => {
    fetchStatus().then((s) => setLiveAvailable(s.live_available)).catch(() => {});
  }, []);

  // The signature element: re-tint the whole interface from the deck's committed colors.
  useEffect(() => {
    applyAccent(result?.archetype.committed_colors ?? []);
  }, [result]);

  const run = useCallback(async (fn: () => Promise<PipelineResult>) => {
    setBusy(true);
    setError(null);
    try {
      setResult(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <span className="brand-name">Draft Assistant</span>
        </div>
        <label
          className={`live-toggle${liveAvailable ? "" : " disabled"}`}
          title={
            liveAvailable
              ? "When on, uploaded screenshots are analyzed with real models (costs a few tokens per pick). The demo is always free."
              : "Add ANTHROPIC_API_KEY to .env to enable real-model analysis."
          }
        >
          <input
            type="checkbox"
            checked={useLive && liveAvailable}
            disabled={!liveAvailable}
            onChange={(e) => setUseLive(e.target.checked)}
          />
          <span>Use real models</span>
          {!liveAvailable && <span className="muted"> (no key)</span>}
        </label>
      </header>

      <main className="main">
        <Dropzone
          onFile={(f) => run(() => recommend(f, useLive && liveAvailable))}
          onDemo={() => run(fetchDemo)}
          busy={busy}
          compact={!!result}
        />

        {error && (
          <div className="error" role="alert">
            <strong>Couldn’t get a recommendation.</strong> {error}
          </div>
        )}

        {!result && !busy && !error && (
          <div className="empty">
            <p>
              Upload a draft screenshot to get a pick — or press{" "}
              <em>Try the demo draft</em> to see the pipeline run end-to-end.
            </p>
          </div>
        )}

        {result && (
          <>
            <Recommendation result={result} />
            <AgentTrace result={result} />
            <CostLog result={result} />
          </>
        )}
      </main>

      <footer className="foot muted">
        The interface wears the deck’s colors — accents are driven by the archetype agent’s
        committed colors.
      </footer>
    </div>
  );
}
