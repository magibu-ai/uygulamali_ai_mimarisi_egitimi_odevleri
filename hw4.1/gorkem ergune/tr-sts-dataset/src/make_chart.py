# -*- coding: utf-8 -*-
"""Render the score-distribution chart for the GitHub README.
Single ordered series -> sequential blue ramp (light band -> dark band)."""
import os
import csv
import collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---- data ----
rows = []
for fn in ("hf_dataset/train.csv", "hf_dataset/test.csv"):
    with open(fn, encoding="utf-8-sig") as f:
        rows += list(csv.DictReader(f))
bands = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0"]
c = collections.Counter()
for r in rows:
    s = float(r["score"])
    i = min(int(s / 0.2), 4) if s >= 0 else 0
    c[bands[i]] += 1
vals = [c[b] for b in bands]

# ---- palette (dataviz reference: sequential blue, ordinal steps 250..650) ----
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASE = "#c3c2b7"
RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]

plt.rcParams["font.family"] = "DejaVu Sans"
fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

x = range(len(bands))
bars = ax.bar(x, vals, width=0.66, color=RAMP, zorder=3,
              edgecolor=SURFACE, linewidth=1.5)

# value labels on top of bars
for xi, v in zip(x, vals):
    ax.text(xi, v + max(vals) * 0.018, str(v), ha="center", va="bottom",
            color=INK, fontsize=11, fontweight="bold")

# recessive grid + axis
ax.set_axisbelow(True)
ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
ax.set_ylim(0, max(vals) * 1.14)
ax.set_xticks(list(x))
ax.set_xticklabels(bands, color=INK, fontsize=10.5)
ax.tick_params(axis="x", length=0)
ax.tick_params(axis="y", colors=MUTED, labelsize=9)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(BASE)

ax.set_title("Score distribution — 1,037 Turkish sentence pairs",
             color=INK, fontsize=13, fontweight="bold", loc="left", pad=12)
ax.set_xlabel("cosine similarity band", color=MUTED, fontsize=10, labelpad=8)

os.makedirs("assets", exist_ok=True)
out = "assets/score_distribution.png"
fig.tight_layout()
fig.savefig(out, facecolor=SURFACE, bbox_inches="tight")
print("saved", out, "| counts:", dict(zip(bands, vals)))
