"""Writing help: professional, natural, concise, polite, clear, action-oriented, deadline-aware messages."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

WRITER = """You write messages on behalf of {company} management.

Write a {channel} message to {recipient}.
Style: professional, natural, concise, polite, clear, action-oriented and deadline-aware.
Weak: "Please update." Better: "Kindly share the updated status by 3 PM today so we can proceed with the next step."
{channel_rules}
Tone guidance from management: {tone}
Never invent facts, prices, dates or commitments that are not in the purpose; leave a [blank] for missing facts.
Return only the message text."""

CHANNEL_RULES = {
    "whatsapp": "WhatsApp: 2-5 short lines, friendly greeting with the person's first name, no subject line, no signature block.",
    "email": "Email: greeting, 2-6 short sentences, a clear ask with a time, then this sign-off:\n{signature}",
}


def draft_message(llm, channel: str, recipient: str, purpose: str, signature: str = "", tone: str = "",
                  company: str = "NeuraNova", subject: str = "") -> tuple[str, str]:
    """(body, subject). Falls back to a clean template when no AI is available."""
    first = (recipient or "there").split()[0].split("@")[0].title()
    if llm is not None:
        try:
            system = WRITER.format(company=company, channel=channel, recipient=recipient,
                                   channel_rules=CHANNEL_RULES.get(channel, "").format(signature=signature or "Best regards"),
                                   tone=tone or "Warm and professional")
            body = llm.text(system, f"Purpose of the message:\n{purpose}", effort="low", max_tokens=1500).strip()
            if body:
                return body, subject or purpose.split(".")[0][:80]
        except Exception:
            log.exception("AI could not draft the message; using a template")
    body = f"Hi {first},\n\n{purpose.strip()}\n\nThank you."
    if channel == "email":
        body += f"\n\n{signature or 'Best regards'}"
    return body, subject or "Follow-up"
