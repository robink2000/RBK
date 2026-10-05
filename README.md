# NeuraNova Agent

A personal operations agent for NeuraNova. It watches your Gmail and Outlook inboxes and your Todoist tasks. It sends you alerts and a morning brief on WhatsApp.

**Phase 1 (this version) is read-only.** It never sends, deletes or changes email. It only reads mail and messages you.

## What it does

| Job | When | What you get on WhatsApp |
|---|---|---|
| Inbox check | every 15 min | Each new email is sorted into a category (client, lead, finance…) with a priority and a one-line summary. High-priority mail is sent to you right away. |
| Reply-time promise | every 15 min | Clients, leads and partners should get a reply within **4 business hours**. You get a warning 1 hour before the deadline and an alert if it's missed. Replying from Gmail or Outlook clears it automatically. |
| Task reminders | every 10 min | A ping 30 min before a timed Todoist task is due. |
| Morning brief | 08:30 | What needs action today, who is waiting on you, today's and overdue tasks, and a one-line status for each goal. |

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
neuranova run                   # keep running on the server
```

Until your WhatsApp Business setup is approved, leave `NOTIFY_CHANNEL=console`. Messages print to the terminal instead.

Full account setup (Google, Microsoft, Todoist, Meta/WhatsApp and the server): **[docs/SETUP.md](docs/SETUP.md)**.

## Layout

```
src/neuranova/
  cli.py            commands and the scheduler
  jobs.py           inbox check, reply-time alerts, reminders, morning brief
  brain.py          Claude: email triage and brief writing
  sla.py            business-hours deadline arithmetic
  db.py             SQLite storage (workspace/owner on every row - team-ready)
  notify.py         WhatsApp Cloud API (template messages) / console
  connectors/       gmail.py, outlook.py, todoist.py
tests/              pytest suite (no network or API keys needed)
```

## Safety

- **Read-only access:** Gmail uses the `gmail.readonly` scope and Outlook uses `Mail.Read`. The agent can't send or delete mail.
- **Emails are treated as information, never as orders.** Email text is passed to Claude marked as data, and Claude is told never to follow instructions found inside it. Suspicious emails are flagged in their summary.
- **Secrets stay out of git.** `.env`, `secrets/` and `data/` are ignored by git.
- **Every action is recorded** in the `activity_log` table.

## Roadmap

- **Phase 2:** turn emails into Todoist tasks, plus draft replies you approve on WhatsApp
- **Phase 3:** web dashboard with NeuraNova progress tracking, plus two-way WhatsApp chat ("remind me to…")
- **Phase 4:** team workspace: invites, task assignment and a team dashboard

## Tests

```bash
pytest
```
