from datetime import timezone

import httpx

from conftest import utc
from neuranova.connectors.outlook import OutlookConnector
from neuranova.connectors.todoist import TodoistConnector, localize


def mock(routes):
    def handler(request):
        for path, body in routes.items():
            if request.url.path.endswith(path):
                return httpx.Response(200, json=body)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_todoist_filter_and_due_parsing(settings):
    client = mock({"/tasks/filter": {"results": [
        {"id": "1", "content": "Call investor", "priority": 4, "due": {"date": "2026-10-05T15:00:00Z"}},
        {"id": "2", "content": "Send invoice", "priority": 1, "due": {"date": "2026-10-05"}},
        {"id": "3", "content": "Floating", "priority": 2, "due": {"date": "2026-10-05T09:30:00"}},
    ], "next_cursor": None}})
    tasks = TodoistConnector("t", http=client).today_and_overdue()
    assert [t.label for t in tasks] == ["P1", "P4", "P3"]
    assert localize(tasks[0], settings.tz) == utc(2026, 10, 5, 15)
    assert localize(tasks[1], settings.tz) is None
    assert localize(tasks[2], settings.tz) == utc(2026, 10, 5, 9, 30)


def test_outlook_inbox_and_replies():
    client = mock({
        "/inbox/messages": {"value": [{
            "id": "m1", "conversationId": "c1", "subject": "Proposal",
            "from": {"emailAddress": {"name": "Asha", "address": "asha@client.com"}},
            "bodyPreview": "Can you send the proposal?", "receivedDateTime": "2026-10-05T08:00:00Z",
        }]},
        "/sentitems/messages": {"value": [
            {"conversationId": "c1", "sentDateTime": "2026-10-05T09:00:00Z"},
            {"conversationId": "c1", "sentDateTime": "2026-10-05T10:00:00Z"},
        ]},
    })
    conn = OutlookConnector("tok", http=client)
    [msg] = conn.fetch_inbox(utc(2026, 10, 4))
    assert msg.sender == "Asha <asha@client.com>" and msg.received_at.tzinfo == timezone.utc
    assert conn.latest_replies(utc(2026, 10, 4)) == {"c1": utc(2026, 10, 5, 10)}
