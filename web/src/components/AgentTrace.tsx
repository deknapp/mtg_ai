import { useState } from "react";
import type { PipelineResult } from "../api";
import { ColorPips } from "./ColorPips";

/**
 * Progressive-disclosure drawer that makes the agent network visible:
 * extraction -> archetype -> evaluation -> synthesis, each with its intermediate output.
 */
export function AgentTrace({ result }: { result: PipelineResult }) {
  const [open, setOpen] = useState(false);
  const { draft_state, enriched, archetype, evaluation } = result;
  const unresolved = [...enriched.pack, ...enriched.picked].filter((c) => c.unresolved);

  return (
    <section className="trace">
      <button
        className="trace-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className={`chevron${open ? " open" : ""}`} aria-hidden>▸</span>
        Agent trace
        <span className="muted">extraction → archetype → evaluation → synthesis</span>
      </button>

      {open && (
        <div className="trace-body">
          <details className="stage" open>
            <summary>
              <span className="stage-dot" /> Extraction
              <span className="muted">
                {draft_state.picked.length} picked · {draft_state.pack.length} in pack
              </span>
            </summary>
            <div className="stage-inner">
              <div className="col">
                <h4>Picked pool</h4>
                <ul>{draft_state.picked.map((n) => <li key={n}>{n}</li>)}</ul>
                {draft_state.picked.length === 0 && <p className="muted">Empty (first pick).</p>}
              </div>
              <div className="col">
                <h4>Current pack</h4>
                <ul>{draft_state.pack.map((n) => <li key={n}>{n}</li>)}</ul>
              </div>
              {unresolved.length > 0 && (
                <p className="warn">
                  Unresolved after fuzzy-match: {unresolved.map((c) => c.name).join(", ")}
                </p>
              )}
            </div>
          </details>

          <details className="stage">
            <summary>
              <span className="stage-dot" /> Archetype
              <span className="muted">
                <ColorPips colors={archetype.committed_colors} size={13} />
              </span>
            </summary>
            <div className="stage-inner block">
              <p>{archetype.summary}</p>
              {archetype.open_lanes.length > 0 && (
                <p><strong>Open lanes:</strong> {archetype.open_lanes.join(" · ")}</p>
              )}
              {archetype.curve_gaps.length > 0 && (
                <p><strong>Curve gaps:</strong> {archetype.curve_gaps.join(" · ")}</p>
              )}
            </div>
          </details>

          <details className="stage">
            <summary>
              <span className="stage-dot" /> Evaluation
              <span className="muted">{evaluation.ranked.length} cards ranked</span>
            </summary>
            <div className="stage-inner">
              <table className="rank">
                <thead>
                  <tr><th>Card</th><th>Power</th><th>Signal</th><th>Note</th></tr>
                </thead>
                <tbody>
                  {evaluation.ranked.map((s) => (
                    <tr key={s.name}>
                      <td>{s.name}</td>
                      <td className="num">{s.power_score}</td>
                      <td className="num">{s.signal_score}</td>
                      <td className="note">{s.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
