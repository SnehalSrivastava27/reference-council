#!/usr/bin/env python3
"""
batch_run.py — Run the machine pass across an entire creator roster.

Built for 1000+ creators. The design constraint is that nobody — human or
model — can look at 12,000 reels. This script does the cheap measurement pass
over everything, applies the triage gate, and hands back a ranked roster so
vision review is spent only where it can change a decision.

Layout it expects:

    roster/
      @creator_one/   reel1.mp4 reel2.mp4 ...
      @creator_two/   ...

Usage:
    python batch_run.py ./roster/ --outdir ./run_2026_08 --workers 16
    python batch_run.py ./roster/ --outdir ./run_2026_08 --resume

Outputs into --outdir:
    roster_summary.json    every creator, verdict, best reels, measurements
    roster_summary.csv     same, spreadsheet-friendly
    review_queue.md        ONLY the creators worth looking at, in priority order
    <handle>/              per-creator analysis + contact sheets for survivors

Resumability matters at this size: a run over 1000 creators takes hours and
will be interrupted. --resume skips creators whose output already exists.
"""

import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYZER = os.path.join(HERE, "analyze_creator.py")


def creator_dirs(root):
    return sorted(
        d for d in glob.glob(os.path.join(root, "*"))
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.mp4"))
    )


def norm_handle(name):
    """Folder basename -> clean handle. Strips a leading @ and a stray leading
    underscore (reels/_gopikakrishna) so the handle doesn't depend on the folder
    being named cleanly."""
    h = os.path.basename(name.rstrip("/")).lstrip("@").strip()
    return h[1:] if h.startswith("_") else h


def run_one(args):
    folder, outdir, review_top, min_machine, no_sheets = args
    handle = norm_handle(folder)
    dest = os.path.join(outdir, handle)
    result_path = os.path.join(dest, "creator_analysis.json")

    cmd = [sys.executable, ANALYZER, folder, "--handle", handle,
           "--outdir", dest, "--review-top", str(review_top),
           "--min-machine", str(min_machine), "--workers", "1"]
    if no_sheets:
        cmd.append("--no-sheets")

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        with open(result_path) as f:
            return json.load(f)
    except Exception as e:
        return {"handle": handle, "verdict": "ERROR", "error": str(e),
                "reels": [], "reel_count": 0, "passing_reels": 0}


def summarise(rec):
    """One row per creator for the roster table."""
    reels = rec.get("reels", [])
    best = reels[0] if reels else {}
    on_pace = sum(1 for r in reels if r.get("pacing_flag") == "ON-PACE")
    warm_ok = sum(1 for r in reels if 1.20 <= r.get("warmth_rb", 0) <= 1.35)
    return {
        "handle": rec.get("handle"),
        "verdict": rec.get("verdict"),
        "reels": rec.get("reel_count", 0),
        "passing": rec.get("passing_reels", 0),
        "best_reel": best.get("reel", ""),
        "best_score": best.get("machine_score_10", 0),
        "best_avg_shot_s": best.get("avg_shot_s", 0),
        "best_luma": best.get("luma", 0),
        "best_warmth": best.get("warmth_rb", 0),
        "pct_on_pace": round(100 * on_pace / len(reels)) if reels else 0,
        "pct_warm_in_band": round(100 * warm_ok / len(reels)) if reels else 0,
    }


def priority(row):
    """Review-queue ordering: strongest, most consistent creators first."""
    return (
        {"REVIEW": 0, "BORDERLINE": 1}.get(row["verdict"], 2),
        -row["passing"],
        -row["best_score"],
        -row["pct_on_pace"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roster", help="folder containing one subfolder per creator")
    ap.add_argument("--outdir", default="./roster_run")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--review-top", type=int, default=4,
                    help="contact sheets per surviving creator (vision budget)")
    ap.add_argument("--min-machine", type=int, default=5)
    ap.add_argument("--no-sheets", action="store_true",
                    help="pure measurement sweep, no images at all")
    ap.add_argument("--resume", action="store_true",
                    help="skip creators already analysed in --outdir")
    args = ap.parse_args()

    folders = creator_dirs(args.roster)
    if not folders:
        print(f"No creator subfolders with .mp4 files under {args.roster}")
        sys.exit(1)

    os.makedirs(args.outdir, exist_ok=True)

    if args.resume:
        before = len(folders)
        folders = [
            f for f in folders
            if not os.path.exists(os.path.join(
                args.outdir, norm_handle(f),
                "creator_analysis.json"))
        ]
        print(f"Resume: skipping {before - len(folders)} already done")

    total_reels = sum(len(glob.glob(os.path.join(f, "*.mp4"))) for f in folders)
    print(f"{len(folders)} creators, {total_reels} reels, {args.workers} workers")
    print("Measuring...\n")

    start = time.time()
    records, done = [], 0
    payloads = [(f, args.outdir, args.review_top, args.min_machine,
                 args.no_sheets) for f in folders]

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(run_one, p) for p in payloads]
        for fut in as_completed(futures):
            rec = fut.result()
            records.append(rec)
            done += 1
            if done % 10 == 0 or done == len(folders):
                rate = done / max(time.time() - start, 1e-6)
                eta = (len(folders) - done) / rate / 60
                print(f"  {done}/{len(folders)}  "
                      f"{rate * 60:.0f} creators/min  ETA {eta:.0f} min")

    # Pull in prior results when resuming so the summary covers the full roster
    if args.resume:
        for d in creator_dirs(args.roster):
            h = norm_handle(d)
            if any(r.get("handle") == h for r in records):
                continue
            p = os.path.join(args.outdir, h, "creator_analysis.json")
            if os.path.exists(p):
                with open(p) as f:
                    records.append(json.load(f))

    rows = sorted((summarise(r) for r in records), key=priority)

    with open(os.path.join(args.outdir, "roster_summary.json"), "w") as f:
        json.dump(rows, f, indent=2)

    # fieldnames from a row if we have one, else from an empty summary so an
    # empty roster still writes a valid header-only CSV instead of IndexError.
    fieldnames = list(rows[0].keys()) if rows else list(summarise({}).keys())
    with open(os.path.join(args.outdir, "roster_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    counts = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    queue = [r for r in rows if r["verdict"] in ("REVIEW", "BORDERLINE")]
    with open(os.path.join(args.outdir, "review_queue.md"), "w") as f:
        f.write("# Review Queue\n\n")
        f.write(f"{len(queue)} of {len(rows)} creators cleared the machine gate.\n\n")
        f.write("Work down this list. Contact sheets are in `<handle>/sheets/`, "
                "hook frames in `<handle>/hooks/`. Score Background, Hook and "
                "Outfit by eye — the machine could not.\n\n")
        f.write("| # | Handle | Verdict | Passing | Best reel | m/10 | avg shot | luma | warm | % on-pace |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(queue, 1):
            f.write(f"| {i} | {r['handle']} | {r['verdict']} | "
                    f"{r['passing']}/{r['reels']} | {r['best_reel']} | "
                    f"{r['best_score']} | {r['best_avg_shot_s']}s | "
                    f"{r['best_luma']} | {r['best_warmth']} | "
                    f"{r['pct_on_pace']}% |\n")

    elapsed = (time.time() - start) / 60
    print(f"\nDone in {elapsed:.1f} min")
    for v, n in sorted(counts.items()):
        print(f"  {v:12s} {n:5d}  ({100 * n / len(rows):.0f}%)")
    print(f"\n  roster_summary.csv   full roster, spreadsheet-ready")
    print(f"  review_queue.md      {len(queue)} creators worth your eyes")
    print(f"\nOnly open contact sheets for creators in the review queue.")


if __name__ == "__main__":
    main()
