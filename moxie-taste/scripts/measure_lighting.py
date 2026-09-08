#!/usr/bin/env python3
"""
measure_lighting.py — Check a film's lighting against the Moxie house look.

Usage:
    python measure_lighting.py video.mp4 [video2.mp4 ...]
    python measure_lighting.py /path/to/folder/

Samples one frame every 3 seconds and reports:
  luma      mean brightness, 0-255            house target 115-135
  warmth    mean red / mean blue ratio         house target 1.20-1.35
  sat       mean saturation, 0-1               house target 0.25-0.33
  luma_sd   brightness variance across film    8-20 single-location

The warmth figure is the most diagnostic number here. Every reference
film in the set measures above 1.15 — the house look has no cool-toned
example at all, so anything under 1.15 is off-brand regardless of how
good the framing is.
"""

import subprocess
import sys
import os
import glob
import json
import tempfile
import shutil

import numpy as np
from PIL import Image

LUMA_LO, LUMA_HI = 115, 135
WARM_LO, WARM_HI = 1.20, 1.35
SAT_LO, SAT_HI = 0.25, 0.33


def sample_frames(path, workdir, every_seconds=3):
    subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", path,
         "-vf", f"fps=1/{every_seconds},scale=160:-1", "-q:v", "5",
         os.path.join(workdir, "%03d.jpg"), "-y"],
        check=False)
    return sorted(glob.glob(os.path.join(workdir, "*.jpg")))


def frame_stats(p):
    a = np.asarray(Image.open(p).convert("RGB"), dtype=float)
    r, g, b = a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean()
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0).mean()
    return luma, r, b, sat


def flags(luma, warmth, sat):
    out = []
    if luma < LUMA_LO:
        out.append("UNDERLIT — lift exposure; wet-hair shots will go muddy")
    elif luma > LUMA_HI:
        out.append("HOT — pull back; skin texture is being lost")
    if warmth < WARM_LO:
        out.append("TOO COOL — off-brand; no reference film sits here. Warm the source.")
    elif warmth > WARM_HI:
        out.append("VERY WARM — acceptable only for golden-hour or tropical exteriors")
    if sat < SAT_LO:
        out.append("FLAT — background may be too neutral for the yellow to pop")
    elif sat > SAT_HI:
        out.append("SATURATED — fine outdoors, check the product still reads as the brightest object")
    return out or ["PASS — inside house look"]


def analyse(path):
    workdir = tempfile.mkdtemp()
    try:
        frames = sample_frames(path, workdir)
        if not frames:
            return {"file": os.path.basename(path), "error": "no frames extracted"}
        stats = [frame_stats(p) for p in frames]
        L = [s[0] for s in stats]
        warmth = np.mean([s[1] for s in stats]) / np.mean([s[2] for s in stats])
        sat = np.mean([s[3] for s in stats])
        return {
            "file": os.path.basename(path),
            "luma": round(float(np.mean(L)), 1),
            "luma_sd": round(float(np.std(L)), 1),
            "warmth_rb": round(float(warmth), 2),
            "saturation": round(float(sat), 2),
            "flags": flags(np.mean(L), warmth, sat),
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


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

    print(f"{'file':28s} {'luma':>6s} {'sd':>6s} {'warm':>6s} {'sat':>6s}  flags")
    print("-" * 110)
    for r in results:
        if "error" in r:
            print(f"{r['file']:28s} {r['error']}")
            continue
        print(f"{r['file']:28s} {r['luma']:6.1f} {r['luma_sd']:6.1f} "
              f"{r['warmth_rb']:6.2f} {r['saturation']:6.2f}  {'; '.join(r['flags'])}")

    with open("lighting_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nWrote lighting_report.json")


if __name__ == "__main__":
    main()
