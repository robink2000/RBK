import base64
from email import message_from_bytes

from neuranova.connectors.gmail import GmailConnector, extract_text


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_extract_prefers_plain_and_falls_back_to_html():
    payload = {"mimeType": "multipart/alternative", "parts": [
        {"mimeType": "text/html", "body": {"data": b64("<p>Hi</p>")}},
        {"mimeType": "text/plain", "body": {"data": b64("Hi there")}},
    ]}
    assert extract_text(payload) == "Hi there"
    html_only = {"mimeType": "text/html", "body": {"data": b64("<style>x</style><p>Hello&amp;bye</p><br><br><br>Line")}}
    assert extract_text(html_only) == "Hello&bye\n\nLine"


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeMessages:
    def __init__(self):
        self.sent = None

    def get(self, **kw):
        return FakeRequest({"threadId": "T1", "payload": {"headers": [
            {"name": "From", "value": "Asha <asha@acme.com>"},
            {"name": "Subject", "value": "Proposal"},
            {"name": "Message-ID", "value": "<abc@acme.com>"},
        ]}})

    def send(self, userId, body):
        self.sent = body
        return FakeRequest({"id": "S1"})


def test_send_reply_threads_correctly():
    msgs = FakeMessages()
    service = type("S", (), {"users": lambda self: type("U", (), {"messages": lambda self: msgs})()})()
    assert GmailConnector("unused", service=service).send_reply("M1", "Hi Asha,\nSure.") == "S1"
    assert msgs.sent["threadId"] == "T1"
    mime = message_from_bytes(base64.urlsafe_b64decode(msgs.sent["raw"]))
    assert mime["To"] == "Asha <asha@acme.com>"
    assert mime["Subject"] == "Re: Proposal"
    assert mime["In-Reply-To"] == "<abc@acme.com>" and mime["References"] == "<abc@acme.com>"
    assert mime.get_payload(decode=True).decode().strip() == "Hi Asha,\nSure."
