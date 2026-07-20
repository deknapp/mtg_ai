import { useCallback, useEffect, useState } from "react";
import { buildSealed, fetchSealedDemo, type SealedResult } from "./api";
import { applyAccent } from "./theme";
import { SealedView } from "./components/SealedView";

export default function App() {
  const [result, setResult] = useState<SealedResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-tint the whole interface from the built deck's colors (the signature element).
  useEffect(() => {
    applyAccent(result?.chosen_colors ?? []);
  }, [result]);

  const run = useCallback(async (fn: () => Promise<SealedResult>) => {
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

  // Open on the sample build so there's always something on screen.
  useEffect(() => {
    run(fetchSealedDemo);
  }, [run]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <span className="brand-name">MTG AI · Sealed</span>
        </div>
        <div className="actions">
          <button className="btn" disabled={busy} onClick={() => run(buildSealed)}>
            Build from my Arena pool
          </button>
          <button className="btn ghost" disabled={busy} onClick={() => run(fetchSealedDemo)}>
            Sample pool
          </button>
        </div>
      </header>

      <main className="main">
        {busy && <div className="empty">Building the best deck from your pool…</div>}

        {error && !busy && (
          <div className="error" role="alert">
            <strong>Couldn’t read your Arena pool.</strong>
            <pre className="error-detail">{error}</pre>
            <p className="muted">
              The sample pool still works — press <em>Sample pool</em> above.
            </p>
          </div>
        )}

        {result && !busy && <SealedView result={result} />}
      </main>

      <footer className="foot muted">
        The interface wears the deck’s colors — accents are driven by the chosen color pair.
      </footer>
    </div>
  );
}
