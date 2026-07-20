import type { Color } from "./api";

// WUBRG accent set from the approved design proposal.
export const COLOR_HEX: Record<Color, string> = {
  W: "#EDE7C8",
  U: "#2C6FB2",
  B: "#5B4A67",
  R: "#B23A2E",
  G: "#2F7D57",
};

export const COLOR_NAME: Record<Color, string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
};

// Neutral pewter used before any colors are committed (e.g. Pack 1 Pick 1).
const NEUTRAL = "#A7A2B4";

/**
 * The signature element: derive the interface accent from the deck's committed colors.
 * - 0 colors  -> quiet neutral pewter (undecided)
 * - 1 color   -> that color, solid
 * - 2+ colors -> a gradient across the identity (guild/shard feel)
 */
export function accentFor(colors: Color[]): { solid: string; gradient: string } {
  if (colors.length === 0) {
    return { solid: NEUTRAL, gradient: NEUTRAL };
  }
  if (colors.length === 1) {
    const hex = COLOR_HEX[colors[0]];
    return { solid: hex, gradient: hex };
  }
  const stops = colors.map((c) => COLOR_HEX[c]);
  // Repeat the first stop at the end for a smoother sweep across three+ colors.
  const sweep = stops.length > 2 ? [...stops, stops[0]] : stops;
  return {
    solid: stops[0],
    gradient: `linear-gradient(120deg, ${sweep.join(", ")})`,
  };
}

/** Apply the accent to CSS custom properties on the document root. */
export function applyAccent(colors: Color[]): void {
  const { solid, gradient } = accentFor(colors);
  const root = document.documentElement;
  root.style.setProperty("--accent", solid);
  root.style.setProperty("--accent-gradient", gradient);
}
