"""Sealed deck builder (current focus).

Auto-imports a Magic: The Gathering Arena sealed pool from the local Arena log and builds the
best legal 40-card deck for it. The pipeline:

    Arena log -> pool (grpId -> card) -> 17Lands ratings join
              -> color-pair scoring (all 10 pairs) -> deck build (mana optimizer + bombs + LLM synergy)
              -> a legal, mana-feasible 40-card deck with rationale

Most of the work is deterministic optimization (color choice, card selection, manabase) — cheap
and inspectable. An LLM step is reserved for synergy judgement and the readable rationale.
"""
