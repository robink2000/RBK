"""Settings: secrets come from the environment (.env), everything else from neuranova.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import find_dotenv, load_dotenv

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_MODEL = "claude-opus-5-5"


@dataclass(frozen=True)
class Goal:
    name: str
    measure: str


@dataclass(frozen=True)
class WorkingHours:
    start: time
    end: time
    days: frozenset[int]  # 0 = Monday


@dataclass(frozen=True)
class Settings:
    workspace_id: str
    owner_id: str
    tz: ZoneInfo
    working_hours: WorkingHours
    sla_hours: float
    sla_warn_minutes: int
    sla_categories: frozenset[str]
    goals: tuple[Goal, ...]
    morning_brief: time
    weekly_report_day: str
    weekly_report_time: time
    inbox_check_minutes: int
    sla_check_minutes: int
    task_reminder_minutes: int
    task_reminder_lead_minutes: int
    instant_high_priority: bool
    db_path: Path
    auto_create_tasks: bool = True
    drafts_enabled: bool = True
    reply_signature: str = ""
    reply_tone: str = ""
    draft_lookback_days: int = 3
    max_drafts_per_run: int = 5
    brand: dict = field(default_factory=dict)
    model: str = DEFAULT_MODEL
    env: dict[str, str] = field(default_factory=dict, repr=False)

    def secret(self, name: str) -> str:
        return self.env.get(name, "").strip()


def _parse_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def _color(value, default: str) -> str:
    """Only plain #rgb / #rrggbb colors are accepted; they are written into the page's CSS."""
    import re
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", value) else default


def load_settings(config_path: str | Path | None = None, env: dict[str, str] | None = None) -> Settings:
    if env is None:
        # The .env next to where you run the command (not next to the installed program).
        load_dotenv(find_dotenv(usecwd=True))
        env = dict(os.environ)
    path = Path(config_path or env.get("NEURANOVA_CONFIG") or "neuranova.toml")
    raw = tomllib.loads(path.read_text()) if path.exists() else {}

    ws = raw.get("workspace", {})
    wh = raw.get("working_hours", {})
    sla = raw.get("response_sla", {})
    sched = raw.get("schedule", {})
    alerts = raw.get("alerts", {})
    tasks = raw.get("tasks", {})
    brand = raw.get("brand", {})
    replies = raw.get("replies", {})

    days = wh.get("days", DAY_NAMES[:5])
    return Settings(
        workspace_id=ws.get("id", "neuranova"),
        owner_id=ws.get("owner_id", "owner"),
        tz=ZoneInfo(ws.get("timezone", "UTC")),
        working_hours=WorkingHours(
            start=_parse_time(wh.get("start", "09:00")),
            end=_parse_time(wh.get("end", "18:00")),
            days=frozenset(DAY_NAMES.index(d.lower()[:3]) for d in days),
        ),
        sla_hours=float(sla.get("hours", 4)),
        sla_warn_minutes=int(sla.get("warn_before_minutes", 60)),
        sla_categories=frozenset(sla.get("categories", ["client", "lead", "partner"])),
        goals=tuple(Goal(g["name"], g.get("measure", "")) for g in raw.get("goals", [])),
        morning_brief=_parse_time(sched.get("morning_brief", "08:30")),
        weekly_report_day=sched.get("weekly_report_day", "mon").lower()[:3],
        weekly_report_time=_parse_time(sched.get("weekly_report_time", "09:00")),
        inbox_check_minutes=int(sched.get("inbox_check_minutes", 15)),
        sla_check_minutes=int(sched.get("sla_check_minutes", 15)),
        task_reminder_minutes=int(sched.get("task_reminder_minutes", 10)),
        task_reminder_lead_minutes=int(sched.get("task_reminder_lead_minutes", 30)),
        instant_high_priority=bool(alerts.get("instant_high_priority", True)),
        db_path=Path(env.get("NEURANOVA_DB") or "data/neuranova.db"),
        auto_create_tasks=bool(tasks.get("auto_create_from_email", True)),
        drafts_enabled=bool(replies.get("draft_replies", True)),
        reply_signature=replies.get("signature", "").strip(),
        reply_tone=replies.get("tone", "").strip(),
        draft_lookback_days=int(replies.get("draft_lookback_days", 3)),
        max_drafts_per_run=int(replies.get("max_drafts_per_run", 5)),
        brand={
            "name": brand.get("name", "NeuraNova"),
            "tagline": brand.get("tagline", "Personal Assistant"),
            "accent": _color(brand.get("accent"), "#8705a1"),
            "accent_dark": _color(brand.get("accent_dark"), "#a06ad9"),
            "logo": brand.get("logo", ""),
        },
        model=env.get("NEURANOVA_MODEL") or DEFAULT_MODEL,
        env=env,
    )
