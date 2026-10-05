from datetime import datetime, timezone

import pytest

from neuranova.config import load_settings
from neuranova.db import Store


@pytest.fixture
def settings(tmp_path):
    cfg = tmp_path / "neuranova.toml"
    cfg.write_text("""
[workspace]
timezone = "UTC"
[working_hours]
start = "09:00"
end = "18:00"
days = ["mon", "tue", "wed", "thu", "fri"]
[response_sla]
hours = 4
warn_before_minutes = 60
[[goals]]
name = "Give proper responses"
measure = "Reply within SLA"
""")
    return load_settings(cfg, env={"NEURANOVA_DB": ":memory:"})


@pytest.fixture
def store(settings):
    return Store(":memory:", settings.workspace_id, settings.owner_id)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)
