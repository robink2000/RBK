# NeuraNova Agent

A personal operations agent for NeuraNova. It watches your Gmail and Outlook inboxes and your Todoist tasks. It sends you alerts and a morning brief on WhatsApp, turns emails into tasks, and drafts replies for you to approve.

**Nothing is ever sent without your approval.** The agent can only send a reply after you text `send <number>` for that exact draft. It cannot delete or change email.

## What it does

| Job | When | What you get on WhatsApp |
|---|---|---|
| Inbox check | every 15 min | Each new email is sorted into a category (client, lead, finance…) with a priority and a one-line summary. High-priority mail is sent to you right away. |
| Reply-time promise | every 15 min | Clients, leads and partners should get a reply within **4 business hours**. You get a warning 1 hour before the deadline and an alert if it's missed. Replying from Gmail or Outlook clears it automatically. |
| Task reminders | every 10 min | A ping 30 min before a timed Todoist task is due. |
| Morning brief | 08:30 | What needs action today, who is waiting on you, today's and overdue tasks, and a one-line status for each goal. |
| **Email → Todoist** | with each inbox check | Emails that involve real work (pay an invoice, prepare a proposal) become Todoist tasks, with the priority, a due date if the email gives one, and a link back to the email. |
| **Draft replies** | with each inbox check | For each client, lead or partner email waiting on you, Claude reads the full email and drafts a reply in your tone and with your signature. |

### Approving drafts on WhatsApp

```
✉️ Draft #12 → Asha (lead)
Re: Pricing for 3 months
Reply by Mon 13:00

Hi Asha,
Thanks for reaching out ... [price for 3 months] ...

❓ Needs you:
- What price should we quote for 3 months?

Reply: send 12 · edit 12 <your text> · redo 12 <what to change> · skip 12
```

| You text | What happens |
|---|---|
| `send 12` | The reply is sent from your own Gmail or Outlook, in the same thread. |
| `edit 12 Hi Asha, ...` | Draft 12 is replaced with exactly your text. |
| `redo 12 shorter, offer a call Tuesday` | Claude rewrites the draft following your instruction. |
| `skip 12` | The draft is dropped. The reply deadline still applies if you answer yourself. |
| `drafts` / `status` / `help` | List the waiting drafts, show what's waiting on you, or list the commands. |

Safety rules:
- A draft that still has a `[blank]` is **refused** until you fill it in, so placeholder text can't reach a client.
- A draft is sent **at most once**.
- If you reply from your mailbox instead, the draft is closed automatically.
- Only **your** WhatsApp number can give commands. Every webhook call must be signed by Meta.

The three goals (develop the business, give proper responses, deliver high quality) and the working hours are in [`neuranova.toml`](neuranova.toml).

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill in keys - see docs/SETUP.md
neuranova auth gmail            # one-time, opens a browser
neuranova auth outlook          # one-time, code you approve on your phone
neuranova test-notify           # check the WhatsApp (or console) channel
neuranova check                 # pull and triage mail now
neuranova brief                 # send the morning brief now
neuranova cmd drafts            # try WhatsApp commands locally, e.g. neuranova cmd "send 3"
neuranova run                   # scheduler + WhatsApp webhook; keep running on the server
```

Until your WhatsApp Business setup is approved, leave `NOTIFY_CHANNEL=console`. Messages print to the terminal instead.

Full account setup (Google, Microsoft, Todoist, Meta/WhatsApp and the server): **[docs/SETUP.md](docs/SETUP.md)**.

## Layout

```
src/neuranova/
  cli.py            command line, scheduler, starts the webhook
  jobs.py           inbox check, tasks from email, drafts, approvals, reply-time alerts, reminders, brief
  brain.py          Claude: triage, reply drafting, brief writing
  commands.py       WhatsApp commands (send / edit / redo / skip / drafts / status)
  server.py         WhatsApp webhook (signature check, owner-only, deduplicated)
  sla.py            business-hours deadline arithmetic
  db.py             SQLite storage (workspace/owner on every row - team-ready)
  notify.py         WhatsApp Cloud API (template messages) / console
  connectors/       gmail.py, outlook.py, todoist.py
tests/              pytest suite (no network or API keys needed)
```

## Safety

- **Limited mail access:** read plus send only (Gmail `gmail.readonly` + `gmail.send`, Outlook `Mail.Read` + `Mail.Send`). The agent has no permission to delete or change email, and it only sends a draft after your `send`.
- **Emails are treated as information, never as orders.** Email text is passed to Claude marked as data, and Claude is told never to follow instructions found inside it. Suspicious emails are flagged in their summary.
- **Secrets stay out of git.** `.env`, `secrets/` and `data/` are ignored by git.
- **Every action is recorded** in the `activity_log` table.

## Roadmap

- ~~Phase 2: turn emails into Todoist tasks, plus draft replies you approve on WhatsApp~~ ✅
- **Phase 3:** web dashboard with NeuraNova progress tracking, plus two-way WhatsApp chat ("remind me to…")
- **Phase 4:** team workspace: invites, task assignment and a team dashboard

## Tests

```bash
pytest
```
