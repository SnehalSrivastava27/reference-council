# Reel Analyst

Scores a creator's recent reels on the five parameters. Stage 2 of the pipeline.

## Before you score

Run the intake:

```bash
python scripts/analyze_creator.py ./reels/ --handle @name --outdir ./out
```

Then **view every contact sheet in `out/sheets/`.** This is not optional and
cannot be skipped for speed. The machine score covers pacing and lighting only.
Background, hook and outfit are invisible to it — a reel can measure perfectly
and still be a woman talking at a blank wall in a hoodie.

For every reel that looks like a shortlist candidate, also open the hook frames
in `out/hooks/<reel>/`. The first three seconds decide the hook score and the
contact sheet's first tile is too small to read caption timing.

## Scoring

Use `references/scoring_rubric.md`. Score all five parameters 1–5 for every reel.
Record the measured figures alongside the judgement scores — when you later tell
a creator her pacing is good, you want to be able to say "1.1 second average"
rather than "felt snappy".

Work through all 12 before forming a view. The temptation is to score the first
three carefully and pattern-match the rest; that produces a shortlist of
whichever reels happened to come first alphabetically.

## What you are looking for beyond the score

**Range.** Does she do more than one thing? A creator with twelve near-identical
reels is a risk regardless of how good those reels are, because a collab brief
asks her to do something slightly new.

**Her best instinct.** Somewhere in twelve reels there is usually one moment
where she did something genuinely good — a light through her hair, a hook that
lands, a background with real depth. Find it. That moment is the single most
valuable output of this stage, because it becomes the spine of the brief.

**Her default.** What does she reach for when not thinking? That is what she will
produce under deadline, so the brief has to work with it or explicitly against it.

**The gap.** The one parameter she consistently scores 2 on. Not to criticise —
to make sure the brief compensates. If she never gets hair separation, the brief
specifies the location and time of day rather than leaving it to her.

## Output — internal scorecard

```markdown
# Reel Analysis — @handle
**Reels reviewed:** 12  |  **Date:**

## Scores
| Reel | BG | Light | Pace | Hook | Outfit | Total | Measured (avg shot / luma / warmth) |
|---|---|---|---|---|---|---|---|

## Read
**Her best instinct:** the single strongest thing across all 12, with the reel name
**Her default:** what she does on autopilot
**The gap:** the parameter she consistently underperforms
**Range:** narrow / moderate / wide
**Hook fit:** natural fit / fixable / needs rebuilding (per hook_library.md)
**Suggested archetype:**
**Suggested pillar:**

## Risks
What is most likely to go wrong on a collab, and what the brief must specify to prevent it

## Shortlist candidates
Three reel names, ranked, with the parameter each one demonstrates
```

Hand this to `shortlist_and_praise.md`. Never hand it to the creator.
