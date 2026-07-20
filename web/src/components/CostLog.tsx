import type { PipelineResult } from "../api";

/** Per-agent cost + model routing. Makes the cheap/strong tier split visible. */
export function CostLog({ result }: { result: PipelineResult }) {
  const rows = result.cost_log;
  const totals = rows.reduce(
    (acc, c) => ({
      input: acc.input + c.input_tokens,
      output: acc.output + c.output_tokens,
      cached: acc.cached + c.cached_input_tokens,
    }),
    { input: 0, output: 0, cached: 0 },
  );

  return (
    <section className="cost">
      <h2 className="section-label">Cost &amp; model routing</h2>
      <table className="cost-table">
        <thead>
          <tr>
            <th>Agent</th><th>Model</th><th className="num">In</th>
            <th className="num">Out</th><th className="num">Cached</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.agent}>
              <td>{c.agent}</td>
              <td className="model">{c.model}</td>
              <td className="num">{c.input_tokens}</td>
              <td className="num">{c.output_tokens}</td>
              <td className="num">{c.cached_input_tokens}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>total</td><td />
            <td className="num">{totals.input}</td>
            <td className="num">{totals.output}</td>
            <td className="num">{totals.cached}</td>
          </tr>
        </tfoot>
      </table>
    </section>
  );
}
