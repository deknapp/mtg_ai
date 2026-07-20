import type { Card, PipelineResult } from "../api";
import { ColorPips } from "./ColorPips";

function cardByName(result: PipelineResult, name: string): Card | undefined {
  return [...result.enriched.pack, ...result.enriched.picked].find(
    (c) => c.name.toLowerCase() === name.toLowerCase(),
  );
}

/** The hero: the recommended pick on a parchment "card face", framed by the deck's colors. */
export function Recommendation({ result }: { result: PipelineResult }) {
  const rec = result.recommendation;
  const hero = cardByName(result, rec.pick);
  const colors = result.archetype.committed_colors;

  return (
    <section className="hero" aria-label="Recommended pick">
      <div className="hero-frame">
        <div className="hero-face">
          <div className="hero-eyebrow">
            <span>Recommended pick</span>
            <ColorPips colors={colors} />
          </div>
          <h1 className="hero-name">{rec.pick}</h1>
          {hero && (
            <div className="hero-meta">
              {hero.type_line && <span>{hero.type_line}</span>}
              {hero.mana_cost && <span className="mana">{hero.mana_cost}</span>}
              {hero.rarity && <span className="rarity">{hero.rarity}</span>}
            </div>
          )}
          <p className="hero-rationale">{rec.rationale}</p>
        </div>
      </div>

      {rec.alternatives.length > 0 && (
        <div className="alts">
          <h2 className="section-label">Also considered</h2>
          <ul className="alt-list">
            {rec.alternatives.map((a) => {
              const c = cardByName(result, a.name);
              return (
                <li key={a.name} className="alt">
                  <div className="alt-head">
                    <span className="alt-name">{a.name}</span>
                    {c && <ColorPips colors={c.colors} size={14} />}
                  </div>
                  <span className="alt-reason">{a.reason}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
