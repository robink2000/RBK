"""Any mailbox with an email address and an app password (IMAP to read, SMTP to send).

Works with Google (Gmail and Workspace), Outlook.com, Zoho, Hostinger, GoDaddy and most other
hosts. Server settings are filled in from the address: known domains first, then the domain's
MX records (looked up over DNS-over-HTTPS), then a sensible guess the user can edit.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import re
import smtplib
import ssl
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage as MimeMessage
from email.utils import getaddresses, make_msgid, parsedate_to_datetime

import httpx

from ..models import EmailMessage

FETCH_LIMIT = 100
MAX_FULL_SIZE = 2_000_000  # bigger messages (attachments) are read header-only


# --- providers ---------------------------------------------------------------------

@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int           # 465 = SSL, 587 = STARTTLS
    app_password_url: str
    steps: tuple[str, ...]
    sent_folder: str = ""
    saves_sent: bool = False  # the provider files SMTP-sent mail into Sent by itself


PROVIDERS = {
    "google": Provider(
        "google", "Google (Gmail / Workspace)", "imap.gmail.com", 993, "smtp.gmail.com", 465,
        "https://myaccount.google.com/apppasswords",
        ("Make sure 2-Step Verification is on for your Google account.",
         "Open the App passwords page, type NeuraNova as the name, and press Create.",
         "Copy the 16-letter password Google shows and paste it below."),
        sent_folder="[Gmail]/Sent Mail", saves_sent=True),
    "microsoft": Provider(
        "microsoft", "Microsoft (Outlook.com / Hotmail)", "outlook.office365.com", 993, "smtp-mail.outlook.com", 587,
        "https://account.live.com/proofs/AppPassword",
        ("Make sure two-step verification is on for your Microsoft account.",
         "Open the App passwords page and choose Create a new app password.",
         "Copy the password and paste it below. (Work Microsoft 365 accounts usually need "
         "Connect with Microsoft instead.)"),
        sent_folder="Sent"),
    "zoho_in": Provider(
        "zoho_in", "Zoho Mail (India)", "imap.zoho.in", 993, "smtp.zoho.in", 465,
        "https://accounts.zoho.in/home#security/app_password",
        ("In Zoho Mail settings, make sure IMAP access is on.",
         "Open App passwords, generate one named NeuraNova.", "Copy it and paste it below."),
        sent_folder="Sent"),
    "zoho": Provider(
        "zoho", "Zoho Mail", "imap.zoho.com", 993, "smtp.zoho.com", 465,
        "https://accounts.zoho.com/home#security/app_password",
        ("In Zoho Mail settings, make sure IMAP access is on.",
         "Open App passwords, generate one named NeuraNova.", "Copy it and paste it below."),
        sent_folder="Sent"),
    "hostinger": Provider(
        "hostinger", "Hostinger Email", "imap.hostinger.com", 993, "smtp.hostinger.com", 465,
        "https://hpanel.hostinger.com/emails",
        ("Use the same password you use for webmail (Hostinger has no app passwords).",
         "Paste it below."), sent_folder="Sent"),
    "godaddy": Provider(
        "godaddy", "GoDaddy Email", "imap.secureserver.net", 993, "smtpout.secureserver.net", 465,
        "https://email.godaddy.com/",
        ("Use your GoDaddy email password.", "Paste it below."), sent_folder="Sent Items"),
    "yahoo": Provider(
        "yahoo", "Yahoo Mail", "imap.mail.yahoo.com", 993, "smtp.mail.yahoo.com", 465,
        "https://login.yahoo.com/account/security/app-passwords",
        ("Open App passwords in your Yahoo account security page.", "Generate one named NeuraNova.",
         "Paste it below."), sent_folder="Sent"),
    "icloud": Provider(
        "icloud", "iCloud Mail", "imap.mail.me.com", 993, "smtp.mail.me.com", 587,
        "https://account.apple.com/account/manage",
        ("Sign in to your Apple Account, open Sign-In and Security → App-Specific Passwords.",
         "Create one named NeuraNova and paste it below."), sent_folder="Sent Messages"),
}

DOMAINS = {
    "gmail.com": "google", "googlemail.com": "google",
    "outlook.com": "microsoft", "hotmail.com": "microsoft", "live.com": "microsoft", "msn.com": "microsoft",
    "outlook.in": "microsoft", "hotmail.co.in": "microsoft", "live.in": "microsoft",
    "zoho.com": "zoho", "zohomail.com": "zoho", "zoho.in": "zoho_in", "zohomail.in": "zoho_in",
    "yahoo.com": "yahoo", "yahoo.in": "yahoo", "yahoo.co.in": "yahoo", "ymail.com": "yahoo",
    "icloud.com": "icloud", "me.com": "icloud", "mac.com": "icloud",
}

MX_PATTERNS = [
    (r"(google\.com|googlemail\.com)\.?$", "google"),
    (r"(outlook\.com|protection\.outlook\.com)\.?$", "microsoft"),
    (r"zoho\.in\.?$", "zoho_in"),
    (r"zoho\.(com|eu)\.?$", "zoho"),
    (r"hostinger\.(com|in)\.?$", "hostinger"),
    (r"secureserver\.net\.?$", "godaddy"),
    (r"yahoodns\.net\.?$", "yahoo"),
    (r"icloud\.com\.?$", "icloud"),
]


def mx_hosts(domain: str, http: httpx.Client | None = None) -> list[str]:
    """MX hostnames via DNS-over-HTTPS (no extra DNS library needed). Empty on any failure."""
    try:
        client = http or httpx.Client(timeout=6)
        resp = client.get("https://dns.google/resolve", params={"name": domain, "type": "MX"})
        answers = resp.json().get("Answer", [])
        return [a["data"].split()[-1].lower() for a in answers if a.get("type") == 15]
    except Exception:
        return []


def detect(address: str, http: httpx.Client | None = None) -> dict:
    """Server settings for an address: {"provider", "name", imap/smtp host+port, "known"}."""
    domain = address.rsplit("@", 1)[-1].strip().lower()
    key = DOMAINS.get(domain)
    if not key:
        for host in mx_hosts(domain, http):
            key = next((k for pattern, k in MX_PATTERNS if re.search(pattern, host)), None)
            if key:
                break
    if key:
        p = PROVIDERS[key]
        return {"provider": key, "name": p.name, "imap_host": p.imap_host, "imap_port": p.imap_port,
                "smtp_host": p.smtp_host, "smtp_port": p.smtp_port, "known": True}
    return {"provider": "other", "name": f"Your mail host ({domain})", "imap_host": f"imap.{domain}",
            "imap_port": 993, "smtp_host": f"smtp.{domain}", "smtp_port": 465, "known": False}


# --- helpers ------------------------------------------------------------------------

def _decode(value) -> str:
    return str(value or "").strip()


def thread_key(msg) -> str:
    """Same key for a message and the replies to it: the first Message-ID in its reference chain."""
    refs = re.findall(r"<[^>]+>", _decode(msg.get("References")))
    if refs:
        return refs[0]
    reply_to = re.findall(r"<[^>]+>", _decode(msg.get("In-Reply-To")))
    if reply_to:
        return reply_to[0]
    return _decode(msg.get("Message-ID")) or ""


def plain_text(msg) -> str:
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
    except Exception:
        part = None
    if part is None:
        return ""
    text = part.get_content() if hasattr(part, "get_content") else ""
    if part.get_content_type() == "text/html":
        text = re.sub(r"(?is)<(script|style).*?</\1>", "", text)
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", text)
        import html as _html
        text = _html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _when(msg, fallback: datetime) -> datetime:
    try:
        dt = parsedate_to_datetime(_decode(msg.get("Date")))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return fallback


# --- connector ------------------------------------------------------------------------

class ImapConnector:
    name = "email"

    def __init__(self, address: str, password: str, imap_host: str, imap_port: int = 993,
                 smtp_host: str = "", smtp_port: int = 465, provider: str = "other",
                 imap_factory=None, smtp_factory=None):
        self.address, self.password = address, password
        self.imap_host, self.imap_port = imap_host, int(imap_port)
        self.smtp_host, self.smtp_port = smtp_host, int(smtp_port)
        self.provider = PROVIDERS.get(provider)
        self._imap_factory = imap_factory or (lambda h, p: imaplib.IMAP4_SSL(h, p, ssl_context=ssl.create_default_context(), timeout=30))
        self._smtp_factory = smtp_factory

    # IMAP --------------------------------------------------------------------------
    def _imap(self):
        conn = self._imap_factory(self.imap_host, self.imap_port)
        conn.login(self.address, self.password)
        return conn

    def _sent_folder(self, conn) -> str:
        typ, boxes = conn.list()
        names = []
        for raw in boxes or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
            match = re.search(r'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$', line)
            if not match:
                continue
            name = match.group("name").strip().strip('"')
            if "\\Sent" in match.group("flags"):
                return name
            names.append(name)
        preferred = [self.provider.sent_folder] if self.provider and self.provider.sent_folder else []
        for candidate in preferred + ["Sent", "Sent Items", "Sent Messages", "Sent Mail", "INBOX.Sent", "[Gmail]/Sent Mail"]:
            if candidate in names:
                return candidate
        return ""

    def _fetch(self, conn, folder: str, since: datetime, full: bool) -> list[tuple[str, object]]:
        typ, _ = conn.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            return []
        typ, data = conn.uid("SEARCH", None, "SINCE", (since - timedelta(days=1)).strftime("%d-%b-%Y"))
        uids = (data[0] or b"").split()[-FETCH_LIMIT:] if typ == "OK" and data else []
        out = []
        for uid in uids:
            uid_s = uid.decode()
            part = "BODY.PEEK[]" if full else "BODY.PEEK[HEADER]"
            if full:
                typ, size_data = conn.uid("FETCH", uid_s, "(RFC822.SIZE)")
                match = re.search(rb"RFC822\.SIZE (\d+)", size_data[0] if size_data and size_data[0] else b"")
                if match and int(match.group(1)) > MAX_FULL_SIZE:
                    part = "BODY.PEEK[HEADER]"
            typ, msg_data = conn.uid("FETCH", uid_s, f"({part})")
            raw = next((item[1] for item in msg_data or [] if isinstance(item, tuple)), None)
            if raw:
                out.append((uid_s, email.message_from_bytes(raw, policy=email.policy.default)))
        return out

    def fetch_inbox(self, since: datetime) -> list[EmailMessage]:
        conn = self._imap()
        try:
            messages = self._fetch(conn, "INBOX", since, full=True)
        finally:
            conn.logout()
        own = self.address.lower()
        out = []
        for uid, msg in messages:
            received = _when(msg, datetime.now(timezone.utc))
            senders = [a.lower() for _, a in getaddresses([_decode(msg.get("From"))])]
            if received < since or own in senders:
                continue
            message_id = _decode(msg.get("Message-ID")) or f"<uid-{uid}@{self.imap_host}>"
            out.append(EmailMessage(
                source=self.name, external_id=message_id, thread_id=thread_key(msg) or message_id,
                sender=_decode(msg.get("From")), subject=_decode(msg.get("Subject")) or "(no subject)",
                snippet=plain_text(msg)[:1500], received_at=received,
            ))
        return out

    def latest_replies(self, since: datetime) -> dict[str, datetime]:
        conn = self._imap()
        try:
            folder = self._sent_folder(conn)
            messages = self._fetch(conn, folder, since, full=False) if folder else []
        finally:
            conn.logout()
        replies: dict[str, datetime] = {}
        for _, msg in messages:
            key = thread_key(msg)
            if not key:
                continue
            at = _when(msg, since)
            if key not in replies or at > replies[key]:
                replies[key] = at
        return replies

    def _find(self, conn, message_id: str):
        conn.select('"INBOX"', readonly=True)
        typ, data = conn.uid("SEARCH", None, "HEADER", "Message-ID", message_id)
        uids = (data[0] or b"").split() if typ == "OK" and data else []
        if not uids:
            return None
        typ, msg_data = conn.uid("FETCH", uids[-1].decode(), "(BODY.PEEK[])")
        raw = next((item[1] for item in msg_data or [] if isinstance(item, tuple)), None)
        return email.message_from_bytes(raw, policy=email.policy.default) if raw else None

    def fetch_body(self, external_id: str) -> str:
        conn = self._imap()
        try:
            msg = self._find(conn, external_id)
        finally:
            conn.logout()
        return plain_text(msg) if msg is not None else ""

    # SMTP -----------------------------------------------------------------------------
    def _smtp(self):
        if self._smtp_factory:
            server = self._smtp_factory(self.smtp_host, self.smtp_port)
        elif self.smtp_port == 465:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ssl.create_default_context(), timeout=30)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
            server.starttls(context=ssl.create_default_context())
        server.login(self.address, self.password)
        return server

    def send_reply(self, external_id: str, body: str) -> str:
        conn = self._imap()
        try:
            original = self._find(conn, external_id)
            if original is None:
                raise RuntimeError("The original email is no longer in the inbox, so the reply can't be threaded.")
            subject = _decode(original.get("Subject"))
            reply = MimeMessage()
            reply["From"] = self.address
            reply["To"] = _decode(original.get("Reply-To")) or _decode(original.get("From"))
            reply["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
            reply["Message-ID"] = make_msgid(domain=self.address.rsplit("@", 1)[-1])
            reply["In-Reply-To"] = external_id
            reply["References"] = f"{_decode(original.get('References'))} {external_id}".strip()
            reply["Date"] = email.utils.formatdate(localtime=True)
            reply.set_content(body)
            server = self._smtp()
            try:
                server.send_message(reply)
            finally:
                server.quit()
            if not (self.provider and self.provider.saves_sent):
                folder = self._sent_folder(conn)
                if folder:  # keep a copy in Sent, like a normal mail app
                    conn.append(f'"{folder}"', "\\Seen", imaplib.Time2Internaldate(datetime.now(timezone.utc)),
                                reply.as_bytes())
        finally:
            conn.logout()
        return reply["Message-ID"]

    def send_new(self, to: str, subject: str, body: str) -> str:
        msg = MimeMessage()
        msg["From"], msg["To"], msg["Subject"] = self.address, to, subject
        msg["Message-ID"] = make_msgid(domain=self.address.rsplit("@", 1)[-1])
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.set_content(body)
        server = self._smtp()
        try:
            server.send_message(msg)
        finally:
            server.quit()
        if not (self.provider and self.provider.saves_sent):
            conn = self._imap()
            try:
                folder = self._sent_folder(conn)
                if folder:
                    conn.append(f'"{folder}"', "\\Seen", imaplib.Time2Internaldate(datetime.now(timezone.utc)),
                                msg.as_bytes())
            finally:
                conn.logout()
        return msg["Message-ID"]

    # check ------------------------------------------------------------------------------
    def check(self) -> str:
        """Log in to both servers. Returns a short description; raises with a plain message on failure."""
        try:
            conn = self._imap()
        except imaplib.IMAP4.error as exc:
            raise RuntimeError("The email server rejected the address or app password.") from exc
        except OSError as exc:
            raise RuntimeError(f"Couldn't reach the incoming mail server {self.imap_host}:{self.imap_port}.") from exc
        try:
            typ, data = conn.select('"INBOX"', readonly=True)
            count = int(data[0]) if typ == "OK" and data and data[0] else 0
            sent = self._sent_folder(conn)
        finally:
            conn.logout()
        try:
            self._smtp().quit()
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError("Reading works, but the outgoing server rejected the app password.") from exc
        except OSError as exc:
            raise RuntimeError(f"Reading works, but couldn't reach the outgoing server {self.smtp_host}:{self.smtp_port}.") from exc
        return f"Reading and sending work. {count} messages in the inbox" + ("." if sent else "; no Sent folder found.")


def provider_dict(key: str) -> dict:
    p = PROVIDERS.get(key)
    return asdict(p) if p else {}
