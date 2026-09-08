# Hook Library

The hook is the fifth scoring parameter and the one most likely to be judged
badly, because it is tempting to reach for general short-form hook advice.
**Don't.** The question here is narrow and comparative: *does the way this
creator already opens a video rhyme with the way Moxie films open?*

A creator with a strong hook instinct trained on a different format (unboxing,
GRWM, trend audio) will produce a technically good hook that is wrong for Moxie.
That is a briefing problem, not a rejection — but you have to spot it.

---

## The five mechanics every Moxie hook shares

Score each of a creator's reels against these. They are observable in the first
three seconds, which `analyze_creator.py` extracts to `out/hooks/<reel>/`.

| # | Mechanic | How to check |
|---|---|---|
| 1 | **Opens mid-thought** | No greeting, no name, no "in this video". Feels like walking in on a conversation already happening. |
| 2 | **First person, personal stake** | The hook is about her. Not about the product, not about the viewer's problem stated abstractly. |
| 3 | **Movement in the first second** | A hand entering, a turn, a whip pan, hair being lifted. Never a static held face. |
| 4 | **Caption on screen from frame one** | Short — typically under eight words visible at once. |
| 5 | **Tension, not summary** | A contradiction, wager, grievance or flat assertion. Never a description of what's coming. |

A reel hitting 4–5 of these is a strong hook by Moxie's standard even if the
topic is unrelated to hair.

---

## The seven hook patterns

Observed across the 15 reference films. Use these to classify a creator's
existing hooks — the pattern she reaches for naturally tells you which Moxie
pillar and archetype she fits.

### 1. Contradiction / pre-emptive dismissal
Sets up the objection so she can demolish it.
> *"It's just a wavy routine… kya hi farak padega?"* — `aashiadani`

Signals: Routine Demonstrator or Skeptic Convert. Works in Hinglish especially
well, because the dismissal reads as something a family member would actually say.

### 2. Grievance list
Opens on accumulated irritation. Highest emotional yield.
> *"Growing up with wavy hair is crazy because here's some things I've heard…"* — `ahillyeah`

Signals: Identity Storyteller. Needs the slowest pacing of any hook type — this
one earns its 2–3s shots.

### 3. Wager / stakes
States a test with a real chance of failure.
> *"Will my slick back survive 45 minutes of Bhangra?"* — `Video-65320`

Signals: Pillar 2, The Professional. The best-performing hook type for short
films because the viewer stays to find out the answer.

### 4. Flat assertion
A claim delivered as fact, daring disagreement.
> *"IT IS POSSIBLE."* — `srish_teee`

Signals: Skeptic Convert. Needs strong caption typography to carry it —
the words are doing all the work.

### 5. Direct address / demand
Speaks at the viewer or at an absent antagonist.
> *"Tell me that there's…"* — `nutellaonella`

Signals: rant register. Pairs with fast cutting and a slightly unhinged delivery.

### 6. Binary question
Poses a two-way split the video resolves.
> *"Wavy or curly?"* — `vibhasree_`

Signals: Educator or Makeover Host. Sets up a teaching structure naturally.

### 7. Instructional label
A title card functioning as the hook.
> *"HOW TO"* — `globalbeautyfinds` · *"the recipe for the perfect slick back"* — `Video-60764`

Signals: Educator, The Professional. The weakest hook type on its own — it needs
mechanic #3 (movement) doing heavy lifting or it reads as a tutorial thumbnail.

---

## Anti-patterns

If a creator's back catalogue is built on these, her hook instinct is trained
elsewhere. Not disqualifying, but the brief must address it explicitly.

- **Greeting opens.** "Hi guys", "Hey everyone", "Welcome back."
- **Self-introduction.** Naming herself before saying anything.
- **Content announcement.** "Today I'm going to show you five tips for…"
- **Static held face.** Three seconds of a person waiting for the audio to start.
- **Trend-audio dependency.** The hook is the sound, not anything she said. These
  do not survive being reused as a Moxie collab, because the audio won't be there.
- **Product-first.** Leading with the tube before establishing why anyone should care.
- **Delayed caption.** Nothing on screen for the first two seconds. On a muted
  autoplay feed this is a dead hook regardless of what she's saying.

---

## Scoring a creator's hook fit

Pull the first three seconds of all 12 reels. For each, record:

| Field | Values |
|---|---|
| Pattern | one of the seven, or "anti-pattern: X" |
| Mechanics hit | 0–5 |
| On-screen words at 0–1s | count |
| Opens mid-thought | Y/N |
| Movement in first second | Y/N |

Then compute across the 12:

- **Mid-thought rate** — % opening without greeting or announcement.
  Above 70% is a natural fit. Below 40% needs explicit briefing.
- **Caption-at-zero rate** — % with text on screen in the first second.
  Below 50% is the most common and most fixable gap.
- **Pattern spread** — how many of the seven she uses. One pattern used twelve
  times is a creator on autopilot; three to five is range.
- **Dominant pattern** — feeds the archetype assignment and pillar routing.

### Verdict bands

**Natural fit.** 70%+ mid-thought, dominant pattern is one of the seven, movement
in most opens. Brief can simply say "open the way you opened your [reel name]".

**Fixable.** Good instincts but caption timing lags, or she leans on one pattern.
Brief gives her two specific hook options written in her own voice, referencing
which of her reels already did it.

**Needs rebuilding.** Majority anti-patterns, greeting-led, trend-audio dependent.
Brief must supply the hook verbatim and explain why — do not assume she'll
improvise into the right register. Flag as a risk in the internal scorecard.

---

## Writing a hook for the brief

Write it in *her* cadence, using the pattern she already reaches for. Never hand
a Grievance-list creator a Wager hook because the campaign wants one — she will
deliver it flat.

Reference her own reel by name in the brief:

> *"Open it the way you opened your Goa reel — mid-sentence, hand already in your
> hair, caption up before you've finished the first word. That reel is the reason
> we reached out."*

That sentence does more than a page of hook theory, because it points at proof
she already owns.
