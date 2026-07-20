import { useCallback, useEffect, useRef, useState } from "react";
import { buildSealed, fetchSealedDemo, fetchSealedStatus, type SealedResult } from "./api";
import { applyAccent } from "./theme";
import { SealedView } from "./components/SealedView";

export default function App() {
  const [result, setResult] = useState<SealedResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyMsg, setBusyMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [aiAvailable, setAiAvailable] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    fetchSealedStatus().then((s) => setAiAvailable(s.ai_available)).catch(() => {});
  }, []);

  useEffect(() => {
    applyAccent(result?.chosen_colors ?? []);
  }, [result]);

  const run = useCallback(async (fn: () => Promise<SealedResult>, msg: string) => {
    setBusy(true);
    setBusyMsg(msg);
    setError(null);
    try {
      setResult(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }, []);

  // Open on the deterministic sample so there's always something on screen (free, instant).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    run(() => fetchSealedDemo(false), "Building the sample deck…");
  }, [run]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <span className="brand-name">MTG AI · Sealed</span>
        </div>
        <div className="actions">
          <button
            className="btn"
            disabled={busy || !aiAvailable}
            title={aiAvailable ? "Opus reasons over your pool (~15s, uses your API key)"
              : "Add ANTHROPIC_API_KEY to .env to enable AI builds"}
            onClick={() => run(() => buildSealed(true), "Reasoning over your pool with Opus… (~15s)")}
          >
            ✦ Build with AI{!aiAvailable && <span className="muted"> (no key)</span>}
          </button>
          <button className="btn ghost" disabled={busy}
            onClick={() => run(() => buildSealed(false), "Building from your pool…")}>
            Quick build
          </button>
          <button className="btn ghost" disabled={busy}
            onClick={() => run(() => fetchSealedDemo(aiAvailable), aiAvailable
              ? "Reasoning over the sample pool with Opus…" : "Building the sample deck…")}>
            Sample
          </button>
        </div>
      </header>

      <main className="main">
        {busy && <div className="empty">{busyMsg}</div>}

        {error && !busy && (
          <div className="error" role="alert">
            <strong>Couldn’t read your Arena pool.</strong>
            <pre className="error-detail">{error}</pre>
            <p className="muted">Press <em>Sample</em> above to see a build on the bundled pool.</p>
          </div>
        )}

        {result && !busy && <SealedView result={result} />}
      </main>

      <footer className="foot muted">
        The interface wears the deck’s colors — accents are driven by the chosen colors.
      </footer>
    </div>
  );
}
