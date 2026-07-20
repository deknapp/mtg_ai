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
