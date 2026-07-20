import type { Color } from "../api";
import { COLOR_HEX, COLOR_NAME } from "../theme";

/** A row of WUBRG mana pips. White gets a subtle ring so it reads on the dark surface. */
export function ColorPips({ colors, size = 18 }: { colors: Color[]; size?: number }) {
  if (colors.length === 0) {
    return <span className="pips-empty">colorless / undecided</span>;
  }
  return (
    <span className="pips" aria-label={colors.map((c) => COLOR_NAME[c]).join(", ")}>
      {colors.map((c, i) => (
        <span
          key={`${c}-${i}`}
          className="pip"
          title={COLOR_NAME[c]}
          style={{
            width: size,
            height: size,
            background: COLOR_HEX[c],
            boxShadow: c === "W" ? "inset 0 0 0 1px rgba(0,0,0,0.25)" : undefined,
          }}
        />
      ))}
    </span>
  );
}
