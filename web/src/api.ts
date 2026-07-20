// Types mirror the backend Pydantic models (see src/mtg_draft_assistant/models.py).
// Kept in one place so the components consume a single, typed shape.

export type Color = "W" | "U" | "B" | "R" | "G";

export interface Card {
  name: string;
  mana_cost: string | null;
  cmc: number;
  colors: Color[];
  type_line: string | null;
  oracle_text: string | null;
  rarity: string | null;
  power: string | null;
  toughness: string | null;
  rating: number | null;
  unresolved: boolean;
}

export interface DraftState {
  picked: string[];
  pack: string[];
}

export interface EnrichedDraftState {
  picked: Card[];
  pack: Card[];
}

export interface ArchetypeRead {
  committed_colors: Color[];
  open_lanes: string[];
  curve_gaps: string[];
  summary: string;
}

export interface CardScore {
  name: string;
  power_score: number;
  signal_score: number;
  note: string;
}

export interface EvaluationResult {
  ranked: CardScore[];
}

export interface Alternative {
  name: string;
  reason: string;
}

export interface PickRecommendation {
  pick: string;
  alternatives: Alternative[];
  rationale: string;
}

export interface CostEntry {
  agent: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
}

export interface PipelineResult {
  draft_state: DraftState;
  enriched: EnrichedDraftState;
  archetype: ArchetypeRead;
  evaluation: EvaluationResult;
  recommendation: PickRecommendation;
  cost_log: CostEntry[];
}

async function parse(res: Response): Promise<PipelineResult> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body; keep the status line */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Whether real-model analysis is available (a key is configured on the backend). */
export async function fetchStatus(): Promise<{ live_available: boolean }> {
  const res = await fetch("/api/status");
  if (!res.ok) return { live_available: false };
  return res.json();
}

/** Run the built-in demo draft (mock backend = zero API cost). */
export async function fetchDemo(): Promise<PipelineResult> {
  return parse(await fetch("/api/demo"));
}

/**
 * Upload a draft screenshot and get a recommendation.
 * `live` opts into real models; the backend ignores it unless a key is configured.
 */
export async function recommend(file: File, live: boolean): Promise<PipelineResult> {
  const form = new FormData();
  form.append("screenshot", file);
  const q = live ? "?live=true" : "";
  return parse(await fetch(`/api/recommend${q}`, { method: "POST", body: form }));
}

// --- Sealed ----------------------------------------------------------------------------------
// Mirrors src/mtg_ai/sealed/models.py.

export interface ColorPairScore {
  label: string;
  colors: Color[];
  playable_count: number;
  deck_score: number;
  avg_rating: number;
  bomb_count: number;
  removal_count: number;
  creature_count: number;
  note: string;
}

export interface DeckCard {
  name: string;
  cmc: number;
  colors: Color[];
  rarity: string | null;
  rating: number | null;
  rating_source: string | null; // which 17Lands format the rating came from
  is_bomb: boolean;
  role: string; // creature | removal | other
}

export interface Manabase {
  lands: Record<string, number>;
  sources: Record<string, number>;
  fixing: string[];
  splash_colors: Color[];
  total_lands: number;
  feasible: boolean;
  notes: string[];
}

export interface SealedDeck {
  colors: Color[];
  spells: DeckCard[];
  manabase: Manabase;
  curve: Record<string, number>;
  bombs: string[];
  creatures: number;
  removal: number;
  total_cards: number;
  sideboard_highlights: DeckCard[];
  rationale: string;
}

export interface Pool {
  set_code: string;
  event: string | null;
  cards: Card[];
  unresolved_ids: number[];
}

export interface SplashSuggestion {
  label: string; // e.g. "WU + R"
  colors: Color[];
  base_colors: Color[];
  splash_color: Color;
  added_cards: string[];
  added_bomb_count: number;
  power_gain: number;
  fixing_count: number;
  fixing_lands: string[];
  note: string;
}

/** A previous AI build, sent back on "Iterate with AI" so the model refines it. */
export interface PriorBuild {
  colors: Color[];
  maindeck: string[];
  rationale: string;
}

export interface SealedResult {
  pool: Pool;
  colorpair_scores: ColorPairScore[];
  splash_options: SplashSuggestion[];
  chosen_colors: Color[];
  deck: SealedDeck;
  cost_log: CostEntry[];
  built_by: string; // "deterministic" | "ai"
  synergies: string[];
}

async function parseSealed(res: Response): Promise<SealedResult> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep the status line */
    }
    throw new Error(detail);
  }
  return res.json();
}

/** Whether the AI build is available (an Anthropic API key is configured on the backend). */
export async function fetchSealedStatus(): Promise<{ ai_available: boolean }> {
  const res = await fetch("/api/sealed/status");
  if (!res.ok) return { ai_available: false };
  return res.json();
}

/** Build query string from ai + optional free-text guidance (guidance only affects AI builds). */
function aiQuery(ai: boolean, guidance = ""): string {
  const params = new URLSearchParams();
  if (ai) params.set("ai", "true");
  if (guidance.trim()) params.set("guidance", guidance.trim());
  const q = params.toString();
  return q ? `?${q}` : "";
}

/** Build from the bundled sample pool. `ai` lets Opus reason over the build. */
export async function fetchSealedDemo(ai = false, guidance = ""): Promise<SealedResult> {
  return parseSealed(await fetch(`/api/sealed/demo${aiQuery(ai, guidance)}`));
}

/** Build from the player's live Arena sealed pool (auto-found log). `ai` opts into reasoning. */
export async function buildSealed(ai = false, guidance = ""): Promise<SealedResult> {
  return parseSealed(await fetch(`/api/sealed/build${aiQuery(ai, guidance)}`));
}

/** One sealed pool found in the Arena log, with metadata to help the user recognize it. */
export interface PoolSummary {
  index: number; // 0 = most recently active
  timestamp: string | null; // e.g. "7/20/2026 8:12:39 AM"
  event: string | null;
  set_code: string | null;
  card_count: number;
  sample_cards: string[]; // a few notable (highest-rarity) names
  grp_ids: number[];
}

export interface PoolListResponse {
  pools: PoolSummary[];
  detailed_logs: boolean | null; // whether Arena's Detailed Logs were on
  log_path: string | null;
}

/** List every distinct sealed pool in the Arena log so the user can pick the right one. */
export async function fetchPools(): Promise<PoolListResponse> {
  const res = await fetch("/api/sealed/pools");
  if (!res.ok) return { pools: [], detailed_logs: null, log_path: null };
  return res.json();
}

/**
 * Build from a specific pool the user selected in the picker.
 * `ai` opts into reasoning; `guidance` is a free-text steer honored only on AI builds.
 */
export async function buildSealedPool(
  pool: PoolSummary,
  ai = false,
  guidance = "",
  prior: PriorBuild | null = null,
): Promise<SealedResult> {
  return parseSealed(
    await fetch(`/api/sealed/build${ai ? "?ai=true" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grp_ids: pool.grp_ids,
        set_code: pool.set_code,
        event: pool.event,
        guidance: guidance.trim(),
        prior, // non-null on "Iterate with AI" -> the model refines this build
      }),
    }),
  );
}
