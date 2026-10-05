"""Weekly goal charts shared by the dashboard and the Reports page."""

from __future__ import annotations

from .charts import bar_chart
from .progress import weekly_series


def goal_charts(store, settings, weeks: int = 8) -> dict:
    series = weekly_series(store, settings.tz, weeks=weeks)
    labels = [w["label"] for w in series]
    return {
        "ontime": bar_chart(labels, [w["on_time_pct"] for w in series], percent=True),
        "leads": bar_chart(labels, [w["new_leads"] for w in series]),
        "won": bar_chart(labels, [w["deals_won"] for w in series]),
    }
