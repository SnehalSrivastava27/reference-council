# QA Critic

Scores a finished or rough cut against the standard. Measure first, judge
second — the numbers catch things the eye rationalises, especially pacing, which
almost everyone misjudges on their own edit.

## Step 1 — Measure

```bash
python scripts/measure_pacing.py <video.mp4>
python scripts/measure_lighting.py <video.mp4>
```

Record the actual figures in the scorecard. Do not paraphrase them as "good
pacing" — the numbers are the point.

## Step 2 — Score each dimension

Score 1-5. A 3 means it meets the standard; 4 and 5 are reserved for work that
adds something the reference set does not already have.

| Parameter | Ask |
|---|---|
| **Pillar clarity** | Is this clearly Testimony or Stress test, and does it stay there? |
| **Hook** | Movement in frame within the first second, 2-3 cuts by 3s, opens mid-thought with no greeting? |
| **Narrative** | Wound, misdiagnosis, framework, routine, payoff, CTA — all present and in order? |
| **Framework handling** | Is the Wavy Theory a revelation or a tagline? Tagline is an automatic fail. |
| **Background** | Depth, texture, a story, hair silhouette reads, no yellow, nothing propped? |
| **Lighting** | Warmth 1.20-1.35, luma 115-135, and crucially — is there light through or across the hair at the reveal? |
| **Pacing** | Measured average 0.8-1.5s, and does the rhythm accelerate into application and brake into reveal? |
| **Wardrobe** | Contrast, open neckline, solid, not yellow, outfit change at reveal? |
| **Tone** | Vindication rather than pride. Confessional, not presenter-voice. |
| **Distinctiveness** | Could this be any creator's film, or only hers? |

## Step 3 — Automatic fails

Any of these sends it back regardless of the total score:

- The "after" shot has straightened hair
- The Wavy Theory delivered as a slogan or product benefit
- Neon yellow in the wardrobe or set dressing
- Ring-light catchlight as the key source
- Opens with a greeting or a statement of what the video contains
- Flat frontal light at the reveal with no hair separation
- A visible light stand, styled product shelf or fairy lights
- Measured warmth below 1.15

## Step 4 — Write fixes, not notes

Every issue gets a specific, executable fix. "Feels slow" is useless. "Average
shot 2.4s; the application section from 0:24-0:41 is running 2s cuts, take it to
sub-second with jump cuts on the scrunch footage" is actionable.

Order fixes by cost. A caption timing change is free; a reshoot is not. Lead
with what can be fixed in the edit, then what needs a pickup, then what would
need a reshoot.

## Output format

```markdown
# QA — [creator] — [film]

## Measured
Avg shot length: Xs (target 0.8-1.5)  |  cuts/min: X
Luma: X (target 115-135) | Warmth: X (target 1.20-1.35) | Sat: X

## Scores
| Dimension | Score | Note |

**Total: X/50**

## Automatic fails
None, or list them

## Fixes
### In the edit
### Needs a pickup
### Would need a reshoot

## What works
Name it specifically — this is how the standard evolves
```
