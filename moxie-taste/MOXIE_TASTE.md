---
name: moxie-taste
description: The Moxie Beauty creator onboarding standard — analyse a creator's recent reels against five parameters (background, lighting, pacing, hook, outfit), shortlist their best 2-3, and generate a collab brief paired with a matching Moxie reference reel. Use this skill whenever the user is onboarding, vetting, shortlisting or briefing creators for Moxie Beauty or any textured-haircare brand; whenever they upload a batch of a creator's reels and ask what's good in them; whenever they mention creator briefs, collab reels, UGC casting, reference reels, or "does this creator fit our taste"; and whenever they ask to review or score a rough cut. Trigger this even when the request sounds like generic content feedback ("which of these reels is best", "what should she wear", "is this too slow") — the standard here is measured and specific, and answering from general marketing knowledge produces off-brand output. Also use it when a campaign brief doc is supplied as input and creators must be matched against it, and for roster-scale batches of hundreds or thousands of creators. Includes runnable scripts that measure pacing and lighting, triage a roster, and generate contact sheets.
compatibility: Requires ffmpeg/ffprobe plus Python with numpy and Pillow for the measurement scripts. The judgement portions work without them.
---

# Moxie Taste

The house standard for Moxie Beauty short-form video, and the pipeline for
onboarding creators against it at scale.

Derived from frame-level analysis of 15 published films (12 creator-led
wavy-hair narratives, 3 brand and stress-test films) plus measured pacing and
colour data.

**Primary job: creator onboarding.** Ingest a creator's recent reels, score them
on five parameters, shortlist the two or three that already sit closest to Moxie
taste, tell the creator specifically what was good in each, and hand them a
collab brief paired with the Moxie reference reel that rhymes with their own
best work.

The brief works because the creator sees *their own reel* next to a Moxie
reel and recognises the overlap. You are not teaching them a new style. You are
pointing at the thing they already do that Moxie wants more of.

---

## The one-line read

Moxie casts **women with a complicated history with their own hair**, and lets
them narrate the moment that history resolved. The product is the plot twist,
never the premise.

Everything downstream — the warm light, the one-second cuts, the wardrobe that
never wears yellow — exists to keep that testimony believable.

---

## Quickstart

**One creator:**
```bash
python scripts/analyze_creator.py ./reels/ --handle @creator --review-top 4
```

**A roster of hundreds or thousands:**
```bash
python scripts/batch_run.py ./roster/ --outdir ./run_2026_08 --workers 16 --resume
# → review_queue.md  (only the creators worth your eyes)
# → roster_summary.csv
```

Then, for each creator in the review queue:

```
1. Read the campaign brief      → agents/campaign_intake.md   (do this FIRST, once per campaign)
2. VIEW the contact sheets       → out/<handle>/sheets/
3. Read the hook frames          → out/<handle>/hooks/<reel>/
4. Score all five parameters     → references/scoring_rubric.md
5. Shortlist 2-3 + write praise  → agents/shortlist_and_praise.md
6. Pair a campaign reference reel→ agents/campaign_intake.md, then moxie_reference_library.md
7. Write the brief               → agents/brief_writer.md
```

**The machine score covers Pacing and Lighting only.** Background, Hook and
Outfit need eyes on the contact sheet. A reel can score 10/10 and open with "hi
guys," which is an automatic fail.

---

## The pipeline

Five stages. Run in order — each constrains the next.

| Stage | What happens | Agent |
|---|---|---|
| **0. Campaign** | Read the campaign brief doc and its reference reels. Sets the scoring bands and the pairing library for everything after. Run once per campaign. | `agents/campaign_intake.md` |
| **1. Intake** | Run `analyze_creator.py`. Generate contact sheets, hook frames, pacing and lighting per reel. | — |
| **2. Score** | Score all 12 reels on the five parameters. | `agents/reel_analyst.md` |
| **3. Shortlist** | Pick the best 2–3. Write specific praise per parameter. | `agents/shortlist_and_praise.md` |
| **4. Match** | Pair each shortlisted reel with the closest **campaign** reference reel; house library only as fallback. | `agents/campaign_intake.md` |
| **5. Brief** | Produce the creator-facing collab brief. | `agents/brief_writer.md` |

For a batch of creators, run `agents/orchestrator.md` — it handles roster
balance and stops fifteen briefs converging on one film.

After footage comes back, score it with `agents/qa_critic.md`.

### Two documents come out of this, not one

**Internal scorecard** — all 12 reels, numeric scores, rejection reasons, risk
flags. Never sent to the creator.

**Creator-facing collab brief** — the 2–3 shortlisted reels with warm specific
praise, the paired Moxie reference, and the shoot brief. Contains no scores and
no criticism of their other reels. A creator who reads "your reel #7 scored 2/5
on lighting" disengages; a creator who reads "the way you used the doorway light
in your Goa reel is exactly what we want" turns up ready.

---

## The five parameters

These are the scoring dimensions. Full rubric with 1–5 anchors in
`references/scoring_rubric.md`.

### 1. Background

The question is not "does she have a nice bathroom." It is **does the frame
behind her have depth, texture and a story.**

Five archetypes: soft wall with shallow depth · lived-in home with a doorway ·
outdoor and travel · workplace and craft · tight application framing. Detail in
`references/backgrounds_and_lighting.md`.

- Never a blank white wall. Every reference frame has colour, texture, or a
  receding plane. Featureless walls read as a content corner.
- The background must lose to the hair. Wall value sits clearly lighter or
  darker than her hair so the silhouette and clump edges read.
- One accent colour maximum, never neon yellow. Yellow belongs to the product.
- One depth cue present: doorway, corridor, window, mirror, receding counter.
- The background should say something true about her. This is narrative work,
  not decoration.
- No propping. No visible light stands, no styled product shelf, no fairy lights.

**Do not default to a bathroom.** It was over-represented in the reference set
because it was convenient, not because it was correct.

### 2. Lighting

Measured across all 15 reference films:

| Metric | Observed range | Target |
|---|---|---|
| Mean brightness (luma 0–255) | 106–157 | **115–135** |
| Warmth (red/blue ratio) | 1.17–1.68 | **1.20–1.35** |
| Saturation | 0.23–0.46 | **0.25–0.33** |

**Every reference film is warm. Not one sits neutral or cool.** Anything under
1.15 warmth is off-brand however good the framing — this is the single fastest
disqualifier when screening a creator's back catalogue.

- One big soft source at roughly 45° front-side. Window is the default.
  Catchlights window-shaped, never ring donuts.
- **Hair needs a second source from behind or the side.** Highest-leverage note
  in this document. Flat frontal light flattens waves into a dark mass;
  backlight is what makes a clump look like a clump. When screening a creator,
  finding even one shot in her back catalogue with light through her hair is a
  strong positive signal — it is rare.
- Mid-key. Nothing blown out, nothing moody. Skin holds texture.
- The reveal is the brightest shot in the film.
- Wet-application shots run about a third of a stop under.
- Overhead-only light is a fail state — it kills the eyes and flattens the
  crown, exactly where wave definition lives.

### 3. Pacing

House average is roughly **one cut per second**. Twelve of fifteen reference
films sit between 0.7s and 1.5s average shot length. Above 2s reads slow.

Length is inversely proportional to speed — the 14–18s films cut two to three
times faster than the 60s narratives.

Rhythm follows the arc rather than staying flat:

| Section | Timing | Shot length |
|---|---|---|
| Hook | 0–3s | 0.6–1.2s, 2–3 cuts before the third second |
| Backstory | 3–15s | 2–3s, slowest part, let the emotion sit |
| Framework reveal | 15–22s | 1.5–2s, the card gets a full beat |
| Application | 22–40s | **0.5–1.0s**, fastest section |
| Air-dry transition | — | one hard cut |
| Reveal | last 8s | **2–4s**, slow motion on hair movement |
| End card | last 1–2s | held static |

A film at a constant 1.5s hits the average and still feels wrong. The rhythm
must accelerate into the application and brake into the reveal.

Captions change every 1.5–2s regardless of picture cuts — that is what stops the
backstory dragging. Slow motion is for hair movement at the reveal only;
speed-up for application montages only; never both. Hard cuts and match cuts
only, no swipes or glitch transitions.

Measure with `scripts/measure_pacing.py`. Read the jump-cut-inclusive figure —
hard-cut detection alone reports these films as far slower than they feel.

### 4. Hook

**Judge the creator's own hooks against Moxie's hook patterns. Do not go
researching general hook theory.** The question is narrow: does the way this
person already opens a video rhyme with the way Moxie films open?

Moxie hooks share five mechanics:

1. **Open mid-thought.** No greeting, no self-introduction, no statement of what
   the video contains. Every one of the 15 reference films starts as though you
   walked in on a conversation.
2. **First person with a personal stake.** The hook is about her, not about the
   product or the viewer's problem in the abstract.
3. **Movement in frame within the first second.** A hand entering, a turn, a
   whip pan. Never opens static.
4. **Caption on screen from frame one**, short — typically under eight words
   visible at a time.
5. **Tension, not summary.** A contradiction, a wager, a grievance, or a flat
   assertion that demands to be disproved.

The seven hook patterns observed, with examples and the full creator-fit scoring
method, are in `references/hook_library.md`. Read it before scoring hooks.

**Screening shortcut:** pull the first three seconds of a creator's 12 reels
(`analyze_creator.py` writes these to `out/hooks/`). If more than a couple open
with a greeting, a face held static, or an announcement of what's coming, her
hook instinct is trained on a different format and the brief needs to address it
explicitly rather than assume it.

### 5. Outfit

In a hair film the outfit is the backdrop for the hair, so it is ranked, not
noted. Apply in order — earlier rules beat later ones.

1. **Contrast against the hair.** Mid-to-light solids so dark hair reads as a
   distinct silhouette. Dark-on-dark is the most common weak frame in the set.
2. **Neckline exposes collarbone and shoulder.** Scoop, halter, boat, tank,
   off-shoulder, open robe. High collars, hoods, turtlenecks and scarves are
   disqualifying — the hair vanishes into fabric exactly where the waves are best.
3. **Solid over print.** Prints work only as robes at frame periphery, never in
   a close-up talking head.
4. **Never wear neon yellow.** The tube must be the only saturated object in
   frame. The whole desaturated palette exists to let the packaging pop.
5. **Sleeveless or pushed-up sleeves for application.** Forearms in frame read
   as actually doing it.
6. **Change outfit between the before and the reveal.** Signals time has passed
   without a caption and makes the payoff feel like an occasion.
7. **Matte fabrics under hard light; satin only in soft light.**
8. **For workplace films, wear the uniform.** Chef whites, studio sweats, office
   tee. The uniform is the credibility — do not style it up.

Disqualifiers: statement earrings or necklaces that tangle in hair, hoods,
drawstrings, standing collars, logos larger than the product label,
white-on-white where the reveal happens against a white wall.

---

## The two pillars

Get this right before briefing — it sets length, pacing, and whether an origin
story is needed.

**Pillar 1 — Testimony** (12 of 15 reference films). The wavy-hair identity
narrative. 40–60s. Wound → misdiagnosis → framework → routine → air-dried
reveal. Register: *vindication.*

**Pillar 2 — Stress test** (3 of 15). Hold under pressure. 14–37s. Setup
question → apply → subject it to something punishing → verdict to camera.
Faster, funnier, no origin wound required. Occupation supplies both the location
and the test.

A film trying to be both loses the emotional beat of the first and the joke of
the second.

---

## Narrative and tone

**Pillar 1 spine:** the wound → the misdiagnosis → the framework (Moxie Wavy
Theory / Wavy Hair Index) → the routine → the payoff → send this to a friend.

The framework does the heavy lifting. It converts an ad into a *diagnosis* —
creators treat it as knowledge they were denied, not a marketing asset. That is
why the films don't read as paid. The moment it is delivered as a slogan, the
film becomes an ad.

**Tone is:** confessional, warm, funny, slightly ranty, educational without
condescension, sisterly.

**Tone is not:** clinical, dermatologist-coded, aspirational-luxury, scripted,
urgency-driven.

**Signature register:** *vindication.* Not "look how pretty I am" but **"I was
right, and nobody told me."**

Captions are burned in, always, styled per creator — yellow handwritten script,
lowercase serif, clean white sans, Hinglish. Do not impose one caption style
across a roster; the variation is load-bearing.

---

## Running at roster scale

At 1000+ creators the binding constraint is attention budget, not judgement.
12,000 reels is not watchable. The pipeline is a funnel:

```
12,000 reels    → machine pass   (ffmpeg + numpy, no model, ~8.3s/reel/core)
1000 creators   → triage gate    (AUTO-REJECT / BORDERLINE / REVIEW)
~600 creators   → vision pass    (4 contact sheets each, not 12)
~150 creators   → shortlist + praise
target roster   → briefs
```

`batch_run.py` does the first two stages and emits `review_queue.md` — only the
creators worth opening. On 16 cores, 12,000 reels measures in under two hours.
Always pass `--resume`; a run that long will be interrupted.

Three things matter more at this scale than at ten creators:

- **Determinism.** The machine half is reproducible; pin the ffmpeg version. The
  vision half drifts — keep a calibration set of pre-scored reels and re-score it
  at the start of every batch.
- **Sample-audit the AUTO-REJECTs.** Pull 5% and eyeball them. If good creators
  are being gated out, `--min-machine` is too high. This is the cheapest quality
  check available.
- **Track background-archetype spread as a headline metric.** The real risk at
  roster scale is not bad scoring, it is 200 briefs that all specify a pastel
  wall and window light. Run the variety gate before delivery.

Full playbook, throughput table, storage and cost levers in
`references/scale_operations.md`.

---

## Failure modes

Ways output drifts off-brand while every individual rule is followed:

- **Template convergence.** Twelve briefs producing twelve identical films. The
  archetypes exist to prevent this — check roster spread before shipping.
- **Bathroom reflex.** Defaulting to a shower because the reference set did.
- **Polish creep.** Studio lighting, styled sets and colour grading all make
  testimony less believable. The work trades polish for credibility on purpose.
- **Framework as tagline.** If the Wavy Theory is delivered as a slogan rather
  than a personal revelation, the whole conceit collapses.
- **Flat cutting.** Constant 1.5s hits the average and still feels wrong.
- **Yellow contamination.** Yellow in wardrobe or set steals the product's only
  visual privilege.
- **Scoring the creator to her face.** Numbers are internal. Praise is external.
- **Scoring against the house average instead of the campaign.** The campaign
  brief sets the bands. Skipping stage 0 produces a shortlist that is defensible
  in general and wrong in particular.
- **Letting the machine score pick the shortlist.** It sees two parameters of
  five.
- **Rubric collapse at scale.** If most scores land on 3, the rubric is being
  applied as a shrug. Re-anchor every ~50 creators.
- **Briefing a creator out of her own strengths.** If the shortlist praises her
  doorway light and the brief then specifies a plain wall, you have wasted the
  shortlist.

---

## Reference files

Read when the task needs the detail; don't load them all up front.

- `references/scale_operations.md` — the 1000+ creator playbook: funnel, throughput, drift control, cost levers
- `references/scoring_rubric.md` — 1–5 anchors for all five parameters
- `references/hook_library.md` — the seven hook patterns, creator hook-fit scoring
- `references/moxie_reference_library.md` — the 15 films indexed for pairing
- `references/measured_benchmarks.md` — per-film pacing, luma, warmth, saturation
- `references/backgrounds_and_lighting.md` — five background archetypes with lighting per archetype
- `references/archetypes.md` — the nine creator archetypes
- `references/product_vocabulary.md` — SKUs, claims language, technique dialect
- `references/brief_template.md` — creator-facing collab brief template

## Agent files

- `agents/campaign_intake.md` — reading the campaign brief; sets bands and the reference pairing library
- `agents/orchestrator.md` — multi-creator batches, roster balance, variety gates
- `agents/reel_analyst.md` — scoring 12 reels on five parameters
- `agents/shortlist_and_praise.md` — picking 2–3 and writing the praise
- `agents/brief_writer.md` — producing the creator-facing collab brief
- `agents/qa_critic.md` — scoring the collab reel when it comes back

## Scripts

- `scripts/batch_run.py` — roster-scale runner: parallel, resumable, emits the review queue
- `scripts/analyze_creator.py` — one creator: measure, triage, contact sheets, hook frames
- `scripts/measure_pacing.py` — cut detection and rhythm verdict for a single film
- `scripts/measure_lighting.py` — luma, warmth and saturation verdict for a single film
