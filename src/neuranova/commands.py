"""Commands the founder sends to the bot on WhatsApp (or via `neuranova cmd ...`)."""

from __future__ import annotations

import re

from .jobs import Agent

HELP = """NeuraNova agent - just text me normally, e.g.
"remind me to call Asha friday 3pm"
"what's waiting on me?"
"we won the Acme deal, 50000"
"how are we doing this month?"

Draft commands:
drafts - show reply drafts waiting for you
show 12 - show draft #12
send 12 - send draft #12
edit 12 <text> - replace draft #12 with your own text
redo 12 <what to change> - let the agent rewrite it
skip 12 - don't send draft #12
status - what's waiting on you
report - latest weekly progress report
help - this message"""

PATTERN = re.compile(r"^\s*([a-zA-Z]+)\s*(?:#?(\d+))?[\s:,-]*(.*)$", re.DOTALL)


def handle(agent: Agent, text: str, chat=None) -> str:
    """Run a draft command, or pass free text to the chat assistant (`chat(text) -> str`)."""
    match = PATTERN.match(text or "")
    if not match:
        return chat(text) if chat and (text or "").strip() else HELP
    word, number, rest = match.group(1).lower(), match.group(2), match.group(3)
    draft_id = int(number) if number else None

    alone = draft_id is None and not rest.strip()  # the message is just this one word

    if word in ("help", "menu", "commands") and alone:
        return HELP

    if word in ("drafts", "pending") and alone:
        drafts = agent.store.pending_drafts()
        if not drafts:
            return "No drafts waiting. 🎉"
        return "\n\n─────\n\n".join(agent.format_draft(agent.store.draft(d["id"])) for d in drafts)

    if word == "report" and alone:
        return agent.store.get("last_weekly_report") or "No weekly report yet - it arrives on Monday morning."

    if word == "status" and alone:
        waiting = agent.store.awaiting_reply()
        drafts = agent.store.pending_drafts()
        lines = [f"{len(waiting)} emails waiting for your reply, {len(drafts)} drafts to approve."]
        lines += [f"- {r['subject']} (reply by {agent._fmt_deadline(r)})" for r in waiting[:8]]
        return "\n".join(lines)

    actions = {"send": agent.send_draft, "approve": agent.send_draft,
               "skip": agent.skip_draft}
    # Strict shapes, so a sentence like "send 50 brochures to Acme" is never mistaken for "send draft 50":
    #   send 12 / skip 12 / show 12 - nothing after the number
    #   edit 12 <text> / redo 12 <instruction>
    exact = draft_id is not None and not rest.strip()
    if word in actions or word == "show":
        is_command = exact or (chat is None and not rest.strip())
    else:
        is_command = word in ("edit", "redo") and (draft_id is not None or chat is None)
    if is_command:
        if draft_id is None:
            return f"Which draft? e.g. {word} 12  (reply 'drafts' to see the numbers)"
        if word in actions:
            return actions[word](draft_id)
        if word == "show":
            d = agent.store.draft(draft_id)
            return agent.format_draft(d) if d else f"No draft #{draft_id}."
        if word == "edit":
            return agent.edit_draft(draft_id, rest)
        return agent.redo_draft(draft_id, rest)

    return chat(text) if chat else HELP
