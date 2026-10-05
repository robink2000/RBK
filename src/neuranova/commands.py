"""Commands the founder sends to the bot on WhatsApp (or via `neuranova cmd ...`)."""

from __future__ import annotations

import re

from .jobs import Agent

HELP = """NeuraNova agent commands:
drafts - show reply drafts waiting for you
show 12 - show draft #12
send 12 - send draft #12
edit 12 <text> - replace draft #12 with your own text
redo 12 <what to change> - let the agent rewrite it
skip 12 - don't send draft #12
status - what's waiting on you"""

PATTERN = re.compile(r"^\s*([a-zA-Z]+)\s*(?:#?(\d+))?[\s:,-]*(.*)$", re.DOTALL)


def handle(agent: Agent, text: str) -> str:
    match = PATTERN.match(text or "")
    if not match:
        return HELP
    word, number, rest = match.group(1).lower(), match.group(2), match.group(3)
    draft_id = int(number) if number else None

    if word in ("drafts", "list", "pending"):
        drafts = agent.store.pending_drafts()
        if not drafts:
            return "No drafts waiting. 🎉"
        return "\n\n─────\n\n".join(agent.format_draft(agent.store.draft(d["id"])) for d in drafts)

    if word == "status":
        waiting = agent.store.awaiting_reply()
        drafts = agent.store.pending_drafts()
        lines = [f"{len(waiting)} emails waiting for your reply, {len(drafts)} drafts to approve."]
        lines += [f"- {r['subject']} (reply by {agent._fmt_deadline(r)})" for r in waiting[:8]]
        return "\n".join(lines)

    actions = {"send": agent.send_draft, "approve": agent.send_draft, "yes": agent.send_draft,
               "skip": agent.skip_draft, "no": agent.skip_draft}
    if word in actions or word in ("show", "edit", "redo"):
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

    return HELP
