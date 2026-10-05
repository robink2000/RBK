import email
import email.policy
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from neuranova import integrations as integ
from neuranova.connectors.imap import ImapConnector, detect, thread_key
from neuranova.server import create_app
from test_team import make_team

NOW = datetime.now(timezone.utc)


def raw(msg_id, sender, to, subject, body, when, refs=None):
    m = email.message.EmailMessage()
    m["Message-ID"], m["From"], m["To"], m["Subject"] = msg_id, sender, to, subject
    m["Date"] = format_datetime(when)
    if refs:
        m["In-Reply-To"], m["References"] = refs[-1], " ".join(refs)
    m.set_content(body)
    return m.as_bytes()


class FakeIMAP:
    """Just enough of imaplib.IMAP4_SSL for the connector."""

    def __init__(self, folders, password="app-pass", flag_sent=True):
        self.folders, self.password, self.flag_sent = folders, password, flag_sent
        self.selected, self.appended = None, []

    def login(self, user, password):
        if password != self.password:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")

    def logout(self):
        pass

    def list(self):
        lines = []
        for name in self.folders:
            flags = "\\HasNoChildren \\Sent" if (self.flag_sent and name.lower().startswith("sent")) else "\\HasNoChildren"
            lines.append(f'({flags}) "/" "{name}"'.encode())
        return "OK", lines

    def select(self, folder, readonly=False):
        name = folder.strip('"')
        if name not in self.folders:
            return "NO", [b"no such folder"]
        self.selected = name
        return "OK", [str(len(self.folders[name])).encode()]

    def uid(self, command, *args):
        box = self.folders[self.selected]
        if command == "SEARCH":
            if "HEADER" in args:
                wanted = args[-1]
                hits = [str(i + 1) for i, m in enumerate(box) if wanted.encode() in m]
                return "OK", [" ".join(hits).encode()]
            return "OK", [" ".join(str(i + 1) for i in range(len(box))).encode()]
        if command == "FETCH":
            data = box[int(args[0]) - 1]
            if "RFC822.SIZE" in args[1]:
                return "OK", [f"{args[0]} (RFC822.SIZE {len(data)})".encode()]
            if "HEADER" in args[1]:
                data = data.split(b"\n\n", 1)[0] + b"\n\n"
            return "OK", [(f"{args[0]} (BODY[] {{{len(data)}}}".encode(), data), b")"]
        raise AssertionError(command)

    def append(self, folder, flags, when, message):
        self.appended.append((folder.strip('"'), message))
        self.folders[folder.strip('"')].append(message)


class FakeSMTP:
    def __init__(self, password="app-pass"):
        self.password, self.sent = password, []

    def login(self, user, password):
        import smtplib
        if password != self.password:
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        pass


def mailbox():
    first = raw("<q1@acme.example>", "Asha Rao <asha@acme.example>", "me@neuranova.in", "Quote for 3 months",
                "Hi, what would 3 months cost?", NOW - timedelta(hours=2))
    other = raw("<n1@news.example>", "News <n@news.example>", "me@neuranova.in", "Weekly digest", "Hello",
                NOW - timedelta(hours=1))
    old = raw("<old@x.example>", "Old <o@x.example>", "me@neuranova.in", "Ancient", "x", NOW - timedelta(days=30))
    reply = raw("<r1@neuranova.in>", "me@neuranova.in", "asha@acme.example", "Re: Quote for 3 months", "Sure",
                NOW - timedelta(minutes=30), refs=["<q1@acme.example>"])
    return {"INBOX": [first, other, old], "Sent": [reply]}


def connector(folders=None, provider="zoho_in", **kw):
    fake = FakeIMAP(folders or mailbox(), **kw)
    smtp = FakeSMTP()
    conn = ImapConnector("me@neuranova.in", "app-pass", "imap.zoho.in", 993, "smtp.zoho.in", 465, provider,
                         imap_factory=lambda h, p: fake, smtp_factory=lambda h, p: smtp)
    return conn, fake, smtp


def test_detect_known_domains_and_mx():
    assert detect("you@gmail.com")["imap_host"] == "imap.gmail.com"

    def dns(request):
        name = request.url.params["name"]
        mx = {"neuranova.in": "10 aspmx.l.google.com.", "shop.in": "10 mx.zoho.in.",
              "biz.in": "10 mx1.hostinger.com."}.get(name)
        return httpx.Response(200, json={"Answer": [{"type": 15, "data": mx}]} if mx else {})

    http = httpx.Client(transport=httpx.MockTransport(dns))
    assert detect("robin@neuranova.in", http)["provider"] == "google"
    assert detect("a@shop.in", http)["smtp_host"] == "smtp.zoho.in"
    assert detect("a@biz.in", http)["imap_host"] == "imap.hostinger.com"
    unknown = detect("a@mystery.example", http)
    assert unknown["known"] is False and unknown["imap_host"] == "imap.mystery.example"


def test_inbox_threads_and_replies():
    conn, _, _ = connector()
    inbox = conn.fetch_inbox(NOW - timedelta(days=2))
    assert [m.subject for m in inbox] == ["Quote for 3 months", "Weekly digest"]   # old mail skipped
    quote = inbox[0]
    assert quote.external_id == "<q1@acme.example>" and quote.thread_id == "<q1@acme.example>"
    assert "3 months cost" in quote.snippet and quote.source == "email"
    assert conn.latest_replies(NOW - timedelta(days=2)) == {"<q1@acme.example>": pytest.approx(
        NOW - timedelta(minutes=30), abs=timedelta(seconds=1))}


def test_send_reply_threads_and_saves_copy():
    conn, fake, smtp = connector()
    msg_id = conn.send_reply("<q1@acme.example>", "Hi Asha,\nIt's 50,000.\nBest")
    [sent] = smtp.sent
    assert sent["To"] == "Asha Rao <asha@acme.example>" and sent["Subject"] == "Re: Quote for 3 months"
    assert sent["In-Reply-To"] == "<q1@acme.example>" and sent["References"] == "<q1@acme.example>"
    assert sent["Message-ID"] == msg_id and "50,000" in sent.get_content()
    assert fake.appended and fake.appended[0][0] == "Sent"                        # copy kept in Sent
    reparsed = email.message_from_bytes(fake.appended[0][1], policy=email.policy.default)
    assert thread_key(reparsed) == "<q1@acme.example>"                            # counts as a reply


def test_gmail_does_not_double_save_sent():
    conn, fake, _ = connector({"INBOX": mailbox()["INBOX"], "[Gmail]/Sent Mail": []}, provider="google",
                              flag_sent=False)
    conn.send_reply("<q1@acme.example>", "Thanks")
    assert fake.appended == []


def test_check_reports_plain_errors():
    conn, _, _ = connector()
    assert conn.check().startswith("Reading and sending work. 3 messages")
    bad = ImapConnector("me@neuranova.in", "wrong", "imap.zoho.in", imap_factory=lambda h, p: FakeIMAP(mailbox()))
    with pytest.raises(RuntimeError, match="rejected the address or app password"):
        bad.check()


def test_wizard_flow_in_the_console(tmp_path, monkeypatch):
    settings, store, agent, *_ = make_team(tmp_path)
    client = TestClient(create_app(settings, lambda: agent, store=store))
    client.post("/login", data={"email": "robin@neuranova.ai", "password": "founder-password-1"})
    page = client.get("/integrations").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    assert "Your email address" in page and "Recommended" in page and "0 of 4 connected" in page

    monkeypatch.setattr("neuranova.connectors.imap.mx_hosts", lambda domain, http=None: ["aspmx.l.google.com."])
    resp = client.post("/integrations/email/detect", data={"csrf": csrf, "address": "robin@neuranova.in"},
                       follow_redirects=False)
    assert "Found Google" in resp.headers["location"].replace("%20", " ")
    page = client.get("/integrations").text
    assert "Detected: <strong>Google (Gmail / Workspace)</strong>" in page
    assert "https://myaccount.google.com/apppasswords" in page and 'value="imap.gmail.com"' in page

    monkeypatch.setattr(integ, "test_integration", lambda name, s, store: (True, "Reading and sending work.",
                                                                           s.secret("EMAIL_ADDRESS")))
    resp = client.post("/integrations/email/save", data={
        "csrf": csrf, "EMAIL_ADDRESS": "robin@neuranova.in", "EMAIL_PROVIDER": "google",
        "EMAIL_APP_PASSWORD": "abcd efgh ijkl mnop", "EMAIL_IMAP_HOST": "imap.gmail.com", "EMAIL_IMAP_PORT": "993",
        "EMAIL_SMTP_HOST": "smtp.gmail.com", "EMAIL_SMTP_PORT": "465"}, follow_redirects=False)
    assert "Reading and sending work" in resp.headers["location"].replace("%20", " ")
    page = client.get("/integrations").text
    assert "1 of 4 connected" in page and "abcd efgh" not in page
    merged = integ.with_integrations(settings, store)
    assert integ.email_connector(merged).password == "abcdefghijklmnop"          # spaces removed
    bad = client.post("/integrations/email/detect", data={"csrf": csrf, "address": "nope"}, follow_redirects=False)
    assert "full email address" in bad.headers["location"].replace("%20", " ")
