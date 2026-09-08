#!/usr/bin/env python3
"""
analyze_creator.py — Ingest a creator's recent reels and score them.

This is the entry point for creator onboarding. Point it at a folder of the
creator's last ~12 reels and it produces:

  1. A contact sheet per reel (24 frames tiled) so you can actually SEE each
     one — including the hook frames and the on-screen captions
  2. Measured pacing and lighting per reel
  3. A ranked table and creator_analysis.json for the shortlisting stage

Usage:
    python analyze_creator.py <folder_of_reels/> --handle @creatorname
    python analyze_creator.py <folder/> --handle @x --outdir ./out --no-sheets

The contact sheets are the important output. Numbers alone cannot tell you
whether a background has depth, whether a hook opens mid-thought, or whether an
outfit separates from the wall — you have to look. The measurements handle the
two dimensions the eye is worst at judging: cut rhythm and colour temperature.

Requires: ffmpeg, ffprobe, numpy, Pillow
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
from concurrent.futures import ProcessPoolExecutor, as_completed

# Pacing thresholds — see references/measured_benchmarks.md
HARD_CUT, JUMP_CUT = 0.30, 0.12
PACE_LO, PACE_HI = 0.8, 1.5

# Lighting targets
LUMA_LO, LUMA_HI = 115, 135
WARM_LO, WARM_HI = 1.20, 1.35
SAT_LO, SAT_HI = 0.25, 0.33
WARM_FLOOR = 1.15  # no reference film sits below this


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def duration(path):
    """Seconds, or 0.0 when ffprobe is missing or the file has no readable
    duration. Callers treat 0.0 as a measurement failure rather than crashing."""
    try:
        out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "csv=p=0", path]).stdout.strip()
        return float(out)
    except (FileNotFoundError, ValueError):
        return 0.0


def scene_scores(path, floor=0.05):
    """
    Single-decode scene detection. Returns every frame's scene score above
    `floor`; both the hard-cut and jump-cut counts are derived from this in
    Python. Decoding is the expensive part, so doing it once rather than once
    per threshold roughly halves the cost of the whole pipeline — which is the
    difference between a roster of 1000 finishing overnight and not.
    """
    proc = run(["ffmpeg", "-nostats", "-v", "quiet", "-i", path,
                "-vf", f"select='gt(scene,{floor})',metadata=print:file=-",
                "-f", "null", "-"])
    scores = []
    for line in proc.stdout.splitlines():
        if "lavfi.scene_score=" in line:
            try:
                scores.append(float(line.split("=", 1)[1]))
            except ValueError:
                pass
    return scores


def shots_from_scores(scores, threshold):
    """Shot count = cuts above threshold, plus one."""
    return sum(1 for x in scores if x > threshold) + 1


def contact_sheet(path, out_path, frames=24, cols=4):
    """Tile `frames` evenly-spaced stills into one image."""
    d = duration(path)
    if d <= 0:
        return None  # unreadable video — no sheet, no divide-by-zero
    rows = (frames + cols - 1) // cols
    run(["ffmpeg", "-v", "error", "-i", path,
         "-vf", f"fps={frames / d},scale=300:-1,"
                f"tile={cols}x{rows}:margin=4:padding=4",
         "-frames:v", "1", "-q:v", "3", out_path, "-y"])
    return out_path if os.path.exists(out_path) else None


def hook_frames(path, out_dir, seconds=3):
    """Extract the first 3 seconds at high res — the hook is decided here."""
    os.makedirs(out_dir, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-t", str(seconds), "-i", path,
         "-vf", "fps=2,scale=720:-1", "-q:v", "2",
         os.path.join(out_dir, "hook_%02d.jpg"), "-y"])
    return sorted(glob.glob(os.path.join(out_dir, "*.jpg")))


def lighting(path, every=3):
    tmp = tempfile.mkdtemp()
    try:
        run(["ffmpeg", "-v", "quiet", "-i", path,
             "-vf", f"fps=1/{every},scale=160:-1", "-q:v", "5",
             os.path.join(tmp, "%03d.jpg"), "-y"])
        frames = sorted(glob.glob(os.path.join(tmp, "*.jpg")))
        if not frames:
            return None
        L, R, B, S = [], [], [], []
        for p in frames:
            a = np.asarray(Image.open(p).convert("RGB"), dtype=float)
            r, g, b = a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean()
            L.append(0.299 * r + 0.587 * g + 0.114 * b)
            R.append(r)
            B.append(b)
            mx, mn = a.max(2), a.min(2)
            S.append(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0).mean())
        return {
            "luma": round(float(np.mean(L)), 1),
            "luma_sd": round(float(np.std(L)), 1),
            "warmth_rb": round(float(np.mean(R) / np.mean(B)), 2),
            "saturation": round(float(np.mean(S)), 2),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pace_flag(avg):
    if avg < PACE_LO:
        return "FAST"
    if avg > PACE_HI:
        return "SLOW"
    return "ON-PACE"


def light_flags(li):
    f = []
    if li["warmth_rb"] < WARM_FLOOR:
        f.append("COOL — off-brand, no Moxie reference sits here")
    elif li["warmth_rb"] > WARM_HI:
        f.append("very warm — OK outdoors only")
    if li["luma"] < LUMA_LO:
        f.append("underlit")
    elif li["luma"] > LUMA_HI:
        f.append("hot")
    if li["saturation"] > 0.40:
        f.append("saturated — check product would still read as brightest object")
    return f or ["on-look"]


def auto_score(pace_avg, li):
    """
    Rough 0-10 machine score on the two measurable parameters only.
    Pacing and Lighting can be scored automatically. Background, Hook and
    Outfit CANNOT — they need eyes on the contact sheet. This score exists to
    rank the 12 for review order, not to pick the shortlist.
    """
    s = 0
    if PACE_LO <= pace_avg <= PACE_HI:
        s += 5
    elif pace_avg <= 2.0:
        s += 3
    elif pace_avg <= 2.6:
        s += 1
    if WARM_LO <= li["warmth_rb"] <= WARM_HI:
        s += 3
    elif li["warmth_rb"] >= WARM_FLOOR:
        s += 2
    if LUMA_LO <= li["luma"] <= LUMA_HI:
        s += 2
    elif li["luma"] >= 108:
        s += 1
    return s


# --- Triage gate -------------------------------------------------------------
# At 1000+ creators you cannot look at 12,000 reels. The machine pass runs on
# everything; vision review is spent only on what survives this gate.

MIN_MACHINE = 5      # a reel below this is not worth a contact sheet
MIN_PASSING_REELS = 2  # a creator with fewer than 2 passing reels is auto-rejected


def hard_fail(rec):
    """Reasons a reel is excluded from review regardless of its score."""
    f = []
    if rec.get("warmth_rb", 99) < WARM_FLOOR:
        f.append("cool-toned — no Moxie reference sits below 1.15 warmth")
    if rec["avg_shot_s"] > 3.0:
        f.append(f"static ({rec['avg_shot_s']}s avg shot)")
    if rec.get("luma", 99) < 95:
        f.append(f"severely underlit (luma {rec.get('luma')})")
    return f


def triage(records, min_machine=MIN_MACHINE):
    """Split a creator's reels into review / skip, and decide creator verdict."""
    for r in records:
        r["hard_fails"] = hard_fail(r)
        r["review"] = (not r["hard_fails"]) and r["machine_score_10"] >= min_machine
    passing = [r for r in records if r["review"]]
    if len(passing) >= MIN_PASSING_REELS:
        verdict = "REVIEW"
    elif passing:
        verdict = "BORDERLINE"
    else:
        verdict = "AUTO-REJECT"
    return verdict, passing


def failed_record(name, reason):
    """A measurement-failed reel with every key downstream code reads, so a bad
    video (missing ffmpeg, zero duration, unreadable) is surfaced in the output
    instead of crashing the run. Scored 0 and hard-failed so it never reaches
    review."""
    return {
        "reel": name, "duration_s": 0.0, "shots_hard": 0, "shots_incl_jump": 0,
        "avg_shot_s": 99.0, "cuts_per_min": 0.0, "pacing_flag": "n/a",
        "lighting_flags": [f"measurement failed: {reason}"],
        "machine_score_10": 0, "error": reason,
    }


def measure(path):
    """Measurement only — no image output. Cheap enough to run on everything."""
    name = os.path.splitext(os.path.basename(path))[0]
    d = duration(path)
    if d <= 0:
        return {**failed_record(name, "zero/unreadable duration"), "path": path}
    scores = scene_scores(path)
    jump = shots_from_scores(scores, JUMP_CUT)
    hard = shots_from_scores(scores, HARD_CUT)
    li = lighting(path) or {}
    rec = {
        "reel": name,
        "path": path,
        "duration_s": round(d, 1),
        "shots_hard": hard,
        "shots_incl_jump": jump,
        "avg_shot_s": round(d / jump, 2),
        "cuts_per_min": round(jump / d * 60, 1),
        "pacing_flag": pace_flag(d / jump),
        **li,
        "lighting_flags": light_flags(li) if li else ["measurement failed"],
    }
    rec["machine_score_10"] = auto_score(rec["avg_shot_s"], li) if li else 0
    return rec


def render(rec, outdir):
    """Contact sheet + hook frames. Only called for reels that survive triage."""
    name = rec["reel"]
    sheets = os.path.join(outdir, "sheets")
    hooks = os.path.join(outdir, "hooks", name)
    os.makedirs(sheets, exist_ok=True)
    rec["contact_sheet"] = contact_sheet(
        rec["path"], os.path.join(sheets, f"{name}.jpg"))
    rec["hook_frames"] = hook_frames(rec["path"], hooks)
    return rec


def analyse(path, outdir, make_sheets=True):
    name = os.path.splitext(os.path.basename(path))[0]
    d = duration(path)
    if d <= 0:
        return failed_record(name, "zero/unreadable duration")
    scores = scene_scores(path)
    jump = shots_from_scores(scores, JUMP_CUT)
    hard = shots_from_scores(scores, HARD_CUT)
    li = lighting(path) or {}

    rec = {
        "reel": name,
        "duration_s": round(d, 1),
        "shots_hard": hard,
        "shots_incl_jump": jump,
        "avg_shot_s": round(d / jump, 2),
        "cuts_per_min": round(jump / d * 60, 1),
        "pacing_flag": pace_flag(d / jump),
        **li,
        "lighting_flags": light_flags(li) if li else ["measurement failed"],
    }
    rec["machine_score_10"] = auto_score(rec["avg_shot_s"], li) if li else 0

    if make_sheets:
        sheets = os.path.join(outdir, "sheets")
        hooks = os.path.join(outdir, "hooks", name)
        os.makedirs(sheets, exist_ok=True)
        rec["contact_sheet"] = contact_sheet(
            path, os.path.join(sheets, f"{name}.jpg"))
        rec["hook_frames"] = hook_frames(path, hooks)

    return rec


def main():
    ap = argparse.ArgumentParser(
        description="Batch-measure a creator's reels and triage them for review.")
    ap.add_argument("folder", help="folder of the creator's reels (.mp4)")
    ap.add_argument("--handle", default="unknown", help="creator handle")
    ap.add_argument("--outdir", default="./creator_analysis")
    ap.add_argument("--workers", type=int, default=os.cpu_count(),
                    help="parallel measurement workers")
    ap.add_argument("--review-top", type=int, default=5,
                    help="max reels to render contact sheets for (vision budget)")
    ap.add_argument("--min-machine", type=int, default=MIN_MACHINE,
                    help="machine score floor for review")
    ap.add_argument("--no-sheets", action="store_true",
                    help="measurement only — no images. Use for a first pass over a large roster.")
    args = ap.parse_args()

    reels = sorted(glob.glob(os.path.join(args.folder, "*.mp4")))
    if not reels:
        print(f"No .mp4 files in {args.folder}")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    # Stage 1 — measure everything in parallel. No images yet.
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(measure, p): p for p in reels}
        for fut in as_completed(futures):
            name = os.path.splitext(os.path.basename(futures[fut]))[0]
            try:
                results.append(fut.result())
            except Exception as e:
                # surface the failure in the output, don't just print it
                print(f"  !! failed {name}: {e}")
                results.append(failed_record(name, str(e)))

    results.sort(key=lambda r: -r["machine_score_10"])

    # Stage 2 — triage. Decides who gets a vision review at all.
    verdict, passing = triage(results, args.min_machine)

    # Stage 3 — render contact sheets ONLY for the top survivors.
    rendered = 0
    if not args.no_sheets and verdict != "AUTO-REJECT":
        for rec in [r for r in results if r["review"]][:args.review_top]:
            render(rec, args.outdir)
            rendered += 1

    print(f"\nCreator: {args.handle}   ({len(results)} reels)   VERDICT: {verdict}\n")
    print(f"{'reel':26s} {'len':>6s} {'avg_shot':>9s} {'luma':>6s} {'warm':>6s} "
          f"{'m/10':>5s} {'rev':>4s}  flags")
    print("-" * 122)
    for r in results:
        mark = "yes" if r["review"] else "-"
        flags = "; ".join(r["hard_fails"]) if r["hard_fails"] else \
                f"{r['pacing_flag']}; {'; '.join(r['lighting_flags'])}"
        print(f"{r['reel']:26s} {r['duration_s']:5.1f}s {r['avg_shot_s']:8.2f}s "
              f"{r.get('luma', 0):6.1f} {r.get('warmth_rb', 0):6.2f} "
              f"{r['machine_score_10']:5d} {mark:>4s}  {flags}")

    payload = {
        "handle": args.handle,
        "reel_count": len(results),
        "verdict": verdict,
        "passing_reels": len(passing),
        "rendered_sheets": rendered,
        "reels": results,
    }
    out = os.path.join(args.outdir, "creator_analysis.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote {out}")

    if verdict == "AUTO-REJECT":
        print("\nAUTO-REJECT — fewer than 2 reels cleared the machine floor.")
        print("No contact sheets rendered. Do not spend review time here.")
    else:
        print(f"\nRendered {rendered} contact sheet(s) → {args.outdir}/sheets/")
        print(f"Hook frames → {args.outdir}/hooks/")
        print("\nNEXT: view those sheets. The machine score ranks review order only —")
        print("it cannot see background, hook or outfit. Score those by eye against")
        print("references/scoring_rubric.md before shortlisting.")


if __name__ == "__main__":
    main()
