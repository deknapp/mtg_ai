import { useCallback, useEffect, useRef, useState } from "react";
import {
  buildSealed,
  buildSealedPool,
  fetchPools,
  fetchSealedDemo,
  fetchSealedStatus,
  type PoolSummary,
  type SealedResult,
} from "./api";
import { applyAccent } from "./theme";
import { SealedView } from "./components/SealedView";

/** "7/20/2026 8:12:39 AM" -> "Jul 20, 8:12 AM" (falls back to the raw string). */
function formatWhen(ts: string | null): string {
  if (!ts) return "unknown time";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** A one-line label for a pool option: when · SET · N cards · a few notable names. */
function poolLabel(p: PoolSummary): string {
  const set = (p.set_code ?? "?").toUpperCase();
  const names = p.sample_cards.slice(0, 3).join(", ");
  const head = `${formatWhen(p.timestamp)} · ${set} · ${p.card_count} cards`;
  return names ? `${head} · ${names}` : head;
}

export default function App() {
  const [result, setResult] = useState<SealedResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyMsg, setBusyMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [aiAvailable, setAiAvailable] = useState(false);
  const [pools, setPools] = useState<PoolSummary[]>([]);
  const [selected, setSelected] = useState(0);
  const [detailedLogs, setDetailedLogs] = useState<boolean | null>(null);
  const started = useRef(false);

  useEffect(() => {
    fetchSealedStatus().then((s) => setAiAvailable(s.ai_available)).catch(() => {});
  }, []);

  // Discover the sealed pools sitting in the Arena log so the user can choose which to build.
  useEffect(() => {
    fetchPools()
      .then((r) => {
        setPools(r.pools);
        setDetailedLogs(r.detailed_logs);
        setSelected(0); // index 0 is the most recently active pool
      })
      .catch(() => {});
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

  // Build the pool the user picked. Falls back to the auto-find endpoint (which returns an
  // actionable error) when no pools were discovered, so the message flow is unchanged.
  const buildChosen = useCallback(
    (ai: boolean) => {
      const pool = pools[selected];
      const msg = ai ? "Reasoning over your pool with Opus… (~15s)" : "Building your selected pool…";
      return pool
        ? run(() => buildSealedPool(pool, ai), msg)
        : run(() => buildSealed(ai), msg);
    },
    [pools, selected, run],
  );

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
          {pools.length > 0 && (
            <label className="pool-picker" title="Choose which sealed pool from your Arena log to build">
              <span className="pool-picker-label">Pool</span>
              <select
                className="pool-select"
                value={selected}
                disabled={busy}
                onChange={(e) => setSelected(Number(e.target.value))}
              >
                {pools.map((p) => (
                  <option key={p.index} value={p.index}>
                    {p.index === 0 ? "★ latest — " : ""}
                    {poolLabel(p)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            className="btn"
            disabled={busy || !aiAvailable}
            title={aiAvailable ? "Opus reasons over the selected pool (~15s, uses your API key)"
              : "Add ANTHROPIC_API_KEY to .env to enable AI builds"}
            onClick={() => buildChosen(true)}
          >
            ✦ Build with AI{!aiAvailable && <span className="muted"> (no key)</span>}
          </button>
          <button className="btn ghost" disabled={busy} onClick={() => buildChosen(false)}>
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
        {!busy && pools.length > 1 && (
          <p className="pool-note">
            Found {pools.length} sealed pools in your Arena log. Selected:{" "}
            <strong>{poolLabel(pools[selected])}</strong>. Use the <em>Pool</em> menu to switch,
            then <em>Quick build</em> or <em>Build with AI</em>.
          </p>
        )}
        {!busy && pools.length === 0 && detailedLogs === false && (
          <p className="pool-note">
            No sealed pool found, and Arena’s <strong>Detailed Logs (Plugin Support)</strong> is
            off. Turn it on, fully quit and reopen Arena, open your sealed event, then reload.
          </p>
        )}

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
