# NeuraNova Agent

A personal operations agent for NeuraNova. It watches your Gmail and Outlook inboxes and your Todoist tasks. It sends you alerts and a morning brief on WhatsApp, turns emails into tasks, drafts replies for you to approve, chats with you in plain language, tracks progress on your three goals in a web dashboard, and runs a shared task board for your team.

**Nothing is ever sent without your approval.** The agent can only send a reply after you text `send <number>` for that exact draft. It cannot delete or change email.

## Try it on your laptop (2 minutes, no accounts)

You need [Python 3.11+](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"** during install. Then download this repository (Code → Download ZIP, unzip it) and:

- **Windows:** double-click `scripts\start-demo.bat`
- **Mac / Linux:** open Terminal in the folder and run `./scripts/start-demo.sh`

The first start takes about a minute while it sets up. Your browser then opens **http://localhost:8080**. Sign in with:

| Email | Password |
|---|---|
| `you@neuranova.demo` | `neuranova-demo` |

Everything you see is sample data, kept in its own file (`data/demo.db`). Nothing is sent anywhere: "sending" a draft only marks it as sent inside the demo. Press **Ctrl+C** in the window to stop it. If port 8080 is busy, use `--port 8090`.

## What it does

| Job | When | What you get on WhatsApp |
|---|---|---|
| Inbox check | every 15 min | Each new email is sorted into a category (client, lead, finance…) with a priority and a one-line summary. High-priority mail is sent to you right away. |
| Reply-time promise | every 15 min | Clients, leads and partners should get a reply within **4 business hours**. You get a warning 1 hour before the deadline and an alert if it's missed. Replying from Gmail or Outlook clears it automatically. |
| Task reminders | every 10 min | A ping 30 min before a timed Todoist task is due. |
| Morning brief | 08:30 | What needs action today, who is waiting on you, today's and overdue tasks, and a one-line status for each goal. |
| **Email → Todoist** | with each inbox check | Emails that involve real work (pay an invoice, prepare a proposal) become Todoist tasks, with the priority, a due date if the email gives one, and a link back to the email. |
| **Draft replies** | with each inbox check | For each client, lead or partner email waiting on you, Claude reads the full email and drafts a reply in your tone and with your signature. |

| **Weekly report** | Monday 09:00 | How each goal did this week compared with last week and the 8-week trend, plus 2-3 actions for next week. |

### Chat with the bot

Text the bot normally on WhatsApp:

| You text | What happens |
|---|---|
| "remind me to call Asha friday 3pm" | Creates a Todoist task due Friday 15:00. You get a ping 30 minutes before. |
| "what's waiting on me?" | Lists emails waiting for your reply, their deadlines, and drafts to approve. |
| "we won the Acme deal, 150000" | Logs a won deal with that value for progress tracking. |
| "delivered the Globex site on time" / "client asked for rework on the logo" | Logs a delivery or rework for the quality goal. |
| "how are we doing this month?" | Gives the progress numbers for all three goals. |
| "done with the hosting invoice" | Marks the matching Todoist task as complete. |

The chat **cannot send or delete email**. Replies only go out through `send <number>`, from WhatsApp or the dashboard.

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
| `drafts` / `status` / `report` / `help` | List the waiting drafts, show what's waiting on you, show the latest weekly report, or list the commands. |

`send` and `skip` only count as commands when the whole message is the word plus a number, like `send 12`. A sentence such as "send 2 brochures to Acme" goes to the chat assistant instead and never sends a draft.

### Team

Invite teammates from the dashboard's **Team** page. Each person gets a one-time link, sets their own password, and signs in with their email.

| | Founder (admin) | Admin | Member |
|---|---|---|---|
| Goals, progress, charts, event log | ✓ | ✓ | ✓ |
| Team board: add, assign, finish, block, hand over tasks | ✓ | ✓ | ✓ (their own tasks, or ones they created) |
| Invite people, change roles, reset passwords, deactivate | ✓ | ✓ | – |
| Founder's inbox, reply drafts, personal Todoist, agent activity | ✓ | – | – |

**Team tasks** live in the agent itself, so teammates don't need Todoist. Your personal Todoist stays private.
- A person gets a WhatsApp message when a task is assigned to them (if their number is on their profile).
- They get a reminder 30 minutes before it's due.
- When a task becomes overdue, the person *and* the admins are told once.
- Marking a task **blocked** (with a reason) alerts the admins straight away.
- You can **delegate an email** from "Waiting for your reply": it becomes a team task with the email's summary and next step. The email's content stays private.

**Teammates on WhatsApp** message the same bot number:

| They text | What happens |
|---|---|
| `tasks` / `team` | Their open tasks, or the whole team board |
| `done 12` / `blocked 12 waiting for logo` / `reopen 12` | Update a task |
| "give Sam the Globex invoice, due friday 5pm" | The chat assistant creates and assigns the task |
| "delivered the Acme site on time" | Logged for the quality goal |

Members' chat can't see your email, drafts or personal Todoist.

The **weekly report** and **morning brief** include who finished what, who's overloaded, and anything overdue or blocked. The quality goal now also counts **team deadlines met**.

### Dashboard

A web page at your server's address. It shows:
- a card per goal with a status (✓ on track, ! needs attention, ✕ off track) and the numbers behind it, over 7, 30 or 90 days
- 8-week charts of replies on time and new leads
- drafts to approve: edit, send or skip right on the page
- emails waiting for your reply, and today's and overdue tasks
- a form to log progress events (or just tell the bot on WhatsApp)
- the agent's recent activity

It works on phone and desktop, follows your light or dark setting, and can be added to your phone's home screen like an app. Sign-in is password-protected.

**How the goals are measured**

| Goal | Measured from |
|---|---|
| Develop the business | New leads (found in email automatically), plus meetings, proposals and deals you log |
| Give proper responses | Share of client, lead and partner emails answered within 4 business hours, and median time to reply |
| Deliver high quality | Deliveries on time vs late, rework requests, and client feedback (all logged by you) |

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
neuranova cmd drafts            # talk to the agent locally, e.g. neuranova cmd "remind me to ... friday 3pm"
neuranova progress              # goal numbers (no Claude call)
neuranova weekly                # send the weekly progress report now
neuranova run                   # scheduler + WhatsApp webhook + dashboard; keep running on the server
```

Until your WhatsApp Business setup is approved, leave `NOTIFY_CHANNEL=console`. Messages print to the terminal instead.

Full account setup (Google, Microsoft, Todoist, Meta/WhatsApp and the server): **[docs/SETUP.md](docs/SETUP.md)**.

## Layout

```
src/neuranova/
  cli.py            command line, scheduler, starts the webhook
  jobs.py           inbox check, tasks from email, drafts, approvals, reply-time alerts, reminders, brief
  brain.py          Claude: triage, reply drafting, brief writing
  commands.py       WhatsApp draft commands; anything else goes to the chat assistant
  assistant.py      chat assistant: Claude with Todoist, email lookup, event and progress tools
  progress.py       goal metrics and weekly trends
  dashboard.py      web dashboard (login, goal cards, charts, drafts, tasks, events)
  charts.py         server-rendered SVG charts
  team.py           people, invites, roles, passwords, team task rules
  templates.py      dashboard HTML, NeuraNova theme and logo
  demo.py           `neuranova demo`: the console with sample data, offline
  server.py         web app: WhatsApp webhook + dashboard
  sla.py            business-hours deadline arithmetic
  db.py             SQLite storage (workspace/owner on every row - team-ready)
  notify.py         WhatsApp Cloud API (template messages) / console
  connectors/       gmail.py, outlook.py, todoist.py
tests/              pytest suite (no network or API keys needed)
```

## Your brand

The console uses the NeuraNova theme: a violet accent, a gold "nova" star logo, and light and dark modes. To change it, edit `[brand]` in `neuranova.toml`:

```toml
[brand]
name = "NeuraNova"
tagline = "Operations console"
accent = "#4a3aa7"        # light theme
accent_dark = "#9085e9"   # dark theme
logo = "brand/logo.svg"   # your own logo (.svg, .png, .jpg or .webp)
```

The built-in mark is also saved as `brand/neuranova-mark.svg` for slides, email signatures and so on.

## Safety

- **Limited mail access:** read plus send only (Gmail `gmail.readonly` + `gmail.send`, Outlook `Mail.Read` + `Mail.Send`). The agent has no permission to delete or change email, and it only sends a draft after your `send`.
- **Emails are treated as information, never as orders.** Email text is passed to Claude marked as data, and Claude is told never to follow instructions found inside it. Suspicious emails are flagged in their summary.
- **Secrets stay out of git.** `.env`, `secrets/` and `data/` are ignored by git.
- **Every action is recorded** in the `activity_log` table.
- **Team access:** each person has their own login, and passwords are stored hashed (scrypt). Invite and reset links work once and expire after 7 days, and only a hash of each link is stored. Deactivating someone signs them out immediately. Roles are checked on the server for every action.
- **Dashboard sign-in:** password with a 5-attempt lockout; a signed, HttpOnly, SameSite=Strict session cookie; a security token (CSRF) on every form; all page content escaped. The server listens only on `127.0.0.1` behind Caddy's HTTPS.

## Roadmap

- ~~Phase 2: turn emails into Todoist tasks, plus draft replies you approve on WhatsApp~~ ✅
- ~~Phase 3: web dashboard with NeuraNova progress tracking, plus two-way WhatsApp chat ("remind me to…")~~ ✅
- ~~Phase 4: team workspace: invites, task assignment and a team dashboard~~ ✅

## Tests

```bash
pytest
```
