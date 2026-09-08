# Campaign Intake

**Runs first, before any creator is touched.** The campaign brief is an input to
this pipeline, not something the pipeline invents. Everything downstream —
which reels get shortlisted, which Moxie reference gets paired, what the collab
brief asks for — is conditioned on what the campaign says.

Skipping this stage means scoring creators against the house average instead of
against the campaign, which produces a shortlist that is defensible in general
and wrong in particular.

## Inputs you should expect

| Input | Form | If missing |
|---|---|---|
| Campaign brief | .md / .docx / .pdf | Stop and ask. Do not proceed on assumption. |
| Campaign reference reels | folder of .mp4, or links | Fall back to `references/moxie_reference_library.md` defaults and say so |
| Creator roster | folders of downloaded reels | Stop and ask |
| Target creator count | number | Assume the roster size |

## Step 1 — Read the brief and extract the campaign profile

Pull these out explicitly and write them down. If the brief doesn't state one,
mark it `UNSPECIFIED` rather than guessing — an unspecified field is a question
for the user, not a gap to fill.

```yaml
campaign: <name>
pillar: 1 Testimony | 2 Stress test | mixed
products: [SKUs in play]
hero_claim: <the one thing the campaign must land>
length_target: <seconds>
archetype_mix: <if specified>
must_have: <non-negotiables — a location type, a demographic, a season>
must_avoid: <exclusions>
creator_count: <n>
deadline: <date>
```

## Step 2 — Measure the campaign's own reference reels

Run the reference reels the campaign supplied through the same measurement the
creators get:

```bash
python scripts/batch_run.py ./campaign_refs_as_folders/ --outdir ./campaign_calibration
```

This gives the campaign's actual pacing and lighting band, which may differ from
the house average. A campaign built on the stress-test films will sit near 0.7s
average shot; one built on the narrative films sits near 1.2s.

**Use the campaign band, not the house band, for scoring.** Write it into the
campaign profile:

```yaml
campaign_pace_band: <lo>-<hi>s      # from the campaign's own refs
campaign_luma_band: <lo>-<hi>
campaign_warmth_band: <lo>-<hi>
```

If the campaign refs measure outside the house band, that is worth flagging to
the user once — it may be intentional, or it may be that someone picked
reference reels that don't represent the brand. Ask; don't silently override.

## Step 3 — Build the campaign reference index

For each campaign reference reel, record what it is the exemplar *for*, using
the parameter vocabulary. This is what stage 4 pairs against.

```yaml
refs:
  - file: <name>
    exemplar_for: [background | lighting | pacing | hook | outfit | tone]
    pillar: 1 | 2
    archetype: <if identifiable>
    hook_pattern: <one of the seven>
    notes: <what a creator should look at, with a timestamp>
```

The `notes` field earns its place. A creator sent a bare link watches at half
attention. "Watch 0:38–0:44 — the light is coming through her hair from the
window behind" gets copied.

## Step 4 — Set the gate

Translate the campaign into machine thresholds for `batch_run.py`:

- `--min-machine` — raise it above 5 for a competitive campaign with more
  applicants than slots; lower it to 4 when the roster is thin and you need
  volume through the gate.
- `--review-top` — how many contact sheets per creator. This is your vision
  budget. 4 is the default; 3 at very large scale.

Record what you set and why. At 1000 creators the gate settings determine the
shape of the whole shortlist, and six months later nobody will remember why the
cut fell where it did.

## Step 5 — Hand off

Emit `campaign_profile.yaml` into the run directory. Every downstream agent
reads it. A creator scored under one campaign profile cannot be compared with a
creator scored under another — if the campaign changes, the scores are stale.

## What changes downstream

| Stage | What the campaign profile changes |
|---|---|
| Scoring | Pacing and lighting bands come from the campaign refs, not the house defaults |
| Shortlist | Reels are picked for what *this* campaign needs, not for general quality |
| Matching | Pairs against campaign refs first; house library only as fallback |
| Brief | Products, claim, length and beats all come from the brief doc |

## The one thing not to do

Do not let the campaign brief override the taste standard's hard rules. A
campaign asking for cool-toned footage, straightened after-shots, or yellow
wardrobe is asking for something no reference film does. Flag it, explain what
the reference set shows, and let the user decide. The campaign sets the target;
it does not repeal the physics of how wavy hair photographs.
