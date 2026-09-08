# Scoring Rubric — the five parameters

Score every reel 1–5 on each parameter. Total out of 25.

**Internal only.** These numbers never appear in a creator-facing document.

Two parameters are machine-measurable (Pacing, Lighting); three require looking
at the contact sheet (Background, Hook, Outfit). `analyze_creator.py` produces a
machine score out of 10 that ranks review order — it cannot pick the shortlist.

---

## 1. Background

| Score | Anchor |
|---|---|
| 5 | Depth cue present, colour or texture, hair silhouette separates cleanly, and the location says something true about her |
| 4 | Depth and separation good, location generic |
| 3 | Readable but flat — one plane, no depth cue, silhouette holds |
| 2 | Hair loses its edge against the wall, or visible propping / content-corner setup |
| 1 | Blank wall, or dark hair against dark background with no separation |

**Auto-cap at 2:** visible light stand, styled product shelf, fairy lights, or
neon yellow in the set dressing.

## 2. Lighting

| Score | Anchor | Measured |
|---|---|---|
| 5 | Warm, mid-key, and light visibly passing through or across the hair | warmth 1.20–1.35, luma 115–135 |
| 4 | Warm and well exposed, no hair separation | warmth 1.20–1.35, luma 110–140 |
| 3 | Acceptable but flat frontal, or slightly under | warmth 1.15–1.20 |
| 2 | Ring-lit, overhead-only, or notably under | luma under 108 |
| 1 | Cool-toned | warmth under 1.15 |

**The hair-light question is the whole parameter.** A creator with even one reel
showing backlight through hair scores a 5 there and should be told so — it is
rare and it is the thing that makes wave definition read.

## 3. Pacing

| Score | Anchor | Measured avg shot |
|---|---|---|
| 5 | On-pace *and* rhythm accelerates into the demo, brakes into the payoff | 0.8–1.5s |
| 4 | On-pace but flat rhythm throughout | 0.8–1.5s |
| 3 | Slightly slow but holding attention | 1.5–2.0s |
| 2 | Slow, or fast with no variation | 2.0–2.6s |
| 1 | Static talking head | above 2.6s |

Use the jump-cut-inclusive figure. Hard-cut detection alone reports these films
as far slower than they feel.

## 4. Hook

| Score | Anchor |
|---|---|
| 5 | 4–5 mechanics hit, one of the seven Moxie patterns, movement and caption from frame one |
| 4 | 3–4 mechanics, recognisable pattern, minor caption lag |
| 3 | Opens mid-thought but static, or good energy with delayed caption |
| 2 | Content announcement, or trend-audio dependent |
| 1 | Greeting-led, static held face, nothing on screen for 2s |

Full method in `hook_library.md`.

## 5. Outfit

| Score | Anchor |
|---|---|
| 5 | Solid, contrasts against hair and wall, open neckline, and changes for the payoff |
| 4 | Solid with good contrast and open neckline |
| 3 | Works, but collar or print slightly competes |
| 2 | Dark-on-dark, busy print in close-up, or a neckline that swallows the hair |
| 1 | High collar / hood / scarf, or neon yellow worn |

---

## Reading the totals

| Total /25 | Meaning |
|---|---|
| 21–25 | Shortlist candidate. Reference-grade. |
| 17–20 | Shortlist candidate if it shows something the others don't |
| 13–16 | Solid but unremarkable — do not shortlist, it teaches the creator nothing |
| Below 13 | Not a shortlist reel |

**Shortlist for spread, not just for score.** Three 22s that all demonstrate the
same strength are worse than a 22, a 20 and an 18 that between them show good
background, good hook and good pacing. The shortlist's job is to point at three
different things she already does well.
