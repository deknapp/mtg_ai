import type { DeckCard, SealedResult } from "../api";
import { COLOR_HEX, COLOR_NAME } from "../theme";

const CURVE_KEYS = ["1", "2", "3", "4", "5", "6+"];
const SRC_SHORT: Record<string, string> = {
  ArenaDirect_Sealed: "event", Sealed: "sealed", TradSealed: "sealed",
  PremierDraft: "draft", TradDraft: "draft", QuickDraft: "draft",
};

function ratingPct(r: number | null): string {
  return r === null ? "—" : `${(r * 100).toFixed(1)}%`;
}

/** Win-rate with a source-tag, or a bomb/no-data marker for cards 17Lands hasn't rated yet. */
function ratingLabel(c: DeckCard): { text: string; title: string } {
  if (c.rating !== null) {
    const src = SRC_SHORT[c.rating_source ?? ""] ?? c.rating_source ?? "";
    return {
      text: `${(c.rating * 100).toFixed(1)}% ${src}`,
      title: `17Lands games-in-hand win rate, source: ${c.rating_source ?? "unknown"}`,
    };
  }
  const bomb = (c.rarity ?? "").toLowerCase() === "rare" || (c.rarity ?? "").toLowerCase() === "mythic";
  return bomb
    ? { text: "no data", title: "No 17Lands win-rate yet — judged from the card (bomb)" }
    : { text: "—", title: "No 17Lands win-rate" };
}

function CardRow({ c }: { c: DeckCard }) {
  const tag = c.is_bomb ? "★" : c.role === "removal" ? "✜" : "";
  const r = ratingLabel(c);
  return (
    <li className={`deck-card${c.is_bomb ? " bomb" : ""}`}>
      <span className="dc-line">
        {tag && <span className="dc-tag" aria-hidden>{tag}</span>}
        <span className="dc-name" title={c.name}>{c.name}</span>
      </span>
      <span className="dc-rating muted" title={r.title}>{r.text}</span>
    </li>
  );
}

export function SealedView({ result }: { result: SealedResult }) {
  const { deck, pool, colorpair_scores, chosen_colors } = result;
  const byCmc: Record<string, DeckCard[]> = Object.fromEntries(CURVE_KEYS.map((k) => [k, []]));
  for (const c of deck.spells) {
    const key = c.cmc >= 6 ? "6+" : String(Math.max(1, Math.floor(c.cmc)));
    (byCmc[key] ??= []).push(c);
  }
  const maxCol = Math.max(1, ...CURVE_KEYS.map((k) => byCmc[k].length));

  return (
    <div className="sealed">
      {/* Hero: the built deck */}
      <section className="hero">
        <div className="hero-colors">
          {chosen_colors.map((c) => (
            <span key={c} className="pip" style={{ background: COLOR_HEX[c] }} title={COLOR_NAME[c]} />
          ))}
          <h1 className="hero-title">{chosen_colors.map((c) => COLOR_NAME[c]).join(" / ")}</h1>
          <span className={`built-by ${result.built_by === "ai" ? "ai" : ""}`}>
            {result.built_by === "ai" ? "✦ AI reasoned" : "optimizer"}
          </span>
        </div>
        <div className="hero-stats">
          <b>{deck.total_cards}-card deck</b>
          <span className="muted">{deck.spells.length} spells · {deck.manabase.total_lands} lands</span>
          <span className="stat">{deck.creatures} creatures</span>
          <span className="stat">{deck.removal} removal</span>
          <span className="stat">{deck.bombs.length} bomb{deck.bombs.length === 1 ? "" : "s"}</span>
        </div>
        <p className="hero-rationale">{deck.rationale}</p>
        {result.synergies.length > 0 && (
          <ul className="synergies">
            {result.synergies.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        )}
        {pool.event && <p className="muted pool-line">Pool: {pool.cards.length} cards · {pool.event}</p>}
      </section>

      {/* Curve columns */}
      <section className="panel">
        <h2 className="panel-h">The deck, by curve</h2>
        <div className="curve">
          {CURVE_KEYS.map((k) => (
            <div key={k} className="curve-col">
              <ul className="curve-cards">
                {byCmc[k].map((c, i) => (
                  <CardRow c={c} key={c.name + i} />
                ))}
              </ul>
              <div className="curve-axis">
                <span className="curve-count">{byCmc[k].length}</span>
                <span className="curve-mv muted">{k}</span>
                <div className="curve-bar" style={{ height: `${(byCmc[k].length / maxCol) * 40 + 4}px` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="two-col">
        {/* Manabase */}
        <section className="panel">
          <h2 className="panel-h">Manabase <span className={`chip ${deck.manabase.feasible ? "ok" : "warn"}`}>
            {deck.manabase.feasible ? "castable" : "tight"}</span></h2>
          <ul className="lands">
            {Object.entries(deck.manabase.lands).map(([land, n]) => (
              <li key={land}><b>{n}×</b> {land}</li>
            ))}
          </ul>
          {deck.manabase.splash_colors.length > 0 && (
            <p className="muted">Splash: {deck.manabase.splash_colors.map((c) => COLOR_NAME[c]).join(", ")}
              {deck.manabase.fixing.length > 0 && <> — off {deck.manabase.fixing.join(", ")}</>}</p>
          )}
          <ul className="notes muted">
            {deck.manabase.notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </section>

        {/* Color-pair reasoning */}
        <section className="panel">
          <h2 className="panel-h">Colors considered</h2>
          <table className="pairs">
            <thead>
              <tr><th>Pair</th><th>Score</th><th>Playable</th><th>Bombs</th><th>Rem.</th></tr>
            </thead>
            <tbody>
              {colorpair_scores.slice(0, 5).map((s, i) => (
                <tr key={s.label} className={i === 0 ? "chosen" : ""}>
                  <td className="pair-label">
                    {s.colors.map((c) => (
                      <span key={c} className="pip sm" style={{ background: COLOR_HEX[c] }} />
                    ))}
                    {s.label}
                  </td>
                  <td>{s.deck_score.toFixed(2)}</td>
                  <td>{s.playable_count}</td>
                  <td>{s.bomb_count}</td>
                  <td>{s.removal_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      {/* Three-color / splash options */}
      {(result.splash_options ?? []).length > 0 && (
        <section className="panel">
          <h2 className="panel-h">Three-color / splash options</h2>
          <ul className="splashes">
            {(result.splash_options ?? []).map((s) => {
              const isChosen =
                chosen_colors.length === s.colors.length &&
                s.colors.every((c) => chosen_colors.includes(c));
              return (
                <li key={s.label} className={`splash${isChosen ? " chosen" : ""}`}>
                  <span className="splash-head">
                    {s.colors.map((c) => (
                      <span key={c} className="pip sm" style={{ background: COLOR_HEX[c] }} />
                    ))}
                    <b>{s.label}</b>
                    {isChosen && <span className="tag-built">built</span>}
                  </span>
                  <span className="splash-add">
                    {s.added_bomb_count > 0 && <span className="splash-bomb">★ {s.added_bomb_count} bomb </span>}
                    adds {s.added_cards.join(", ")}
                  </span>
                  <span className="muted splash-fix">
                    +{s.power_gain.toFixed(2)} power · {s.fixing_count} fixing land
                    {s.fixing_count === 1 ? "" : "s"} for {COLOR_NAME[s.splash_color]}
                    {s.fixing_lands.length > 0 && ` (${s.fixing_lands.join(", ")})`}
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="muted">
            A splash is only as strong as its fixing — the manabase check flags one it can’t support.
          </p>
        </section>
      )}

      {/* Sideboard + pipeline */}
      <div className="two-col">
        {deck.sideboard_highlights.length > 0 && (
          <section className="panel">
            <h2 className="panel-h">Next best (sideboard)</h2>
            <ul className="sideboard">
              {deck.sideboard_highlights.map((c, i) => (
                <li key={c.name + i}><span className="dc-name">{c.name}</span>
                  <span className="muted">{ratingPct(c.rating)}</span></li>
              ))}
            </ul>
          </section>
        )}
        <section className="panel">
          <h2 className="panel-h">Pipeline</h2>
          <ul className="pipeline">
            {result.cost_log.map((c, i) => (
              <li key={i}><span className="agent">{c.agent}</span>
                <span className="muted">{c.model}</span></li>
            ))}
          </ul>
          <p className="muted">Color choice, selection and manabase are deterministic — free and inspectable.</p>
        </section>
      </div>
    </div>
  );
}
