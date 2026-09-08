"""brief.py — emit the creator-portal collab-brief JSON straight from Gemini.

The creator portal (creator_portal/src/lib/collab-brief.ts, parseCollabBrief)
consumes ONE per-creator JSON. This module makes the pipeline produce that exact
shape automatically instead of anyone hand-authoring it. The admin flow then
becomes: paste this JSON + attach the reel mp4s.

Split of responsibility (deliberate — see P1.5/P1.6 in the task):
  • Gemini writes the JUDGEMENT — which reels to shortlist, the praise, the film
    idea, the five specs, the products, and a real camera shot list. It is given
    a response_schema so it returns the portal shape directly (no markdown).
  • This module fills the FACTS deterministically — each reel's igUrl + mp4
    filename from reels/<handle>/.manifest.json, and each reference's pairsWith
    string ("your reel #N — <title>") from the pairing the model chose. The model
    never hand-builds a URL or a pairing sentence.

Run `python brief.py --selftest` for the offline check (no key, no network).
"""

import json
import os
import re
from pathlib import Path

from google.genai import types
from google.genai import errors as genai_errors
from tenacity import (retry, retry_if_exception, stop_after_attempt,
                      wait_exponential)

ROOT = Path(__file__).resolve().parent.parent
REELS_ACTOR = "xMc5Ga1oCONPmWJIa"  # same dedicated reels actor DG-API uses

# Real-people reel frames (faces, skin, bodies) routinely trip Gemini's DEFAULT
# safety thresholds, which returns a 200 with an empty candidate and no text —
# the "Gemini did not return JSON" failures seen at scale. This is benign beauty
# content, so turn blocking off for every category.
_SAFETY_OFF = [
    types.SafetySetting(category=c, threshold=types.HarmBlockThreshold.BLOCK_NONE)
    for c in (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    )
]

# ---------------------------------------------------------------------------
# Portal contract, as a Gemini response_schema. This is the SUBSET the model
# produces — igUrl / videoFile / pairsWith are filled by assemble_brief(), NOT
# the model, so they cannot drift. Keys/shape match creator_portal's CollabBrief
# (no `beats`, no `words` — the portal removed them).
# ---------------------------------------------------------------------------
FIVE_THINGS = ("Background", "Lighting", "Pacing", "Hook", "Outfit")

_LOVED = {
    "type": "OBJECT",
    "propertyOrdering": ["label", "time", "note"],
    "properties": {
        "label": {"type": "STRING", "description": "Background / Lighting / Pacing / Hook / Outfit / etc."},
        "time": {"type": "STRING", "description": "timestamp like 0:38, or empty"},
        "note": {"type": "STRING"},
    },
    "required": ["label", "note"],
}

BRIEF_SCHEMA = {
    "type": "OBJECT",
    # Gemini emits keys in this order. Its default is ALPHABETICAL, which made the
    # model write fiveThings/film before it had chosen the reels they build on.
    "propertyOrdering": ["reels", "refs", "whyYou", "film", "fiveThings", "products", "mustHaveShots"],
    "properties": {
        "whyYou": {"type": "STRING", "description": "two warm sentences, naming one of her reels"},
        "reels": {
            "type": "ARRAY",
            "description": "THREE shortlisted reels, each the best example of a different parameter; two only when no third reel deserves it",
            "minItems": 2, "maxItems": 3,
            "items": {
                "type": "OBJECT",
                "propertyOrdering": ["reel", "title", "loved"],
                "properties": {
                    "reel": {"type": "STRING", "description": "the reel's filename stem EXACTLY as in creator_analysis.json, e.g. 06_Da2qlkpyJqG"},
                    "title": {"type": "STRING", "description": "short descriptor, e.g. 'B.Ed Student GRWM'"},
                    "loved": {"type": "ARRAY", "items": _LOVED},
                },
                "required": ["reel", "title", "loved"],
            },
        },
        "refs": {
            "type": "ARRAY",
            "description": "one Moxie reference reel per shortlisted reel, max 3",
            "minItems": 1, "maxItems": 3,
            "items": {
                "type": "OBJECT",
                "propertyOrdering": ["libraryHandle", "pairsWithReel", "share"],
                "properties": {
                    "libraryHandle": {"type": "STRING", "description": "a handle from moxie_reference_library.md"},
                    "pairsWithReel": {"type": "STRING", "description": "the filename stem of the creator reel this pairs with"},
                    "share": {"type": "STRING", "description": "one sentence naming the overlap (the strength praised, not the topic)"},
                },
                "required": ["libraryHandle", "pairsWithReel", "share"],
            },
        },
        "film": {
            "type": "OBJECT",
            "propertyOrdering": ["idea", "format", "length"],
            "properties": {
                "idea": {"type": "STRING", "description": "the Core Message to Land, one line"},
                "format": {"type": "STRING", "description": "e.g. 'Reel · 9:16'"},
                "length": {"type": "STRING", "description": "e.g. '45-55 sec'"},
            },
            "required": ["idea", "format", "length"],
        },
        "fiveThings": {
            "type": "ARRAY",
            "description": "exactly five, in this order: Background, Lighting, Pacing, Hook, Outfit",
            "minItems": 5, "maxItems": 5,
            "items": {
                "type": "OBJECT",
                "propertyOrdering": ["label", "items"],
                "properties": {
                    "label": {"type": "STRING", "enum": list(FIVE_THINGS)},
                    "items": {"type": "ARRAY", "minItems": 1, "items": {"type": "STRING"}},
                },
                "required": ["label", "items"],
            },
        },
        "products": {"type": "ARRAY", "items": {"type": "STRING"}},
        "mustHaveShots": {
            "type": "ARRAY",
            "description": "concrete CAMERA SHOTS to capture (framing + subject + action), not narrative theory",
            "items": {"type": "STRING"},
        },
    },
    "required": ["reels", "refs", "film", "fiveThings", "products", "mustHaveShots"],
}

BRIEF_TASK = """You are executing the Moxie Taste creator-onboarding skill. The
reference/agent documents above are your standard — follow shortlist_and_praise.md
and brief_writer.md exactly.

You are given the machine measurements (creator_analysis.json) and, labelled by
filename, contact sheets (24 tiled frames per reel) and hook frames. Score
Background, Hook and Outfit from the images; Pacing and Lighting are measured.

Return a single JSON object that is the creator-facing collab brief, matching the
provided schema. It is the artifact the creator films against — no scores, no
criticism, nothing that does not help her shoot. Specifically:

- reels: shortlist THREE reels, each the best example of a DIFFERENT strength.
  You have a contact sheet for every reel — judge all of them, not just the ones
  the machine score ranks highest. Fall back to two only when no third reel
  reaches 4 on any parameter; never pad, but never default to two either. Set
  each reel's "reel" field to that reel's filename stem EXACTLY as it appears in
  creator_analysis.json (e.g. 06_Da2qlkpyJqG) — do NOT invent a URL or a
  filename; the pipeline fills those. Each reel gets warm, specific praise in
  "loved": one entry per parameter with a timestamp and why it matters.
- Background is judged indoors-first. The collab is shot in her home, so an
  indoor frame with a doorway, receding room or textured wall (archetypes 1 and 2
  in backgrounds_and_lighting.md) outranks an outdoor frame with equal
  separation. Shortlist an outdoor reel for Background only when no indoor reel
  reaches 4. A COOL / underlit lighting flag on an indoor reel is not a reason to
  skip it — praise its background and fix the light in the Lighting spec.
- Outfit is mandatory. Praise it in "loved" on at least one reel, naming the
  garment, colour and neckline you can see in the frames.
- refs: for each shortlisted reel choose ONE Moxie reference from
  moxie_reference_library.md. Set "libraryHandle" to its handle, "pairsWithReel"
  to the filename stem of the creator reel it pairs with, and "share" to one
  sentence naming the overlap — match on the strength you praised, not the topic.
  Maximum three.
- film.idea: the Core Message to Land, in one line.
- fiveThings: five entries, in order and labelled exactly Background, Lighting,
  Pacing, Hook, Outfit, each a specification tailored to her — per brief_writer.md:
  Background = two rooms she already filmed in, named from her reels, one brighter
  for the reveal (exteriors only if the campaign brief asks for them); Lighting =
  where the hair light comes from and the time of day; Pacing = a number; Hook =
  written out; Outfit = Look 1 (routine) and Look 2 (reveal) as colours, necklines
  and fabrics, then two or three things to avoid against the named backgrounds.
- products: the Moxie SKUs / items she will use.
- mustHaveShots: a real shot list — the specific CAMERA SHOTS she must capture,
  each as framing + subject + action (e.g. "Macro close-up of the scalp parting —
  flakes visible at the start, clean at the end"). NOT narrative beats, NOT theory.

Do NOT output any "beats" or "words" field anywhere.
"""


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested by --selftest, no key / network needed)
# ---------------------------------------------------------------------------
def norm_handle(h: str) -> str:
    """IG handle, no leading @, and no stray leading underscore (the reels/
    folder for gopikakrishna is `_gopikakrishna` — normalise it here rather than
    depend on the folder being clean)."""
    h = (h or "").strip().lstrip("@").strip()
    return h[1:] if h.startswith("_") else h


def _shortcode(url: str):
    m = re.search(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", url or "")
    return m.group(1) if m else None


def load_manifest(reels_dir) -> dict:
    """shortcode -> mp4 filename, from reels/<handle>/.manifest.json."""
    p = Path(reels_dir) / ".manifest.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _stem(name: str) -> str:
    return name[:-4] if name.lower().endswith(".mp4") else name


def _resolve_reel(reel_name: str, file_to_code: dict):
    """(shortcode, mp4_filename) for a reel the model named. Prefers the manifest;
    falls back to the NN_<shortcode> naming so uploads without a manifest still work."""
    stem = _stem(str(reel_name))
    fname = stem + ".mp4"
    if fname in file_to_code:
        return file_to_code[fname], fname
    sc = stem.split("_", 1)[1] if "_" in stem else stem
    return sc, fname


def reel_igurl(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/" if shortcode else ""


def parse_reference_library(md_text: str) -> dict:
    """Read the moxie_reference_library.md table -> {handle: reel_url}. Uses the
    'Reel URL' column when present (full URL or a bare shortcode); handles without
    one are simply absent, and the caller falls back to the profile URL."""
    table = [
        [c.strip() for c in ln.strip().strip("|").split("|")]
        for ln in md_text.splitlines()
        if ln.strip().startswith("|")
    ]
    if not table:
        return {}
    header = [c.lower() for c in table[0]]
    try:
        hi = header.index("film")
        ui = next(i for i, c in enumerate(header) if "reel url" in c)
    except (ValueError, StopIteration):
        return {}
    out = {}
    for row in table[1:]:
        if len(row) <= max(hi, ui):
            continue
        if set(row[hi]) <= {"-", ":"}:  # separator row
            continue
        handle = norm_handle(row[hi].strip("`"))
        val = row[ui].strip().strip("`")
        if not handle or handle.lower() == "film" or not val or set(val) <= {"-"}:
            continue
        out[handle] = val if val.startswith("http") else reel_igurl(val)
    return out


def assemble_brief(handle, model, manifest, ref_lib, moxie_refs_dir=None) -> dict:
    """The emit code path: model judgement + deterministic facts -> portal JSON."""
    file_to_code = {v: k for k, v in (manifest or {}).items()}
    model_reels = model.get("reels") or []

    reels, stem_index = [], {}
    for i, m in enumerate(model_reels, 1):
        sc, fname = _resolve_reel(m.get("reel", ""), file_to_code)
        stem_index[_stem(str(m.get("reel", "")))] = i
        reels.append({
            "title": m.get("title", ""),
            "igUrl": reel_igurl(sc),
            "videoFile": fname,
            "loved": [
                {"label": l.get("label", ""), "time": l.get("time", ""), "note": l.get("note", "")}
                for l in (m.get("loved") or [])
            ],
        })

    refs = []
    for r in (model.get("refs") or []):
        rh = norm_handle(r.get("libraryHandle", ""))
        i = stem_index.get(_stem(str(r.get("pairsWithReel", ""))))
        pairs_with = f"your reel #{i} — {reels[i - 1]['title']}" if i else ""
        vf = ""
        if moxie_refs_dir and (Path(moxie_refs_dir) / f"{rh}.mp4").exists():
            vf = f"{rh}.mp4"
        refs.append({
            "handle": rh,
            "igUrl": ref_lib.get(rh) or (f"https://www.instagram.com/{rh}/" if rh else ""),
            "share": r.get("share", ""),
            "pairsWith": pairs_with,
            "videoFile": vf,
        })

    film = model.get("film") or {}
    return {
        "handle": norm_handle(handle),
        "whyYou": model.get("whyYou", ""),
        "reels": reels,
        "refs": refs,
        "film": {"idea": film.get("idea", ""), "format": film.get("format", ""),
                 "length": film.get("length", "")},
        "fiveThings": [
            {"label": t.get("label", ""), "items": list(t.get("items") or [])}
            for t in (model.get("fiveThings") or [])
        ],
        "products": list(model.get("products") or []),
        "mustHaveShots": list(model.get("mustHaveShots") or []),
    }


_FORBIDDEN = ("beats", "words")


def _has_forbidden(obj) -> bool:
    if isinstance(obj, dict):
        return any(k in _FORBIDDEN for k in obj) or any(_has_forbidden(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_forbidden(x) for x in obj)
    return False


def validate_brief(b: dict) -> None:
    """Raise ValueError on any contract violation. Raising here makes the retried
    Gemini call try again rather than emitting a broken brief. Mirrors the portal
    parser's expectations + the task's VERIFY assertions."""
    if not isinstance(b, dict):
        raise ValueError("brief is not an object")
    reels = b.get("reels") or []
    if len(reels) < 2:
        raise ValueError(f"only {len(reels)} reel(s) shortlisted — need 2-3")
    for i, r in enumerate(reels):
        if not (r.get("title") and r.get("igUrl") and r.get("videoFile")):
            raise ValueError(f"reel {i} missing title/igUrl/videoFile")
        if not any((l.get("note") or l.get("label")) for l in (r.get("loved") or [])):
            raise ValueError(f"reel {i} has no loved notes")
    if not b.get("refs"):
        raise ValueError("no refs")
    if not (b.get("film") or {}).get("idea"):
        raise ValueError("film.idea missing")
    if not b.get("mustHaveShots"):
        raise ValueError("mustHaveShots empty")
    five = {t.get("label"): [x for x in (t.get("items") or []) if x] for t in (b.get("fiveThings") or [])}
    missing = [l for l in FIVE_THINGS if not five.get(l)]
    if missing:
        raise ValueError(f"fiveThings missing or empty: {missing}")
    if _has_forbidden(b):
        raise ValueError("brief contains forbidden beats/words keys")


# ---------------------------------------------------------------------------
# Gemini call — structured output, with retry/backoff on 429/5xx and on our own
# validation failures (P3/P4).
# ---------------------------------------------------------------------------
def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return getattr(exc, "code", None) == 429
    return isinstance(exc, ValueError)  # bad/empty JSON or failed validation


@retry(stop=stop_after_attempt(4),
       wait=wait_exponential(multiplier=2, min=2, max=30),
       retry=retry_if_exception(_retryable),
       reraise=True)
def generate_brief(client, model, contents, handle, manifest, ref_lib,
                   moxie_refs_dir=None) -> dict:
    """Call Gemini for the portal brief, assemble deterministic fields, validate.
    Retries the whole call (not just the request) so a model that returns an
    invalid brief gets another shot instead of us shipping it."""
    resp = client.models.generate_content(
        model=model, contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BRIEF_SCHEMA,
            safety_settings=_SAFETY_OFF,
            # A full brief (reels, five specs, shots) is long — give it room so
            # structured output isn't truncated mid-JSON (a MAX_TOKENS finish).
            max_output_tokens=8192))
    text = resp.text
    if not text:
        # 200 with no text: say WHY (safety block, MAX_TOKENS, empty) so the log
        # is actionable instead of a bare "did not return JSON". Still a
        # ValueError, so tenacity retries it.
        fr = pf = None
        try:
            fr = resp.candidates[0].finish_reason
        except (AttributeError, IndexError, TypeError):
            pass
        pf = getattr(resp, "prompt_feedback", None)
        raise ValueError(f"Gemini returned no text (finish_reason={fr}, prompt_feedback={pf})")
    try:
        model_out = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Gemini did not return JSON: {e}")
    brief = assemble_brief(handle, model_out, manifest, ref_lib, moxie_refs_dir)
    validate_brief(brief)
    return brief


# ---------------------------------------------------------------------------
# Reel download (P3) — adapted from DG-API/ig_download.py run_user(). Fetches a
# creator's last N reels into reels/<handle>/NN_<shortcode>.mp4 + .manifest.json,
# so a brief run can pull reels that aren't on disk yet. apify_client + requests
# are imported lazily so this module stays importable without them / without keys.
# ---------------------------------------------------------------------------
def download_reels(handle, count=12, reels_dir=None):
    import requests
    try:
        from apify_client import ApifyClient
    except ImportError as e:
        raise RuntimeError("apify-client not installed — `pip install apify-client` to enable reel download") from e

    key = os.environ.get("APIFY_API_KEY")
    if not key:
        raise RuntimeError("APIFY_API_KEY not set — cannot download reels")

    handle = norm_handle(handle)
    out = Path(reels_dir) if reels_dir else (ROOT / "reels" / handle)
    out.mkdir(parents=True, exist_ok=True)

    client = ApifyClient(key)
    run_ = client.actor(REELS_ACTOR).call(
        run_input={"username": [handle], "resultsLimit": count, "addComments": False})
    items = list(client.dataset(run_["defaultDatasetId"]).iterate_items())
    items.sort(key=lambda i: i.get("timestamp") or "", reverse=True)

    mpath = out / ".manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    manifest = {k: v for k, v in manifest.items() if (out / v).exists()}

    for i, it in enumerate(items[:count], 1):
        sc = it.get("shortCode") or it.get("shortcode") or _shortcode(it.get("url", ""))
        src = it.get("videoUrl")
        if not sc or not src or sc in manifest:
            continue
        name = f"{i:02d}_{sc}.mp4"
        r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=180, stream=True)
        r.raise_for_status()
        with open(out / name, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        manifest[sc] = name
        mpath.write_text(json.dumps(manifest, indent=1))
    return out


# ---------------------------------------------------------------------------
def _selftest():
    """Offline check of the deterministic emit path — no key, no network."""
    # library parse: a bare shortcode becomes a reel URL, a full URL passes through
    lib = parse_reference_library(
        "| Film | Pillar | Reel URL |\n"
        "|---|---|---|\n"
        "| `aashiadani` | 1 | ABC123 |\n"
        "| `taneesho` | 1 | https://www.instagram.com/reel/XYZ/ |\n"
        "| `nutellaonella` | 1 |  |\n")
    assert lib == {
        "aashiadani": "https://www.instagram.com/reel/ABC123/",
        "taneesho": "https://www.instagram.com/reel/XYZ/",
    }, lib

    manifest = {"Da2qlkpyJqG": "06_Da2qlkpyJqG.mp4", "DbnmPDZSSrl": "02_DbnmPDZSSrl.mp4"}
    model = {
        "whyYou": "loved your GRWM.",
        "reels": [
            {"reel": "06_Da2qlkpyJqG", "title": "B.Ed Student GRWM",
             "loved": [{"label": "Background", "time": "0:38", "note": "airy depth"}]},
            {"reel": "02_DbnmPDZSSrl.mp4", "title": "Traditional Transition",
             "loved": [{"label": "Hook", "time": "0:01", "note": "question on frame 0"}]},
        ],
        "refs": [
            {"libraryHandle": "@aashiadani", "pairsWithReel": "06_Da2qlkpyJqG", "share": "fast demo cuts"},
            {"libraryHandle": "nutellaonella", "pairsWithReel": "02_DbnmPDZSSrl", "share": "warm side-light"},
        ],
        "film": {"idea": "heal the scalp barrier", "format": "Reel · 9:16", "length": "45-55 sec"},
        "fiveThings": [{"label": l, "items": [f"{l} spec"]} for l in FIVE_THINGS],
        "products": ["Moxie Pre-Wash"],
        "mustHaveShots": ["Macro close-up of the scalp parting."],
    }
    b = assemble_brief("_gopikakrishna", model, manifest, lib,
                       moxie_refs_dir=ROOT / "reels" / "_moxie_refs")
    validate_brief(b)  # must not raise

    assert b["handle"] == "gopikakrishna"  # leading underscore stripped
    # igUrl + videoFile come from the manifest, not the model
    assert b["reels"][0]["igUrl"] == "https://www.instagram.com/reel/Da2qlkpyJqG/"
    assert b["reels"][0]["videoFile"] == "06_Da2qlkpyJqG.mp4"
    assert b["reels"][1]["videoFile"] == "02_DbnmPDZSSrl.mp4"  # ".mp4" tolerated
    # pairsWith is generated deterministically from the pairing index
    assert b["refs"][0]["pairsWith"] == "your reel #1 — B.Ed Student GRWM", b["refs"][0]
    assert b["refs"][1]["pairsWith"] == "your reel #2 — Traditional Transition"
    # aashiadani had a library URL; nutellaonella did not -> profile fallback
    assert b["refs"][0]["igUrl"] == "https://www.instagram.com/reel/ABC123/"
    assert b["refs"][1]["igUrl"] == "https://www.instagram.com/nutellaonella/"
    assert not _has_forbidden(b)

    # validation actually rejects bad output
    for bad in ({"reels": []},
                {**b, "reels": b["reels"][:1]},                       # one reel is not a shortlist
                {**b, "fiveThings": b["fiveThings"][:4]},              # Outfit dropped
                {**b, "fiveThings": b["fiveThings"][:4] + [{"label": "Outfit", "items": []}]},
                {"reels": b["reels"], "refs": [], "film": b["film"], "mustHaveShots": ["x"]},
                {**b, "beats": [1]}):
        try:
            validate_brief(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"validate_brief accepted bad brief: {bad}")
    print("selftest ok")


def _emit_mock(handle, outpath):
    """Write a realistic canned brief for `handle` using that handle's real
    on-disk manifest — the mocked emit path for VERIFY when no live key/network."""
    h = norm_handle(handle)
    reels_dir = None
    for cand in (ROOT / "reels" / h, ROOT / "reels" / f"_{h}"):
        if cand.is_dir():
            reels_dir = cand
            break
    manifest = load_manifest(reels_dir) if reels_dir else {}
    codes = list(manifest.keys())[:3] or ["AAA111", "BBB222", "CCC333"]
    stems = [_stem(manifest[c]) for c in codes] if manifest else ["01_AAA111", "02_BBB222", "03_CCC333"]
    lib = parse_reference_library((ROOT / "moxie-taste" / "references" / "moxie_reference_library.md").read_text())
    model = {
        "whyYou": f"@{h}, your reels already do what Moxie films do — clean depth, honest light.",
        "reels": [
            {"reel": stems[0], "title": "Routine GRWM",
             "loved": [{"label": "Background", "time": "0:12", "note": "clean wall separation keeps your frame airy."},
                       {"label": "Pacing", "time": "", "note": "roughly one cut a second — your demos never drag."}]},
            {"reel": stems[1], "title": "Transition Reel",
             "loved": [{"label": "Hook", "time": "0:01", "note": "on-screen question on frame zero with an immediate gesture."}]},
            {"reel": stems[2], "title": "Definition Showcase",
             "loved": [{"label": "Lighting", "time": "0:04", "note": "directional light catches individual clumps."}]},
        ][:len(stems)],
        "refs": [
            {"libraryHandle": "aashiadani", "pairsWithReel": stems[0], "share": "Fast rhythmic demo cuts in a bright interior."},
            {"libraryHandle": "srish_teee", "pairsWithReel": stems[1], "share": "Flat-assertion hook, warm enthusiasm."},
            {"libraryHandle": "nutellaonella", "pairsWithReel": stems[2], "share": "Warm side-lighting on curl clumps."},
        ][:len(stems)],
        "film": {"idea": "Heal the scalp barrier — don't scrub flakes raw.",
                 "format": "Reel · 9:16", "length": "45-55 sec"},
        "fiveThings": [
            {"label": "Background", "items": ["Location 1: your textured doorway.", "Location 2 (reveal): by your bright window."]},
            {"label": "Lighting", "items": ["Shoot 3:00-5:30 PM soft daylight, key 45° front."]},
            {"label": "Pacing", "items": ["1.0-1.2s per cut through application; hold the reveal 3-4s."]},
            {"label": "Hook", "items": ["\"Dandruff isn't dirt — it's a broken scalp barrier.\""]},
            {"label": "Outfit", "items": ["Look 1: neutral sleeveless. Look 2 (reveal): a vibrant kurti."]},
        ],
        "products": ["Moxie Dandruff Detox Pre-Wash Treatment", "Moxie Scalp Reviving Shampoo", "Scalp massager"],
        "mustHaveShots": [
            "Macro close-up of the scalp parting — flakes visible at the start, clean at the end.",
            "The bi-phase bottle held to camera, then the shake that blends the layers.",
            "Precision nozzle applying product onto dry scalp sections.",
            "Final flake-free part to camera in bright window light.",
        ],
    }
    b = assemble_brief(h, model, manifest, lib, moxie_refs_dir=ROOT / "reels" / "_moxie_refs")
    validate_brief(b)
    Path(outpath).write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote mock brief -> {outpath}")


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    elif "--emit-mock" in sys.argv:
        i = sys.argv.index("--emit-mock")
        _emit_mock(sys.argv[i + 1], sys.argv[i + 2])
    else:
        print("usage: python brief.py --selftest | --emit-mock <handle> <outpath>")
