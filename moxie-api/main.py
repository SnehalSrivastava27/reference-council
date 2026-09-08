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

    contents: list = [skill_prompt(), TASK]
    if campaign_brief:
        contents.append(f"===== CAMPAIGN BRIEF (stage 0) =====\n{campaign_brief}")
    if brief_pdf:
        contents.append("===== CAMPAIGN BRIEF PDF (stage 0) =====")
        contents.append(types.Part.from_bytes(
            data=brief_pdf.file.read(), mime_type="application/pdf"))
    contents.append("===== creator_analysis.json =====\n" + json.dumps(machine, indent=2))
    for img in images:
        contents.append(f"IMAGE: {img.relative_to(out)}")
        contents.append(types.Part.from_bytes(data=img.read_bytes(), mime_type="image/jpeg"))

    resp = gemini().models.generate_content(
        model=MODEL, contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json"))
    try:
        review = json.loads(resp.text)
    except (json.JSONDecodeError, TypeError):
        review = {"raw": resp.text}

    return {"handle": handle, "model": MODEL, "machine": machine,
            "images_reviewed": len(images), "review": review}


def _brief_contents(machine, images, out, campaign_brief, brief_pdf):
    contents: list = [skill_prompt(), brief.BRIEF_TASK]
    if campaign_brief:
        contents.append(f"===== CAMPAIGN BRIEF (stage 0) =====\n{campaign_brief}")
    if brief_pdf:
        contents.append("===== CAMPAIGN BRIEF PDF (stage 0) =====")
        contents.append(types.Part.from_bytes(
            data=brief_pdf.file.read(), mime_type="application/pdf"))
    contents.append("===== creator_analysis.json =====\n" + json.dumps(machine, indent=2))
    for img in images:
        contents.append(f"IMAGE: {img.relative_to(out)}")
        contents.append(types.Part.from_bytes(data=img.read_bytes(), mime_type="image/jpeg"))
    return contents


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
    contents = _brief_contents(machine, images, out, campaign_brief, brief_pdf)

    result = brief.generate_brief(
        gemini(), MODEL, contents, h, manifest, ref_lib,
        moxie_refs_dir=ROOT / "reels" / "_moxie_refs")

    dest = ROOT / f"{h}_collab_brief.json"
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return {"handle": h, "model": MODEL, "images_reviewed": len(images),
            "written": str(dest), "brief": result}


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
