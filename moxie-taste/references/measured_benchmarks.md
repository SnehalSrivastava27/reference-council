# Measured Benchmarks — 15 reference films

All figures measured directly from the source files. Pacing via ffmpeg scene
detection at two thresholds; lighting via per-frame RGB sampling every 3
seconds. Regenerate for any new film with `scripts/measure_pacing.py` and
`scripts/measure_lighting.py`.

## Pacing

Sorted fastest to slowest. "Avg shot incl. jump" is the figure to judge against —
hard-cut detection alone reports these films as far slower than they feel.

| Film | Pillar | Length | Avg shot (hard) | Avg shot (incl. jump) |
|---|---|---|---|---|
| `Video-60764` kitchen | 2 | 14.1s | 1.2s | **0.7s** fastest |
| `Video-65320` dance studio | 2 | 18.1s | 1.6s | 1.0s |
| `shrijajhinkwan` | 1 | 66.7s | 2.6s | 1.0s |
| `aashiadani` | 1 | 40.7s | 2.0s | 1.0s |
| `globalbeautyfinds` | 1 | 37.7s | 1.2s | 1.1s |
| `theriyakohli` | 1 | 27.5s | 1.5s | 1.1s |
| `eshnakutty` | 1 | 51.2s | 1.7s | 1.1s |
| `nutellaonella` | 1 | 32.5s | 1.7s | 1.2s |
| `vibhasree_` | 1 | 42.1s | 2.6s | 1.2s |
| `taneesho` | 1 | 57.3s | 2.9s | 1.4s |
| `asmitapathik` | 1 | 55.6s | 3.7s | 1.4s |
| `srish_teee` | 1 | 44.4s | 1.9s | 1.5s |
| `Video-47055` office | 2 | 37.2s | 3.1s | 1.7s |
| `urshaynesss` | 1 | 60.6s | 3.4s | 1.8s |
| `ahillyeah` | 1 | 59.8s | 7.5s | **2.6s** slowest |

**Read:** 12 of 15 sit between 0.7s and 1.5s. The two outliers above 1.8s are
heavy talking-head films — `ahillyeah` holds attention on story alone and is the
exception that proves the rule, not a model to copy.

## Lighting and colour

| Film | Luma | Luma SD | Warmth (R/B) | Saturation |
|---|---|---|---|---|
| `nutellaonella` | 156.9 | 44.3 | 1.28 | 0.29 |
| `shrijajhinkwan` | 135.0 | 14.3 | 1.29 | 0.25 |
| `Video-60764` | 133.9 | 39.8 | 1.28 | 0.30 |
| `Video-65320` | 133.7 | 42.3 | 1.35 | 0.43 |
| `globalbeautyfinds` | 128.2 | 8.8 | 1.26 | 0.33 |
| `aashiadani` | 126.2 | 4.7 | 1.26 | 0.27 |
| `Video-47055` | 125.1 | 18.8 | 1.17 | 0.29 |
| `eshnakutty` | 121.4 | 20.5 | 1.68 | 0.46 |
| `taneesho` | 121.2 | 13.0 | 1.25 | 0.29 |
| `theriyakohli` | 120.0 | 28.1 | 1.18 | 0.26 |
| `srish_teee` | 119.8 | 10.0 | 1.28 | 0.29 |
| `ahillyeah` | 113.7 | 6.1 | 1.25 | 0.23 |
| `asmitapathik` | 113.5 | 9.9 | 1.34 | 0.30 |
| `urshaynesss` | 110.7 | 11.3 | 1.37 | 0.30 |
| `vibhasree_` | 106.0 | 11.2 | 1.25 | 0.31 |

**Read:**

- **Warmth is the tell.** Every film measures above 1.15. No cool-toned example
  exists in the set. Anything under 1.15 is off-brand however good the framing.
- Nine of fifteen cluster at 1.25–1.29. That is the house neutral.
- `eshnakutty` at 1.68 warmth and 0.46 saturation is the tropical-exterior
  outlier — acceptable because the location justifies it.
- **Luma SD separates single-location from travelling films.** Under 15 means one
  room. Above 25 means the film genuinely moves, which is legitimate but must be
  motivated by the story rather than by restlessness.
- `vibhasree_` at 106 luma is the darkest and shows the cost — dark hair against
  a dark wooden door, silhouette barely reading. Useful as a negative example.
