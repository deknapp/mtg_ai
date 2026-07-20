# Manabase model (Frank-Karsten, splash-aware)

`sealed/manabase.py` decides whether a chosen set of spells is actually castable and builds the
17-land base. It's the deterministic guardrail behind objective A: never recommend a deck you
can't cast. This note documents the numbers and the method so they're auditable.

## The core idea (Frank Karsten)

Karsten's mana research answers one question: **how many sources of a color do you need to
reliably cast a card with N colored pips by the turn you want it?** ("Reliably" ≈ ~90% of games.)
It is a *source-count* model, not a splash reward — splashes just come out cheap because the math
says so.

We use a compact 40-card (limited) table for the number of colored **pips** a single card needs,
cast **on curve**:

| colored pips (of one color) | sources on curve |
|---|---|
| 1 (e.g. `{2}{R}`) | 9 |
| 2 (e.g. `{R}{R}`) | 14 |
| 3 (e.g. `{R}{R}{R}`) | 17 |

Then we apply a **timing discount**: every turn you can afford to cast the card *later* than its
earliest natural turn (`pips + 1`) removes ~1 required source (you have more draw steps to find
one). Floors: 6 sources for single-pip, 9 for double-pip.

```
sources_needed(pips, cmc) = max(floor, base[pips] - max(0, floor(cmc) - (pips + 1)))
```

Worked examples:
- `{R}{R}` two-drop → `14 - 0 = 14` sources. Double-pip on turn 2 is genuinely demanding.
- `{2}{W}` three-drop (1 pip) → `9 - max(0, 3-2) = 8` sources.
- `{4}{W}` five-drop bomb, single pip → `9 - max(0, 5-2) = 6` sources. **This is why a late,
  single-pip splash is cheap** — six sources is a rainbow land or two plus a couple of basics.

## Main vs splash

A color is treated as a **splash** when it has ≤ 4 total colored pips across the deck **and** no
card that costs it at 3 mana or less (nothing you need early). Splash colors get the low, late
Karsten requirement; main colors get the on-curve requirement.

## Building the base (17 lands)

1. **Fixing first.** Pull the pool's nonbasic lands whose `produced_mana` covers a deck color
   (Scryfall `produced_mana`, ingested per card). Each counts as a source for *every* color it
   makes. This is what lets the third color work — a rainbow land is +1 to all three colors.
2. **Basics fill the rest**, sized so each color reaches its Karsten requirement, with any surplus
   weighted toward the main colors (by pip demand).
3. **Feasibility** flags any color whose sources fall more than one below its requirement, tagged
   `main` or `splash`, so a greedy build is called out rather than silently shipped.

## Why this matters for the AI build

The AI picks colors and cards; this optimizer runs on *its* choice and reports what the mana
supports. The pool's fixing lands and this feasibility read are handed to the AI in its prompt,
so a bomb splash off adequate fixing reads as *castable* — which is how a human sealed player
justifies going three colors for the bombs, and now the tool does too.

## Caveats

- The pip table is a compact approximation of Karsten's fuller per-turn tables; it's tuned for
  40-card limited and errs slightly conservative.
- We don't yet model tapped-land timing, mana rocks/ramp as fixing, or off-color activated costs.
  Those are refinements, not blockers.
