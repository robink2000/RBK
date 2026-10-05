"""Small server-rendered SVG bar charts for the dashboard (single series, no JS needed).

Follows the dashboard's chart rules: one series per chart (so no legend), thin bars with 4px rounded
data-ends on a baseline, recessive gridlines, a direct label only on the latest bar, a per-bar hover
tooltip (<title>), and a data table alongside for accessibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

W, H = 440, 190
LEFT, RIGHT, TOP, BOTTOM = 36, 6, 18, 24


@dataclass
class Bar:
    x: float
    y: float
    w: float
    h: float
    label: str
    value: float | None
    tip: str
    path: str


def _nice_max(values: list[float]) -> float:
    top = max([v for v in values if v is not None] or [0])
    if top <= 4:
        return 4
    step = 10 ** (len(str(int(top))) - 1)
    return ceil(top / step) * step


def _rounded_top(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Bar path with rounded top corners and a square base sitting on the baseline."""
    r = min(r, w / 2, h)
    return (f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
            f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z")


def bar_chart(labels: list[str], values: list[float | None], *, percent: bool = False, unit: str = "") -> dict:
    vmax = 100 if percent else _nice_max(values)
    plot_w, plot_h = W - LEFT - RIGHT, H - TOP - BOTTOM
    slot = plot_w / max(len(values), 1)
    bar_w = min(24, slot * 0.6)
    bars = []
    for i, (label, value) in enumerate(zip(labels, values)):
        x = LEFT + i * slot + (slot - bar_w) / 2
        h = 0 if value is None else max(plot_h * value / vmax, 2)  # 0 still shows a thin stub
        y = TOP + plot_h - h
        shown = "no data" if value is None else (f"{value:g}%" if percent else f"{value:g}{unit}")
        bars.append(Bar(x, y, bar_w, h, label, value, f"Week of {label}: {shown}",
                        _rounded_top(x, y, bar_w, h) if h else ""))
    grid = [{"y": TOP + plot_h - plot_h * f, "label": f"{vmax * f:g}{'%' if percent else ''}"}
            for f in (0, 0.5, 1)]
    last = next((b for b in reversed(bars) if b.value is not None), None)
    return {"w": W, "h": H, "bars": bars, "grid": grid, "last": last, "base_y": TOP + plot_h,
            "left": LEFT, "right": W - RIGHT, "percent": percent}
