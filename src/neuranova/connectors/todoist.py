"""Todoist (API v1). Todoist is the single source of truth for tasks."""

from __future__ import annotations

from datetime import datetime

import httpx

from ..models import Task

API = "https://api.todoist.com/api/v1"


def _task(raw: dict) -> Task:
    due = raw.get("due") or {}
    due_dt = None
    date_value = due.get("date")
    # API v1 puts the full timestamp in `date` for timed tasks; older payloads used `datetime`.
    stamp = due.get("datetime") or (date_value if date_value and "T" in date_value else None)
    if stamp:
        # Naive result = "floating" time, interpreted in the workspace timezone by localize().
        due_dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return Task(
        id=str(raw["id"]),
        content=raw.get("content", ""),
        priority=int(raw.get("priority", 1)),
        due_date=date_value[:10] if date_value else None,
        due_datetime=due_dt,
        url=raw.get("url") or f"https://app.todoist.com/app/task/{raw['id']}",
    )


class TodoistConnector:
    def __init__(self, token: str, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=30)
        self.headers = {"Authorization": f"Bearer {token}"}

    def filter(self, query: str) -> list[Task]:
        tasks, cursor = [], None
        while True:
            params = {"query": query, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            resp = self.http.get(f"{API}/tasks/filter", params=params, headers=self.headers)
            resp.raise_for_status()
            body = resp.json()
            tasks.extend(_task(t) for t in body.get("results", []))
            cursor = body.get("next_cursor")
            if not cursor:
                return tasks

    def today_and_overdue(self) -> list[Task]:
        return self.filter("today | overdue")

    def add_task(self, content: str, description: str = "", due_string: str = "", priority: int = 1) -> Task:
        payload = {"content": content, "description": description, "priority": priority}
        if due_string:
            payload["due_string"] = due_string
        resp = self.http.post(f"{API}/tasks", json=payload, headers=self.headers)
        resp.raise_for_status()
        return _task(resp.json())


    def close_task(self, task_id: str) -> None:
        resp = self.http.post(f"{API}/tasks/{task_id}/close", headers=self.headers)
        resp.raise_for_status()


def localize(task: Task, tz) -> datetime | None:
    """Timed tasks as an aware datetime in `tz` (floating times are taken as local)."""
    if task.due_datetime is None:
        return None
    if task.due_datetime.tzinfo is None:
        return task.due_datetime.replace(tzinfo=tz)
    return task.due_datetime.astimezone(tz)
