"""Plain data types shared across connectors, storage and jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

CATEGORIES = (
    "client", "lead", "partner", "team", "vendor", "finance",
    "personal", "newsletter", "notification", "spam", "other",
)
PRIORITIES = ("high", "medium", "low")


@dataclass
class EmailMessage:
    source: str            # "gmail" | "outlook"
    external_id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    received_at: datetime  # timezone-aware
    link: str = ""         # open-in-mailbox URL


@dataclass
class Triage:
    category: str
    priority: str
    needs_reply: bool
    summary: str
    suggested_action: str
    create_task: bool = False
    task_title: str = ""
    task_due: str = ""     # Todoist natural language, e.g. "friday", "" for no date


@dataclass
class Draft:
    reply: str
    needs_input: list[str]


@dataclass
class Task:
    id: str
    content: str
    priority: int                 # Todoist: 4 = P1 (highest) ... 1 = P4
    due_date: str | None          # YYYY-MM-DD
    due_datetime: datetime | None  # set only when the task has a time
    url: str = ""

    @property
    def label(self) -> str:
        return f"P{5 - self.priority}"
