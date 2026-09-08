# Scale Operations — running this on 1000+ creators

At roster scale the binding constraint stops being judgement and becomes
**attention budget**. 1000 creators × 12 reels is 12,000 videos. Nobody watches
that, and no model should be asked to look at that either. The pipeline is
therefore a funnel: cheap measurement on everything, vision only on survivors,
human judgement only on finalists.

## The funnel

```
12,000 reels          machine pass          ffmpeg + numpy, no model
      │                                     ~8s/reel/core
      ▼
1000 creators         triage gate           AUTO-REJECT / BORDERLINE / REVIEW
      │                                     typically rejects 30-45%
      ▼
~600 creators         vision pass           4 contact sheets each = ~2,400 images
      │                                     scores Background, Hook, Outfit
      ▼
~150 creators         shortlist + praise    2-3 reels each, written per creator
      │
      ▼
target roster         briefs                one .md per creator
```

The two numbers that matter: **the gate must remove enough to make the vision
pass affordable**, and **the vision pass must look at few enough reels per
creator to stay affordable**. `--review-top 4` rather than all 12 is a 3×
saving on the largest cost in the pipeline.

## Throughput

Measured: **~8.3s per reel per core** for the full measurement pass (single
decode, both cut thresholds, colour sampling).

| Cores | 12,000 reels |
|---|---|
| 1 | ~28 hours |
| 8 | ~3.5 hours |
| 16 | ~1.7 hours |
| 32 | ~52 min |

Run it overnight on one 16-core box. It is embarrassingly parallel — split the
roster across machines by subfolder if you need it faster.

```bash
python scripts/batch_run.py ./roster/ --outdir ./run_2026_08 --workers 16
```

**Always use `--resume`.** A run this long will be interrupted. Resume skips any
creator whose `creator_analysis.json` already exists and still emits a summary
covering the full roster.

## Storage

12,000 reels at ~12MB each is roughly 150GB of source video. The outputs are
small — a contact sheet is ~500KB and you only generate them for survivors, so
budget ~2GB for 2,400 sheets. **Delete source video after the machine pass**;
the JSON and the sheets are what downstream stages need. Keep the source only
for creators who reach the shortlist stage, in case you need a closer look.

## Determinism and drift

At this scale you will re-run the pipeline, and you need last month's scores to
mean the same thing as this month's.

**The machine half is deterministic.** Same file in, same numbers out. Pin the
ffmpeg version — scene-detection scores shift slightly across major releases,
which moves the gate.

**The vision half is not.** Model scoring of Background, Hook and Outfit will
drift across runs and across model versions. Two controls:

1. **Calibration set.** Keep 15–20 already-scored reels spanning the full 1–5
   range on each parameter. Re-score them at the start of every batch. If the
   scores have moved more than a point, the rubric anchors need re-reading
   before the batch proceeds — not after.
2. **Score with anchors visible.** Always load `references/scoring_rubric.md`
   into the scoring context. Scoring from memory of the rubric is where drift
   starts.

Record the model version, ffmpeg version, campaign profile and gate settings in
every run directory. A score without its context is not comparable to anything.

## Batch hygiene

**Score all of one creator's reels before moving to the next.** Cross-creator
interleaving invites relative scoring — "better than the last one I saw" — and
the rubric is absolute.

**Re-anchor every ~50 creators.** Re-read the rubric anchors and re-score one
calibration reel. Long batches drift toward the middle of the scale.

**Watch the distribution.** If more than about 60% of scores on any parameter
land on 3, the rubric is being applied as a shrug rather than a judgement.
Healthy output has a spread.

**Never let the machine score pick the shortlist.** It covers Pacing and
Lighting only. A reel can score 10/10 and open with "hi guys," which is an
automatic fail. The machine ranks *review order*; eyes pick the shortlist.

## Quality assurance on the roster

Sample-audit rather than review everything:

- **Pull 5% of AUTO-REJECTs and eyeball them.** If good creators are being
  rejected, the gate is too tight — lower `--min-machine` and re-run. This is
  the cheapest check available and the one most worth doing.
- **Pull 5% of shortlists and check the praise.** Every note should be specific
  enough that it could only have been written about that reel. Generic praise is
  the first symptom of a batch running on autopilot.
- **Check parameter spread across shortlists.** If 80% of praise notes are about
  lighting, the scoring is collapsing onto one dimension.

## Cost control levers

Ranked by saving per unit of quality lost:

1. `--review-top 3` instead of 4 — 25% off the vision pass, small quality cost
2. Raise `--min-machine` to 6 — cuts the review queue substantially, but recheck
   your AUTO-REJECT sample afterwards
3. `--no-sheets` on a first sweep to size the roster, then a second pass with
   sheets on survivors only — two decodes, but the second is over a much smaller set
4. Shorter contact sheets (16 frames instead of 24) — noticeably harder to judge
   hook and background, use only if forced

Do not save money by skipping the hook frames. The hook is the parameter most
likely to disqualify a creator, and it is judged in three seconds of footage.

## When the roster is this big, the real risk

It is not bad scoring. It is **template convergence** — 200 briefs that all
specify a soft pastel wall, window light, and a 1.0s cut because that is what
the reference set does most often. Run the variety gate in
`agents/orchestrator.md` on every batch of briefs before delivery, and track
background-archetype distribution across the roster as a headline metric. If
more than half the roster is shooting against the same kind of wall, the
campaign will look like one creator posted 200 times.
