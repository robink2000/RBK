"""Integrations: connect Gmail, Outlook, Todoist, WhatsApp and Claude from the console.

Keys and sign-in tokens entered in the console are stored encrypted in the database (Fernet,
key derived from DASHBOARD_SECRET) and merged into the agent's settings at run time. A value
set in .env always wins and shows as "set in .env" in the console.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass, field, replace
from urllib.parse import urlparse

import httpx

from .db import Store, row_dt

log = logging.getLogger(__name__)

OAUTH_STATE_SECONDS = 15 * 60


# --- catalog ------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    key: str            # setting name, e.g. TODOIST_API_TOKEN
    label: str
    secret: bool = False
    help: str = ""
    placeholder: str = ""
    required: bool = True


@dataclass(frozen=True)
class Integration:
    name: str
    title: str
    category: str
    summary: str
    unlocks: tuple[str, ...]
    fields: tuple[Field, ...] = ()
    oauth: str = ""       # "google" | "microsoft" for a Connect button
    steps: tuple[str, ...] = ()
    links: tuple[tuple[str, str], ...] = ()
    token_key: str = ""   # setting that holds the OAuth sign-in
    extra: dict = field(default_factory=dict)


CATALOG: tuple[Integration, ...] = (
    Integration(
        "email", "Email", "Email",
        "Your business inbox. Type your address, paste an app password, done. Works with Google, "
        "Outlook.com, Zoho, Hostinger, GoDaddy and most other mail hosts.",
        ("Inbox triage", "4-hour reply tracking", "Reply drafts"),
        fields=(Field("EMAIL_ADDRESS", "Email address", placeholder="you@neuranova.in"),
                Field("EMAIL_APP_PASSWORD", "App password", secret=True),
                Field("EMAIL_IMAP_HOST", "Incoming server (IMAP)"),
                Field("EMAIL_IMAP_PORT", "Port", placeholder="993"),
                Field("EMAIL_SMTP_HOST", "Outgoing server (SMTP)"),
                Field("EMAIL_SMTP_PORT", "Port", placeholder="465"),
                Field("EMAIL_PROVIDER", "Provider", required=False)),
        extra={"wizard": True},
    ),
    Integration(
        "claude", "Claude", "AI",
        "The brain of the agent: sorts email, drafts replies, writes briefs and answers chat.",
        ("Email triage", "Reply drafts", "Morning brief", "Chat"),
        fields=(Field("ANTHROPIC_API_KEY", "API key", secret=True, placeholder="sk-ant-..."),),
        steps=("Open the Claude Console and sign in.", "Go to API Keys and create a key named NeuraNova.",
               "Paste it here and press Save & test.", "Set a monthly spend limit under Billing."),
        links=(("Claude Console", "https://console.anthropic.com/settings/keys"),),
    ),
    Integration(
        "openai", "OpenAI", "AI",
        "An alternative AI for the PA. Use it instead of Claude if you prefer.",
        ("Email triage", "Reply drafts", "Briefings", "Chat"),
        fields=(Field("OPENAI_API_KEY", "API key", secret=True, placeholder="sk-..."),
                Field("OPENAI_MODEL", "Model", placeholder="gpt-4.1",
                      help="The model name from your OpenAI account, e.g. gpt-4.1. Test checks it exists.")),
        steps=("Open the OpenAI platform and sign in.", "Go to API keys and create a key named NeuraNova.",
               "Paste it here with the model name and press Save & test.",
               "Choose which AI the PA uses with the switch above the AI cards."),
        links=(("OpenAI API keys", "https://platform.openai.com/api-keys"),),
    ),
    Integration(
        "gmail", "Gmail with Google sign-in", "Email (advanced)",
        "Only if your company turned off app passwords. Needs a one-time app on Google Cloud.",
        ("Inbox triage", "4-hour reply tracking", "Reply drafts"),
        fields=(Field("GOOGLE_CLIENT_ID", "Google client ID", placeholder="1234-abc.apps.googleusercontent.com"),
                Field("GOOGLE_CLIENT_SECRET", "Google client secret", secret=True)),
        oauth="google", token_key="GMAIL_TOKEN_JSON",
        steps=("In Google Cloud, create a project and enable the Gmail API.",
               "Set up the OAuth consent screen and add your address as a test user.",
               "Create credentials → OAuth client ID → Web application, and add the redirect URI shown here.",
               "Paste the client ID and secret here, save, then press Connect with Google."),
        links=(("Google Cloud credentials", "https://console.cloud.google.com/apis/credentials"),
               ("Enable Gmail API", "https://console.cloud.google.com/apis/library/gmail.googleapis.com")),
    ),
    Integration(
        "outlook", "Microsoft 365 with Microsoft sign-in", "Email (advanced)",
        "For work Microsoft 365 mailboxes, which usually block app passwords.",
        ("Inbox triage", "4-hour reply tracking", "Reply drafts"),
        fields=(Field("OUTLOOK_CLIENT_ID", "Application (client) ID", placeholder="00000000-0000-..."),
                Field("OUTLOOK_CLIENT_SECRET", "Client secret", secret=True, required=False,
                      help="Needed when the console runs on a web address; not needed on localhost."),
                Field("OUTLOOK_TENANT", "Tenant", required=False, placeholder="common",
                      help="Leave as common for personal and work accounts.")),
        oauth="microsoft", token_key="OUTLOOK_TOKEN_CACHE_JSON",
        steps=("In Microsoft Entra, open App registrations → New registration.",
               "Choose accounts in any organization and personal Microsoft accounts, and add the redirect URI shown "
               "here (platform: Web; or Mobile and desktop for localhost).",
               "Under API permissions add Microsoft Graph → Delegated → Mail.Read and Mail.Send.",
               "For a web address, create a client secret under Certificates & secrets.",
               "Paste the IDs here, save, then press Connect with Microsoft."),
        links=(("App registrations", "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"),),
    ),
    Integration(
        "todoist", "Todoist", "Tasks",
        "Your personal task list: reminders, tasks created from email, and the chat's \"remind me\".",
        ("Task reminders", "Email → task", "Remind me ..."),
        fields=(Field("TODOIST_API_TOKEN", "API token", secret=True),),
        steps=("In Todoist open Settings → Integrations → Developer.", "Copy your API token and paste it here."),
        links=(("Todoist developer settings", "https://app.todoist.com/app/settings/integrations/developer"),),
    ),
    Integration(
        "whatsapp", "WhatsApp", "Messaging",
        "Alerts, drafts to approve, and chat with the agent, on the NeuraNova business number.",
        ("Alerts", "Approve drafts", "Chat", "Team reminders"),
        fields=(Field("WHATSAPP_PHONE_NUMBER_ID", "Phone number ID", placeholder="1234567890"),
                Field("WHATSAPP_ACCESS_TOKEN", "Permanent access token", secret=True),
                Field("WHATSAPP_RECIPIENT", "Your WhatsApp number", placeholder="919876543210",
                      help="Where alerts go. International format, digits only."),
                Field("WHATSAPP_APP_SECRET", "App secret", secret=True,
                      help="Meta app → App settings → Basic. Used to check messages really come from Meta."),
                Field("WHATSAPP_TEMPLATE_NAME", "Message template", required=False, placeholder="neuranova_update")),
        steps=("Get a phone number that isn't on WhatsApp yet and create a Meta Business account.",
               "In Meta for Developers, create a Business app and add WhatsApp; verify the number.",
               "Create a permanent token for a system user with whatsapp_business_messaging.",
               "Create the Utility template neuranova_update with body: NeuraNova update: {{1}}",
               "Paste the details here and save. Then in WhatsApp → Configuration set the webhook URL and "
               "verify token shown here, and subscribe to messages."),
        links=(("Meta for Developers", "https://developers.facebook.com/apps"),
               ("WhatsApp Manager", "https://business.facebook.com/wa/manage/")),
    ),
)
BY_NAME = {i.name: i for i in CATALOG}


# --- encryption --------------------------------------------------------------------------

class Vault:
    def __init__(self, secret: str):
        from cryptography.fernet import Fernet

        if not secret:
            raise ValueError("DASHBOARD_SECRET is needed to store integration keys")
        key = base64.urlsafe_b64encode(hashlib.sha256(("neuranova-integrations:" + secret).encode()).digest())
        self.fernet = Fernet(key)

    def seal(self, data: dict) -> str:
        return self.fernet.encrypt(json.dumps(data).encode()).decode()

    def open(self, token: str) -> dict:
        from cryptography.fernet import InvalidToken

        if not token:
            return {}
        try:
            return json.loads(self.fernet.decrypt(token.encode()))
        except InvalidToken:
            log.warning("Stored integration keys can't be read (was DASHBOARD_SECRET changed?)")
            return {}


def vault_for(settings) -> Vault | None:
    secret = settings.secret("DASHBOARD_SECRET")
    return Vault(secret) if secret else None


def stored(store: Store, settings, name: str) -> dict:
    vault = vault_for(settings)
    row = store.integration(name)
    return vault.open(row["data_enc"]) if vault and row else {}


def save_values(store: Store, settings, name: str, values: dict, by_user: str) -> None:
    vault = vault_for(settings)
    current = stored(store, settings, name)
    for key, value in values.items():
        if value is None:
            current.pop(key, None)
        elif value != "":
            current[key] = value
    store.save_integration(name, vault.seal(current), by_user)


def with_integrations(settings, store: Store):
    """Settings with console-saved values added. Values from .env take precedence."""
    vault = vault_for(settings)
    if vault is None:
        return settings
    extra: dict[str, str] = {}
    for row in store.integrations():
        for key, value in vault.open(row["data_enc"]).items():
            if isinstance(value, str) and value and not settings.env.get(key):
                extra[key] = value
    if "WHATSAPP_PHONE_NUMBER_ID" in extra and not settings.env.get("NOTIFY_CHANNEL"):
        extra["NOTIFY_CHANNEL"] = "whatsapp"
    return replace(settings, env={**settings.env, **extra}) if extra else settings


def from_env(settings, key: str) -> bool:
    return bool(settings.env.get(key))


# --- tests ------------------------------------------------------------------------------------

def _graph_get(url: str, token: str, **params) -> dict:
    resp = httpx.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", {})
            msg = detail.get("message") if isinstance(detail, dict) else str(detail)
        except ValueError:
            msg = resp.text[:200]
        raise RuntimeError(f"{resp.status_code}: {msg}")
    return resp.json()


def test_integration(name: str, settings, store: Store) -> tuple[bool, str, str | None]:
    """Run a harmless check. Returns (ok, message, account)."""
    s = settings.secret
    try:
        if name == "claude":
            import anthropic

            if not s("ANTHROPIC_API_KEY"):
                return False, "Add an API key.", None
            model = anthropic.Anthropic(api_key=s("ANTHROPIC_API_KEY")).models.retrieve(settings.model)
            return True, f"Key works. Using {model.display_name}.", None
        if name == "openai":
            if not s("OPENAI_API_KEY"):
                return False, "Add an API key.", None
            if not s("OPENAI_MODEL"):
                return False, "Add the model name.", None
            from openai import OpenAI

            model = OpenAI(api_key=s("OPENAI_API_KEY")).models.retrieve(s("OPENAI_MODEL"))
            return True, f"Key works. Model {model.id} is available.", None
        if name == "email":
            conn = email_connector(settings)
            if conn is None:
                return False, "Add your email address and app password.", None
            return True, conn.check(), s("EMAIL_ADDRESS")
        if name == "todoist":
            if not s("TODOIST_API_TOKEN"):
                return False, "Add your API token.", None
            from .connectors.todoist import TodoistConnector

            n = len(TodoistConnector(s("TODOIST_API_TOKEN")).today_and_overdue())
            return True, f"Connected. {n} tasks due today or overdue.", None
        if name == "gmail":
            if not (s("GMAIL_TOKEN_JSON") or (s("GMAIL_TOKEN_FILE") and os.path.exists(s("GMAIL_TOKEN_FILE")))):
                return False, "Not signed in yet. Press Connect with Google.", None
            from .connectors.gmail import GmailConnector

            conn = GmailConnector(s("GMAIL_TOKEN_FILE") or None, token_json=s("GMAIL_TOKEN_JSON") or None,
                                  on_refresh=lambda t: save_values(store, settings, "gmail", {"GMAIL_TOKEN_JSON": t}, "agent"))
            email = conn.profile_email()
            return True, "Reading and sending as this address.", email
        if name == "outlook":
            if not s("OUTLOOK_TOKEN_CACHE_JSON"):
                if s("OUTLOOK_CLIENT_ID") and os.path.exists(s("OUTLOOK_TOKEN_CACHE") or "secrets/outlook_token_cache.json"):
                    from .connectors.outlook import access_token
                    access_token(s("OUTLOOK_CLIENT_ID"), s("OUTLOOK_TENANT") or "common",
                                 s("OUTLOOK_TOKEN_CACHE") or "secrets/outlook_token_cache.json")
                    return True, "Connected (signed in from the command line).", None
                return False, "Not signed in yet. Press Connect with Microsoft.", None
            from .connectors.outlook import token_from_cache

            token, user = token_from_cache(
                s("OUTLOOK_CLIENT_ID"), s("OUTLOOK_TENANT") or "common", s("OUTLOOK_TOKEN_CACHE_JSON"),
                s("OUTLOOK_CLIENT_SECRET"),
                on_change=lambda c: save_values(store, settings, "outlook", {"OUTLOOK_TOKEN_CACHE_JSON": c}, "agent"))
            inbox = _graph_get("https://graph.microsoft.com/v1.0/me/mailFolders/inbox", token,
                               **{"$select": "totalItemCount"})
            return True, f"Connected. {inbox.get('totalItemCount', 0)} messages in the inbox.", user
        if name == "whatsapp":
            missing = [f.label for f in BY_NAME["whatsapp"].fields if f.required and not s(f.key)]
            if missing:
                return False, "Missing: " + ", ".join(missing) + ".", None
            info = _graph_get(f"https://graph.facebook.com/{s('WHATSAPP_API_VERSION') or 'v22.0'}/"
                              f"{s('WHATSAPP_PHONE_NUMBER_ID')}", s("WHATSAPP_ACCESS_TOKEN"),
                              fields="display_phone_number,verified_name")
            return True, f"Bot number {info.get('display_phone_number', '')} is ready.", info.get("verified_name")
    except Exception as exc:  # shown to the founder on the card
        log.warning("Integration test %s failed: %s", name, exc)
        return False, _plain_error(exc), None
    return False, "Unknown integration.", None


def _plain_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    lowered = text.lower()
    if "401" in lowered or "invalid x-api-key" in lowered or "authentication" in lowered or "invalid_grant" in lowered:
        return "The key or sign-in was rejected. Check it, or reconnect."
    if "403" in lowered:
        return "Signed in, but missing a permission. " + text[:160]
    if "timed out" in lowered or "connecterror" in lowered or "name or service" in lowered:
        return "Couldn't reach the service. Check the internet connection and try again."
    return text[:240]


def email_connector(settings):
    """The quick-connect mailbox from settings, or None if it isn't filled in."""
    s = settings.secret
    if not (s("EMAIL_ADDRESS") and s("EMAIL_APP_PASSWORD") and s("EMAIL_IMAP_HOST")):
        return None
    from .connectors.imap import ImapConnector

    return ImapConnector(s("EMAIL_ADDRESS"), s("EMAIL_APP_PASSWORD").replace(" ", ""), s("EMAIL_IMAP_HOST"),
                         int(s("EMAIL_IMAP_PORT") or 993), s("EMAIL_SMTP_HOST") or s("EMAIL_IMAP_HOST"),
                         int(s("EMAIL_SMTP_PORT") or 465), s("EMAIL_PROVIDER") or "other")


def detect_email(store: Store, settings, address: str, by_user: str, http=None) -> dict:
    """Step 1 of the email wizard: remember the address and fill in its server settings."""
    from .connectors.imap import detect

    address = address.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
        raise ValueError("Enter a full email address, like you@neuranova.in.")
    found = detect(address, http)
    save_values(store, settings, "email", {
        "EMAIL_ADDRESS": address, "EMAIL_PROVIDER": found["provider"],
        "EMAIL_IMAP_HOST": found["imap_host"], "EMAIL_IMAP_PORT": str(found["imap_port"]),
        "EMAIL_SMTP_HOST": found["smtp_host"], "EMAIL_SMTP_PORT": str(found["smtp_port"]),
    }, by_user)
    return found


def run_check(name: str, settings, store: Store) -> tuple[bool, str]:
    settings = with_integrations(settings, store)
    ok, message, account = test_integration(name, settings, store)
    store.set_integration_status(name, "connected" if ok else "error", message, account)
    store.log("integration_test", integration=name, ok=ok)
    return ok, message


def is_configured(name: str, settings) -> bool:
    s = settings.secret
    integ = BY_NAME[name]
    if integ.token_key:
        return bool(s(integ.token_key)) or (name == "gmail" and bool(s("GMAIL_TOKEN_FILE")) and
                                            os.path.exists(s("GMAIL_TOKEN_FILE")))
    return all(s(f.key) for f in integ.fields if f.required)


def health_check(settings, store: Store, notify) -> dict[str, bool]:
    """Daily: re-test every configured integration; tell the founder once when one breaks."""
    settings = with_integrations(settings, store)
    results = {}
    for integ in CATALOG:
        if not is_configured(integ.name, settings):
            continue
        before = store.integration(integ.name)
        was_ok = before is None or before["status"] != "error"
        ok, message = run_check(integ.name, settings, store)
        results[integ.name] = ok
        if was_ok and not ok:
            try:
                notify(f"⚠️ {integ.title} stopped working: {message}\nFix it on the Integrations page.")
            except Exception:
                log.exception("Could not send the integration alert")
    return results


# --- OAuth (Connect buttons) ----------------------------------------------------------------------

def redirect_uri(base_url: str, provider: str) -> str:
    return f"{base_url.rstrip('/')}/integrations/{provider}/callback"


def _allow_local_http(uri: str) -> None:
    # oauthlib refuses plain http; allow it only for this computer (the laptop demo).
    host = urlparse(uri).hostname or ""
    if uri.startswith("http://") and host in ("localhost", "127.0.0.1"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def _save_state(store: Store, provider: str, state: str, data: dict) -> None:
    store.put(f"oauth:{provider}:{state}", json.dumps({**data, "exp": time.time() + OAUTH_STATE_SECONDS}))


def _take_state(store: Store, provider: str, state: str) -> dict | None:
    key = f"oauth:{provider}:{state}"
    raw = store.get(key)
    if not raw:
        return None
    store.put(key, json.dumps({"exp": 0}))  # single use
    data = json.loads(raw)
    return data if data.get("exp", 0) > time.time() else None


def _google_flow(settings, uri: str, code_verifier: str | None = None):
    from google_auth_oauthlib.flow import Flow

    from .connectors.gmail import SCOPES

    config = {"web": {"client_id": settings.secret("GOOGLE_CLIENT_ID"),
                      "client_secret": settings.secret("GOOGLE_CLIENT_SECRET"),
                      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                      "token_uri": "https://oauth2.googleapis.com/token"}}
    return Flow.from_client_config(config, SCOPES, redirect_uri=uri, code_verifier=code_verifier,
                                   autogenerate_code_verifier=code_verifier is None)


def start_oauth(provider: str, settings, store: Store, base_url: str, user_id: str) -> str:
    """URL to send the browser to."""
    settings = with_integrations(settings, store)
    uri = redirect_uri(base_url, provider)
    _allow_local_http(uri)
    if provider == "google":
        if not (settings.secret("GOOGLE_CLIENT_ID") and settings.secret("GOOGLE_CLIENT_SECRET")):
            raise ValueError("Save your Google client ID and secret first.")
        flow = _google_flow(settings, uri)
        url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
        _save_state(store, "google", state, {"verifier": flow.code_verifier, "user": user_id, "uri": uri})
        return url
    if provider == "microsoft":
        from .connectors.outlook import SCOPES, make_app

        if not settings.secret("OUTLOOK_CLIENT_ID"):
            raise ValueError("Save your Microsoft application (client) ID first.")
        app, _ = make_app(settings.secret("OUTLOOK_CLIENT_ID"), settings.secret("OUTLOOK_TENANT") or "common",
                          client_secret=settings.secret("OUTLOOK_CLIENT_SECRET"))
        flow = app.initiate_auth_code_flow(SCOPES, redirect_uri=uri, prompt="select_account")
        _save_state(store, "microsoft", flow["state"], {"flow": flow, "user": user_id, "uri": uri})
        return flow["auth_uri"]
    raise ValueError("Unknown provider")


def finish_oauth(provider: str, settings, store: Store, params: dict, user_id: str) -> str:
    """Complete sign-in from the callback. Returns a message for the founder."""
    if params.get("error"):
        raise ValueError(f"Sign-in was cancelled or refused ({params['error']}).")
    state = _take_state(store, provider, params.get("state", ""))
    if state is None or state.get("user") != user_id:
        raise ValueError("This sign-in link expired. Press Connect again.")
    settings = with_integrations(settings, store)
    _allow_local_http(state["uri"])
    if provider == "google":
        flow = _google_flow(settings, state["uri"], code_verifier=state["verifier"])
        flow.fetch_token(code=params.get("code", ""))
        save_values(store, settings, "gmail", {"GMAIL_TOKEN_JSON": flow.credentials.to_json()}, user_id)
        ok, message = run_check("gmail", settings, store)
        return "Gmail connected." if ok else f"Signed in, but the check failed: {message}"
    if provider == "microsoft":
        from .connectors.outlook import make_app

        app, cache = make_app(settings.secret("OUTLOOK_CLIENT_ID"), settings.secret("OUTLOOK_TENANT") or "common",
                              client_secret=settings.secret("OUTLOOK_CLIENT_SECRET"))
        result = app.acquire_token_by_auth_code_flow(state["flow"], params)
        if "access_token" not in result:
            raise ValueError(f"Microsoft sign-in failed: {result.get('error_description', result.get('error'))}")
        save_values(store, settings, "outlook", {"OUTLOOK_TOKEN_CACHE_JSON": cache.serialize()}, user_id)
        ok, message = run_check("outlook", settings, store)
        return "Outlook connected." if ok else f"Signed in, but the check failed: {message}"
    raise ValueError("Unknown provider")


def disconnect(name: str, store: Store, by_user: str) -> None:
    store.delete_integration(name)
    store.log("integration_disconnected", integration=name, by=by_user)


def new_verify_token() -> str:
    return secrets.token_urlsafe(24)


def _provider_help(settings) -> dict:
    from .connectors.imap import PROVIDERS

    key = settings.secret("EMAIL_PROVIDER")
    address = settings.secret("EMAIL_ADDRESS")
    if not address:
        return {}
    p = PROVIDERS.get(key)
    if p is None:
        return {"name": f"Your mail host ({address.rsplit('@', 1)[-1]})", "url": "", "known": False,
                "steps": ("Use the password for this mailbox, or an app password if your host offers one.",
                          "Check the server names below with your host's help page (often under 'IMAP settings').")}
    return {"name": p.name, "url": p.app_password_url, "known": True, "steps": p.steps}


def view(settings, store: Store, base_url: str) -> list[dict]:
    """Everything the Integrations page shows, per card."""
    merged = with_integrations(settings, store)
    out = []
    for integ in CATALOG:
        row = store.integration(integ.name)
        saved = stored(store, settings, integ.name)
        configured = is_configured(integ.name, merged)
        status = row["status"] if row and configured else ("ready" if configured else "not_connected")
        fields = []
        for f in integ.fields:
            env_set = from_env(settings, f.key)
            value = settings.env.get(f.key) if env_set else saved.get(f.key, "")
            fields.append({"key": f.key, "label": f.label, "secret": f.secret, "help": f.help,
                           "placeholder": f.placeholder, "required": f.required, "env": env_set,
                           "has_value": bool(value),
                           "shown": ("••••" + value[-4:]) if (f.secret and value) else value})
        checked = row_dt(row["checked_at"]) if row and row["checked_at"] else None
        out.append({
            "name": integ.name, "title": integ.title, "category": integ.category, "summary": integ.summary,
            "unlocks": integ.unlocks, "steps": integ.steps, "links": integ.links, "oauth": integ.oauth,
            "fields": fields, "status": status, "configured": configured,
            "message": row["message"] if row else "", "account": row["account"] if row else "",
            "checked": checked.astimezone(settings.tz).strftime("%d %b %H:%M") if checked else "",
            "redirect_uri": redirect_uri(base_url, integ.oauth) if integ.oauth else "",
            "signed_in": bool(integ.token_key and merged.secret(integ.token_key)),
            "webhook_url": f"{base_url.rstrip('/')}/webhook" if integ.name == "whatsapp" else "",
            "verify_token": merged.secret("WHATSAPP_VERIFY_TOKEN") if integ.name == "whatsapp" else "",
            "wizard": bool(integ.extra.get("wizard")),
            "provider": _provider_help(merged) if integ.name == "email" else {},
        })
    return out


def summary(cards: list[dict]) -> dict:
    """Progress over what the agent needs: one mailbox (any of the email options), Claude, Todoist, WhatsApp."""
    ok = {c["name"] for c in cards if c["status"] == "connected"}
    needs = [("Email", {"email", "gmail", "outlook"}), ("AI", {"claude", "openai"}), ("Todoist", {"todoist"}),
             ("WhatsApp", {"whatsapp"})]
    missing = [label for label, names in needs if not (names & ok)]
    return {"total": len(needs), "connected": len(needs) - len(missing), "missing": missing}


def ai_choice(settings, store: Store) -> dict:
    """Which AI the PA uses, and which are connected."""
    merged = with_integrations(settings, store)
    have = {"claude": bool(merged.secret("ANTHROPIC_API_KEY")), "openai": bool(merged.secret("OPENAI_API_KEY"))}
    current = (merged.secret("AI_PROVIDER") or "").lower()
    if current not in have:
        current = "openai" if have["openai"] and not have["claude"] else "claude"
    return {"current": current, "have": have, "locked": from_env(settings, "AI_PROVIDER")}
