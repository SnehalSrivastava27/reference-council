#!/usr/bin/env python3
"""
measure_pacing.py — Measure cut rhythm against the Moxie house standard.

Usage:
    python measure_pacing.py video.mp4 [video2.mp4 ...]
    python measure_pacing.py /path/to/folder/

Reports duration, hard-cut count, jump-cut-inclusive count, average shot
length, and a PASS/SLOW/FAST verdict against the house target of
0.8-1.5s average shot length.

Two thresholds are used because scene detection at a single sensitivity
misses the jump cuts that carry most of the energy in these films:
  0.30 = hard cuts (location / framing changes)
  0.12 = includes jump cuts within a single setup
"""

import subprocess
import sys
import os
import glob
import json

HARD = 0.30
JUMP = 0.12
TARGET_LO, TARGET_HI = 0.8, 1.5


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def shot_count(path, threshold):
    """Return number of shots (cuts + 1) detected at the given threshold."""
    proc = subprocess.run(
        ["ffmpeg", "-nostats", "-v", "quiet", "-i", path,
         "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
         "-f", "null", "-"],
        capture_output=True, text=True)
    return proc.stdout.count("pts_time") + 1


def verdict(avg):
    if avg < TARGET_LO:
        return "FAST — check the hook still reads; very fast cutting suits <20s films only"
    if avg > TARGET_HI:
        return "SLOW — tighten. Add jump cuts in the application section."
    return "PASS — inside house rhythm"


def analyse(path):
    d = duration(path)
    hard = shot_count(path, HARD)
    jump = shot_count(path, JUMP)
    return {
        "file": os.path.basename(path),
        "duration_s": round(d, 1),
        "shots_hard": hard,
        "shots_incl_jump": jump,
        "avg_shot_hard_s": round(d / hard, 2),
        "avg_shot_incl_jump_s": round(d / jump, 2),
        "cuts_per_min": round(jump / d * 60, 1),
        "verdict": verdict(d / jump),
    }


def collect(args):
    paths = []
    for a in args:
        if os.path.isdir(a):
            paths += sorted(glob.glob(os.path.join(a, "*.mp4")))
        else:
            paths.append(a)
    return paths


def main():
    paths = collect(sys.argv[1:])
    if not paths:
        print(__doc__)
        sys.exit(1)

    results = [analyse(p) for p in paths]

    print(f"{'file':28s} {'dur':>6s} {'avg_shot':>9s} {'cuts/min':>9s}  verdict")
    print("-" * 100)
    for r in results:
        print(f"{r['file']:28s} {r['duration_s']:5.1f}s "
              f"{r['avg_shot_incl_jump_s']:8.2f}s {r['cuts_per_min']:9.1f}  "
              f"{r['verdict']}")

    with open("pacing_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote pacing_report.json")


if __name__ == "__main__":
    main()
