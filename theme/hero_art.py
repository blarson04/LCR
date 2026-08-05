"""
hero_art.py: Tier 1 data-as-art for covers, dividers, and site headers (B-7).

Every image here is generated from the frozen edition's real data and the
tokens file — never hand-drawn — so it regenerates correctly at every freeze.
Background art never carries data the reader is expected to read (it is
texture made of truth, not a chart): no axes, no labels, no legends.

Functions return matplotlib Figures; callers save them. Rules baked in:
paper-color linework at 15-25% opacity on divider fields; the gold flag
appears only on speculative surfaces; one motif per image.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow  # noqa: F401  (reserved)

from . import lcr_theme


def _bare_ax(fig):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    return ax


def cover_backdrop(scores, width_in=8.5, height_in=2.6, mode="light"):
    """The full 110-market diverging chart as a quiet band: bars at low
    opacity in pine/clay, no labels, no axes. `scores` is the edition's
    score series in rank order."""
    t = lcr_theme.tokens(mode)
    fig = plt.figure(figsize=(width_in, height_in))
    fig.patch.set_alpha(0.0)
    ax = _bare_ax(fig)
    ax.patch.set_alpha(0.0)
    vals = list(scores)
    colors = [t["pine"] if v >= 0 else t["clay"] for v in vals]
    ax.bar(range(len(vals)), vals, color=colors, alpha=0.28, width=0.82)
    ax.axhline(0, color=t["slate"], linewidth=0.6, alpha=0.35)
    ax.set_xlim(-1, len(vals))
    return fig


def _divider_fig(width_in=8.5, height_in=2.1, mode="light"):
    """A pine field ready for paper-color linework."""
    t = lcr_theme.tokens(mode)
    fig = plt.figure(figsize=(width_in, height_in))
    fig.patch.set_facecolor(t["pine"])
    ax = _bare_ax(fig)
    ax.patch.set_facecolor(t["pine"])
    return fig, ax, t


def divider_top10_ranges(rank_lo, rank_hi, ranks, mode="light"):
    """Key findings divider: the top-10 rank ranges as paper-color interval
    bars with a dot at the point rank."""
    fig, ax, t = _divider_fig(mode=mode)
    n = len(ranks)
    for i in range(n):
        y = n - i
        ax.plot([rank_lo[i], rank_hi[i]], [y, y], color=t["paper"],
                alpha=0.22, linewidth=3.5, solid_capstyle="round")
        ax.plot([ranks[i]], [y], "o", color=t["paper"], alpha=0.30,
                markersize=5)
    ax.set_xlim(0, max(rank_hi) * 1.05)
    ax.set_ylim(0.3, n + 0.7)
    return fig


def divider_weights(weights, mode="light"):
    """Methodology divider: the weight bars (40/25/20/10/5) as a paper-color
    strip."""
    fig, ax, t = _divider_fig(mode=mode)
    x = 0.0
    for w in weights:
        ax.barh([0], [w], left=x, color=t["paper"], alpha=0.20,
                height=0.5, edgecolor=t["paper"], linewidth=0.8)
        x += w + 1.2
    ax.set_xlim(-1, x + 1)
    ax.set_ylim(-1.2, 1.2)
    return fig


def divider_edge_windows(edges, mode="light"):
    """Track record divider: the six-window top-10 edge bars plus the
    freeze-grade rail geometry underneath."""
    fig, ax, t = _divider_fig(mode=mode)
    n = len(edges)
    colors_a = [0.25 if e >= 0 else 0.30 for e in edges]
    for i, e in enumerate(edges):
        ax.bar([i], [e], color=t["paper"], alpha=colors_a[i], width=0.6)
    ax.axhline(0, color=t["paper"], linewidth=0.8, alpha=0.35)
    lo = min(0, min(edges))
    y_rail = lo - (max(edges) - lo) * 0.28
    ax.plot([-0.3, n - 0.7], [y_rail, y_rail], color=t["paper"],
            alpha=0.30, linewidth=1.1)
    ax.plot([-0.3], [y_rail], "o", color=t["paper"], alpha=0.35, markersize=6)
    ax.plot([n - 0.7], [y_rail], "o", markerfacecolor="none",
            markeredgecolor=t["paper"], alpha=0.35, markersize=6,
            markeredgewidth=1.2)
    ax.set_xlim(-0.9, n - 0.1)
    ax.set_ylim(y_rail - abs(y_rail) * 0.4, max(edges) * 1.15)
    return fig


def divider_tier_strip(tiers, mode="light"):
    """Full rankings divider: 110 thin vertical bands colored by tier — a
    legend the reader has seen before the table."""
    t = lcr_theme.tokens(mode)
    scale = lcr_theme.tier_scale(mode)
    order = ["Leading cluster", "Strong", "Mid", "Weak", "Lagging"]
    fig = plt.figure(figsize=(8.5, 2.1))
    fig.patch.set_facecolor(t["pine"])
    ax = _bare_ax(fig)
    ax.patch.set_facecolor(t["pine"])
    for i, tier in enumerate(tiers):
        try:
            c = scale[order.index(tier)]
        except ValueError:
            c = t["tint"]
        ax.bar([i], [1], color=c, width=0.9, alpha=0.85)
    ax.set_xlim(-1, len(tiers))
    ax.set_ylim(0, 1.6)
    return fig


def divider_speculative(mode="light"):
    """Speculative divider: the freeze-grade rail broken/dashed, with the
    gold flag — the only surface where gold appears in art."""
    fig, ax, t = _divider_fig(mode=mode)
    y = 0.5
    ax.plot([0.06, 0.55], [y, y], color=t["paper"], alpha=0.30,
            linewidth=1.6, linestyle=(0, (4, 3)))
    ax.plot([0.60, 0.94], [y, y], color=t["flag"], alpha=0.75,
            linewidth=1.6, linestyle=(0, (2, 3)))
    ax.plot([0.06], [y], "o", color=t["paper"], alpha=0.4, markersize=8)
    ax.plot([0.94], [y], "o", markerfacecolor="none",
            markeredgecolor=t["flag"], markersize=8, markeredgewidth=1.5)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return fig


def band_motif(width_in=8.5, height_in=0.28, mode="light"):
    """Tier 2 texture: the 5-step tier band strip (footer rule, cover
    accent, one-pager spine)."""
    scale = lcr_theme.tier_scale(mode)
    fig = plt.figure(figsize=(width_in, height_in))
    fig.patch.set_alpha(0.0)
    ax = _bare_ax(fig)
    ax.patch.set_alpha(0.0)
    seg = 1.0 / len(scale)
    for i, c in enumerate(scale):
        ax.barh([0], [seg], left=i * seg, color=c, height=1.0)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, 0.5)
    return fig


def save(fig, path, dpi=300, transparent=False):
    # facecolor must be passed explicitly: the report builder sets a global
    # savefig.facecolor (paper) that would otherwise override the pine field.
    fig.savefig(path, dpi=dpi, transparent=transparent,
                facecolor="none" if transparent else fig.get_facecolor(),
                bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    return path
