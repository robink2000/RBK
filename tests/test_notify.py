import httpx

from neuranova.notify import WhatsAppNotifier, chunk, flatten_for_template


def test_flatten_removes_newlines_and_long_spaces():
    flat = flatten_for_template("Line one\n\n  - item\tA\nx      y")
    assert "\n" not in flat and "\t" not in flat and "    " not in flat
    assert flat.startswith("Line one | - item A")


def test_chunk_splits_on_separators():
    parts = chunk(" | ".join(["word " * 20] * 20), limit=300)
    assert len(parts) > 1 and all(len(p) <= 300 for p in parts)


def test_whatsapp_sends_template_messages():
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    n = WhatsAppNotifier("tok", "123", "+919999999999", "neuranova_update",
                         http=httpx.Client(transport=httpx.MockTransport(handler)))
    n.send("Hello\nworld")
    assert len(sent) == 1
    body = sent[0].read().decode()
    assert '"to":"919999999999"' in body.replace(" ", "")
    assert "Hello | world" in body
    assert sent[0].headers["authorization"] == "Bearer tok"


def test_free_text_inside_window_and_teaser_outside():
    sent = []
    handler = lambda request: sent.append(request.read().decode()) or httpx.Response(200, json={})
    window = {"open": True}
    n = WhatsAppNotifier("tok", "123", "919999999999", "neuranova_update",
                         http=httpx.Client(transport=httpx.MockTransport(handler)),
                         window_open=lambda: window["open"])
    n.send("Draft #1\nHi Asha", teaser="Draft #1 ready")
    assert '"type":"text"' in sent[0].replace(" ", "") and "Draft #1\\nHi Asha" in sent[0]
    window["open"] = False
    n.send("Draft #1\nHi Asha", teaser="Draft #1 ready")
    assert '"type":"template"' in sent[1].replace(" ", "") and "Draft #1 ready" in sent[1]
    assert "Hi Asha" not in sent[1]
