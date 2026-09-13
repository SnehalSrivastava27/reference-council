"""Moxie Taste API — runs the moxie-taste skill over a creator's reels.

POST /analyze : upload reels (or point at a local folder) → machine measurements
(ffmpeg pass from the skill's analyze_creator.py) + Gemini vision review
(scorecard, shortlist + praise, creator-facing brief) driven by the skill's own
agent and reference files as the prompt.

Env:
  GEMINI_API_KEY   required
  GEMINI_MODEL     default gemini-2.5-flash ("gemini 3.7 flash" does not exist)
  MOXIE_SKILL_DIR  default ../moxie-taste relative to this file

Run: uvicorn main:app --reload
"""

import functools
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from google import genai
from google.genai import types

import brief

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # repo root
load_dotenv()  # moxie-api/.env, if present; existing env vars win

SKILL_DIR = Path(os.environ.get(
    "MOXIE_SKILL_DIR",
    Path(__file__).resolve().parent.parent / "moxie-taste"))
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
ANALYZE_SCRIPT = SKILL_DIR / "scripts" / "analyze_creator.py"
MAX_IMAGES = 80  # safety net only: 12 sheets + 3 hook frames x 12 reels = 48

# The skill's own files ARE the prompt. Loaded fresh per request so edits to
# the skill take effect without a restart.
PROMPT_FILES = [
    "references/scoring_rubric.md",
    "references/backgrounds_and_lighting.md",
    "references/hook_library.md",
    "references/moxie_reference_library.md",
    "references/brief_template.md",
    "agents/reel_analyst.md",
    "agents/shortlist_and_praise.md",
    "agents/brief_writer.md",
]

TASK = """You are executing the Moxie Taste creator-onboarding skill. The
reference/agent documents above are your standard — follow them exactly.

You are given the machine measurements (creator_analysis.json) and, labelled by
filename, contact sheets (24 tiled frames per reel) and hook frames (first
seconds of each reel). The machine score covers Pacing and Lighting only;
Background, Hook and Outfit you must judge from the images.

If a campaign brief is provided it sets the scoring bands and the reference
pairing library (stage 0). Otherwise score against the house standard.

Return ONLY a JSON object with these keys:
  "scorecard": internal — per reel: five parameter scores 1-5 with one-line
               reasons, rejection reasons, risk flags. Never shown to the creator.
  "shortlist": the best 3 reels (2 only if no third deserves it), each with
               specific warm praise per parameter.
  "reference_pairing": for each shortlisted reel, the paired Moxie reference
               reel and why it rhymes.
  "brief": the full creator-facing collab brief as markdown, per the template.
               No scores, no criticism of other reels.
"""

app = FastAPI(title="Moxie Taste API")


@functools.lru_cache
def gemini() -> genai.Client:
    # lazy so the app imports without GEMINI_API_KEY; cached so the client's
    # httpx session isn't GC-closed mid-request
    return genai.Client()


def skill_prompt() -> str:
    return "".join(
        f"\n\n===== {rel} =====\n{(SKILL_DIR / rel).read_text()}"
        for rel in PROMPT_FILES)


@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "skill_dir": str(SKILL_DIR),
            "skill_found": ANALYZE_SCRIPT.exists()}


def _repo_reels_dir(handle):
    """The repo's reels/<handle> folder, tolerating the stray reels/_<handle>
    (gopikakrishna). None if neither has any mp4s."""
    for cand in (ROOT / "reels" / handle, ROOT / "reels" / f"_{handle}"):
        if cand.is_dir() and list(cand.glob("*.mp4")):
            return cand
    return None


def _reels_src(reels, reels_dir, handle, workdir, download=False):
    """Resolve the folder of the creator's reels: uploads, an explicit reels_dir,
    or the repo's reels/<handle> (also reels/_<handle>, tolerating the stray
    leading underscore). Downloads via Apify only when asked and nothing is local."""
    if reels:
        src = workdir / "reels"
        src.mkdir()
        for f in reels:
            name = Path(f.filename or "reel.mp4").name
            if not name.lower().endswith((".mp4", ".mov", ".m4v")):
                raise HTTPException(400, f"Not a video file: {name}")
            (src / name).write_bytes(f.file.read())
        return src
    if reels_dir:
        src = Path(reels_dir)
        if not src.is_dir():
            raise HTTPException(400, f"reels_dir not found: {reels_dir}")
        return src
    local = _repo_reels_dir(handle)
    if local:
        return local
    if download:
        try:
            return brief.download_reels(handle)
        except Exception as e:
            raise HTTPException(400, f"no local reels and download failed: {e}")
    raise HTTPException(400, f"no reels for {handle} under reels/ — upload reels, "
                             "pass reels_dir, or set download=true")


def _analyze(handle, src, workdir):
    """Run the ffmpeg/measure pass (analyze_creator.py) and collect its outputs."""
    out = workdir / "out"
    proc = subprocess.run(
        [sys.executable, str(ANALYZE_SCRIPT), str(src),
         "--handle", handle, "--outdir", str(out),
         # Every reel gets a contact sheet. The triage gate is a roster-screening
         # tool: it ranks on lighting + pacing only, so it dropped the indoor
         # reels (cooler, dimmer) and Gemini never saw their backgrounds.
         "--review-all"],
        capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise HTTPException(500, f"analyze_creator.py failed: {proc.stderr[-2000:]}")
    machine = json.loads((out / "creator_analysis.json").read_text())
    images = sorted((out / "sheets").glob("*.jpg")) if (out / "sheets").is_dir() else []
    # hook frames are 3s at 2fps; every other one (0s, 1s, 2s) reads caption timing fine
    for d in sorted((out / "hooks").iterdir()) if (out / "hooks").is_dir() else []:
        images += sorted(d.glob("*.jpg"))[::2]
    return machine, images[:MAX_IMAGES], out


@app.post("/analyze")
def analyze(
    handle: str = Form(...),
    campaign_brief: str = Form(""),
    brief_pdf: Optional[UploadFile] = File(default=None),
    reels_dir: str = Form(""),
    reels: list[UploadFile] = File(default=[]),
):
    # ponytail: synchronous request, add a job queue when a roster batch or
    # client timeouts make it hurt
    if not reels and not reels_dir:
        raise HTTPException(400, "Provide reel uploads or a local reels_dir")

    slug = re.sub(r"[^a-zA-Z0-9_]", "", handle) or "creator"
    workdir = Path(tempfile.mkdtemp(prefix=f"moxie_{slug}_"))
    src = _reels_src(reels, reels_dir, brief.norm_handle(handle), workdir)
    machine, images, out = _analyze(handle, src, workdir)

    pdf_bytes = brief_pdf.file.read() if brief_pdf else None
    contents = _contents(TASK, machine, images, out, campaign_brief, pdf_bytes)

    excluded = []
    try:
        review = _review_json(contents)
    except brief.PromptBlocked as e:
        contents, images, excluded = _contents_minus_blocked(
            TASK, e.reason, machine, images, out, campaign_brief, pdf_bytes)
        review = _review_json(contents)

    return {"handle": handle, "model": MODEL, "machine": machine,
            "images_reviewed": len(images), "excluded_reels": excluded,
            "review": review}


def _contents(task, machine, images, out, campaign_brief, pdf_bytes):
    """The prompt for one creator: skill docs, the task, the campaign brief, the
    measurements, then every frame. pdf_bytes (not the UploadFile) because the
    prompt is rebuilt on a safety-block retry and a file object only reads once."""
    contents: list = [skill_prompt(), task]
    if campaign_brief:
        contents.append(f"===== CAMPAIGN BRIEF (stage 0) =====\n{campaign_brief}")
    if pdf_bytes:
        contents.append("===== CAMPAIGN BRIEF PDF (stage 0) =====")
        contents.append(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
    contents.append("===== creator_analysis.json =====\n" + json.dumps(machine, indent=2))
    for img in images:
        contents.append(f"IMAGE: {img.relative_to(out)}")
        contents.append(types.Part.from_bytes(data=img.read_bytes(), mime_type="image/jpeg"))
    return contents


def _probe_reel(item):
    """Do this reel's own frames trip the block? Returns the reel name, or None."""
    name, imgs = item
    parts = [types.Part.from_bytes(data=i.read_bytes(), mime_type="image/jpeg")
             for i in imgs]
    try:
        resp = gemini().models.generate_content(
            model=MODEL, contents=["Reply with: ok"] + parts,
            config=types.GenerateContentConfig(max_output_tokens=16,
                                               safety_settings=brief.SAFETY_OFF))
    except Exception:
        return None  # transient API error — never drop a reel on a failed probe
    return name if brief.block_reason(resp) else None


def _blocked_reels(images):
    """Which reels Gemini refuses to look at. One small probe per reel, in parallel:
    roughly the image-token cost of a single full request, and it names EVERY
    offender — a bisect would find one and block again on the next."""
    by_reel = {}
    for img in images:
        by_reel.setdefault(brief.reel_of_image(img), []).append(img)
    with ThreadPoolExecutor(max_workers=4) as pool:
        return sorted(n for n in pool.map(_probe_reel, by_reel.items()) if n)


def _contents_minus_blocked(task, reason, machine, images, out, campaign_brief, pdf_bytes):
    """Recovery after a PromptBlocked: find the offending reel(s), drop them, and
    rebuild the prompt from the rest so one bad reel doesn't waste the whole run."""
    excluded = _blocked_reels(images)
    if not excluded:
        raise HTTPException(422, f"Gemini blocked the prompt ({reason}) and no single "
                                 "reel reproduces it on its own — the campaign brief "
                                 "text/PDF is the likely trigger.")
    images, machine = brief.drop_reels(images, machine, excluded)
    return _contents(task, machine, images, out, campaign_brief, pdf_bytes), images, excluded


def _review_json(contents):
    """/analyze's Gemini call. Surfaces an input block instead of silently
    returning {"raw": None}."""
    resp = gemini().models.generate_content(
        model=MODEL, contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           safety_settings=brief.SAFETY_OFF))
    reason = brief.block_reason(resp)
    if reason:
        raise brief.PromptBlocked(reason)
    try:
        return json.loads(resp.text)
    except (json.JSONDecodeError, TypeError):
        return {"raw": resp.text}


@app.post("/brief")
def brief_endpoint(
    handle: str = Form(...),
    campaign_brief: str = Form(""),
    brief_pdf: Optional[UploadFile] = File(default=None),
    reels_dir: str = Form(""),
    reels: list[UploadFile] = File(default=[]),
    download: bool = Form(False),
):
    """Per-creator run that writes the exact portal JSON to
    <repo>/<handle>_collab_brief.json — the artifact the portal admin pastes."""
    h = brief.norm_handle(handle)
    slug = re.sub(r"[^a-zA-Z0-9_]", "", h) or "creator"
    workdir = Path(tempfile.mkdtemp(prefix=f"moxie_{slug}_"))

    src = _reels_src(reels, reels_dir, h, workdir, download=download)
    machine, images, out = _analyze(h, src, workdir)

    manifest = brief.load_manifest(src)
    ref_lib = brief.parse_reference_library(
        (SKILL_DIR / "references" / "moxie_reference_library.md").read_text())
    pdf_bytes = brief_pdf.file.read() if brief_pdf else None
    contents = _contents(brief.BRIEF_TASK, machine, images, out, campaign_brief, pdf_bytes)

    def run(c):
        return brief.generate_brief(gemini(), MODEL, c, h, manifest, ref_lib,
                                    moxie_refs_dir=ROOT / "reels" / "_moxie_refs")

    excluded = []
    try:
        result = run(contents)
    except brief.PromptBlocked as e:
        # One unviewable reel out of a dozen used to waste the whole request.
        # Name it, drop it, brief the creator off the reels that are fine.
        contents, images, excluded = _contents_minus_blocked(
            brief.BRIEF_TASK, e.reason, machine, images, out, campaign_brief, pdf_bytes)
        try:
            result = run(contents)
        except brief.PromptBlocked as e2:
            raise HTTPException(422, f"still blocked ({e2.reason}) after excluding {excluded}")

    dest = ROOT / f"{h}_collab_brief.json"
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return {"handle": h, "model": MODEL, "images_reviewed": len(images),
            "excluded_reels": excluded, "written": str(dest), "brief": result}


@app.get("/reel/{handle}/{filename:path}")
def reel(handle: str, filename: str):
    """Stream one creator reel mp4 by the exact videoFile name /brief emitted, so
    the portal can pull the videos right after. `:path` captures slashes only so
    we can reject them — filename must be a plain *.mp4 basename."""
    if "/" in filename or "\\" in filename or ".." in filename \
            or filename != Path(filename).name:
        raise HTTPException(400, "filename must be a plain basename")
    if not filename.lower().endswith(".mp4"):
        raise HTTPException(400, "only .mp4 is served")
    d = _repo_reels_dir(brief.norm_handle(handle))
    if not d:
        raise HTTPException(404, f"no reels for {handle}")
    path = d / filename
    if not path.is_file():
        raise HTTPException(404, f"reel not found: {filename}")
    return FileResponse(path, media_type="video/mp4")


if __name__ == "__main__":
    # `python main.py` so PORT is read after load_dotenv — works from a real
    # container env var (Coolify) or a PORT= line in .env.
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
