# NeuraNova PA

**Your personal assistant for business growth, operations, communication, quality and progress.**

NeuraNova PA watches your email, WhatsApp, calendar, team work and NeuraNova applications, and answers one question all day: **what needs attention now, and what should I do next?** It tracks promises people make, follows up on leads, spots recurring quality problems, tests your applications, writes your daily and weekly summaries, and drafts messages for you, which are sent only after you approve them.

---

## Install on Windows (no Python needed)

1. Download **NeuraNova-PA-Setup-1.2.0.exe** from the repository's **Releases** page ("latest"). Builds from a branch are under **Actions → Windows build → Artifacts**.
2. Run it. It installs for your user only, so you don't need admin rights. You can tick:
   - **Create a desktop shortcut**
   - **Start NeuraNova PA automatically when I sign in to Windows** (recommended, so reminders and checks keep running)
3. Open **NeuraNova PA** from the Start menu. Your browser opens at **http://localhost:8080**. The PA keeps working in the background, shown by the NeuraNova icon in the system tray next to the clock. Click the icon to reopen it, or right-click → **Quit**.
4. **First time:** create your login in the browser (email and password). Then sign in and follow the **10-step setup**. Every step can be skipped and changed later under Settings.

**Prefer no installer?** Download **NeuraNova-PA-Windows-1.2.0.zip**, unzip it anywhere and double-click **Start NeuraNova PA.bat**. Run **Add to Windows startup.bat** once to start it automatically when you sign in.

**Just want to look around first?** Start menu → **NeuraNova PA (sample data demo)**, or **Start demo (sample data).bat** in the ZIP. Sign in with `you@neuranova.demo` / `neuranova-demo`. It uses sample data only, kept apart from your real data.

Your data lives in `%LOCALAPPDATA%\NeuraNova PA`. Uninstalling keeps that folder, so upgrades never lose anything.

<details><summary>Run from source (Mac, Linux or Windows with Python 3.11+)</summary>

```
pip install -e .
neuranova-pa            # same as the Windows program: browser first-run, then the PA
neuranova-pa --demo     # sample data
neuranova run           # the PA using .env in the current folder (server installs)
```
Or double-click `scripts\start.bat` / run `./scripts/start.sh`. Server and WhatsApp-webhook setup is in [docs/SETUP.md](docs/SETUP.md). Docker: see `Dockerfile`.
</details>

---

## What you see

| Page | What it's for |
|---|---|
| **Dashboard** | The briefing: "Good morning. 2 overdue items, 3 people waiting for your reply, 1 hot lead…", plus a ranked **Do next** list and your goal cards (business, responses, quality) with weekly charts. |
| **Today** | Everything that needs attention, grouped as urgent, overdue, due today, waiting for your reply, waiting on others, follow-ups, meetings (with what to prepare), opportunities, application issues, quality concerns and decisions. After a meeting you can capture the promised actions in one box. |
| **Tasks** | One list for tasks, follow-ups, "waiting for", leads, application issues, quality concerns, decisions and payments. It has filters, natural due dates ("tomorrow 3pm", "before Friday", "month end"), duplicate detection, the full history of every change, and a neutral **Who owns what** view that helps spot overload early. |
| **Business** | Lead pipeline (New → Contacted → Demo pending → Admission in progress → Quoted → Payment pending → Converted / No response / Lost), hot and stalled leads, follow-ups due, payments pending, and conversion %, which is shown only once there are real outcomes. |
| **Communications** | *Founder only.* Messages waiting for your approval, emails and WhatsApp messages you owe a reply, recent mail, contacts (parent, teacher, mentor…). You can also ask the PA to write a message ("remind Ravi's parents the fee is due Friday"). |
| **Application QA** | Production (safe monitoring) and Development (full workflow tests) for the roles Super Admin, Mentor, Teacher, Student, Coordinator and IT Support. Issues go New → Assigned → In progress → Ready for test → Testing → Failed / Fix required → Retest → Verified → Closed, with screenshots and errors as evidence, never a duplicate, and reopened automatically if a fixed problem comes back. |
| **Quality** | Quality concerns by area, how fast they are resolved, and **recurring patterns** (for example "3 Scheduling issues in 14 days"). |
| **Reports** | Morning Brief, End-of-Day, Weekly Management, Monthly Business, Sales, Quality and Application QA summaries. They are made on schedule or on demand, kept here, sent to WhatsApp if you choose, and saved to Google Drive if it's connected. |
| **AI Assistant** | Chat with your PA: "what needs my attention?", "who hasn't replied to us?", "remind Priya to send the timetable by Friday". It can look things up, create and update items, and draft messages for approval. |
| **Settings** | General, NeuraNova applications, test accounts, AI, integrations (Connected / Not connected / Disabled / Expired / Error, with Connect, Reconnect, Disconnect, Enable, Disable, Test and Save), notifications, scheduler, **security / Safe Mode**, people and the **audit log**. |

The same assistant also answers on WhatsApp. Teammates get their own login and see only their own work; the founder's mailbox, drafts and reports stay private.

### Handy shortcuts
- **+ New** (top right of every page, or press **N**): type what needs doing in your own words, e.g. *"Call Ravi's parents tomorrow 3pm"*. The date is understood automatically.
- **/** jumps to search.
- **✓** next to any item marks it done. **→ Tomorrow** moves an overdue or today's item to tomorrow.
- **Getting started** on the Dashboard shows what's left to connect, with a link to each step.
- If an older copy is still running, the PA tells you and opens the new version on the next free address.

### Built for everyday use
- **Repeating tasks:** write *"Publish the timetable every Friday"* or *"Send fee reminders every month on the 5th"*. When you tick one done, the next one appears.
- **Backups every day** of everything (Settings → Backups), with one-click download. The newest 14 are kept.
- **Download for Excel:** tasks (with your filters), leads and contacts.
- **On your phone:** Settings → Phone access lets phones on the same Wi-Fi open the PA.
- **Update notice:** when a newer version is published, a "New version" link appears in the menu.
- **Runs quietly in the system tray** on Windows, with no window to keep open. The log is in `logs\neuranova-pa.log` if anything goes wrong.

### How it decides what to do with a message
Important emails and WhatsApp messages are read by the AI, which decides whether to **create**, **update**, **close** or **ignore**. "Ok 👍" never becomes a task. "I'll send it by Friday" becomes a **waiting for** item due Friday at 6 pm, and if Friday passes the PA tells you and drafts a polite follow-up for approval. It updates existing items instead of creating duplicates. Messages from people who aren't on your team are treated as information only, never as commands.

---

## What is working

- Browser setup: first-run login page, 10-step setup wizard and Settings. No config files to edit.
- Email: any mailbox via app password (Gmail, Google Workspace, Outlook.com, Zoho, Hostinger, GoDaddy, Yahoo, iCloud…), with automatic server detection. Gmail and Microsoft 365 sign-in are also available as advanced options.
- Inbox triage, the 4-business-hour reply promise with warnings, reply drafts and automatic detection of replies.
- WhatsApp: alerts, briefings, two-way chat with the PA, analysis of messages from parents, leads and staff, and approved outgoing messages (template outside the 24-hour window).
- Smart items: tasks, follow-ups, waiting-for, leads, QA issues, quality concerns, decisions and payments, with history, departments, statuses, owners, natural dates and duplicate detection.
- Today briefing and Do-next ranking, proactive alerts (grouped, at most hourly, quiet outside work hours unless urgent).
- Business pipeline, hot and stalled leads, conversions and lost reasons.
- Quality concerns with recurring-pattern detection.
- Application QA with real browser checks (it uses Microsoft Edge on Windows), role test accounts, evidence and the full lifecycle.
- Calendar (Google or Outlook, private iCal address): today's and upcoming meetings, what to prepare, capturing actions afterwards.
- All seven reports, with plain-text fallback when AI is off, WhatsApp delivery and Google Drive upload.
- AI: Claude (default) or OpenAI, switchable in Settings.
- Team: invites, roles, member logins, task handover, blocked alerts, accountability view.
- Todoist: today's and overdue tasks, and email → task.
- Windows: installer, portable ZIP, start-with-Windows, single-instance start, demo mode.

## What needs your credentials

| To use… | You provide (in Settings → Integrations, or during setup) |
|---|---|
| AI reading, drafting, reports in prose, AI Assistant | a **Claude** API key (console.anthropic.com) *or* an **OpenAI** API key |
| Email | your address + an **app password** from your email provider |
| WhatsApp | a **Meta WhatsApp Business** phone number ID, access token and app secret. Two-way chat needs the PA on a server with a public `https://` address ([docs/SETUP.md](docs/SETUP.md), section 6); alerts work from the laptop |
| Calendar | your calendar's **private iCal address** |
| Google Drive (reports) | a Google OAuth client ID/secret, then **Sign in with Google** |
| Application QA | your **Production / Development addresses** and **one test account per role** |
| Todoist (optional) | an API token |

Everything else works without credentials. Without AI, briefings, alerts, the pipeline, QA and plain-text reports still work.

## Security protections

- **Safe Mode is ON by default.** Emails and WhatsApp messages are drafted and wait for your approval. Turning Safe Mode off requires typing `TURN OFF`, and even then only the kinds you explicitly mark as trusted are sent automatically.
- **Nothing destructive is automated:** the PA never deletes email, never changes users or fees, and **Production QA only opens pages and reads**. Clicks and form-filling are allowed on Development only.
- **No plain-text secrets:** the console password is stored only as a **scrypt hash** (an existing plain one in `.env` is converted automatically). API keys, app passwords, tokens and QA test-account passwords are **encrypted at rest** (Fernet) and never shown again in full.
- **Secrets never logged:** the audit log records *which* setting changed, never its value.
- Sign-in rate limiting, signed HttpOnly SameSite=Strict session cookies, a CSRF token on every form, no off-site redirects, X-Frame-Options DENY.
- The WhatsApp webhook checks Meta's signature, and messages from non-team numbers are treated as data only, never as instructions.
- Team members can't see the founder's mailbox, drafts, communications, reports or settings.
- By default it listens on `127.0.0.1` only, so other computers on your network can't reach it.
- A full **audit log** under Settings.

## Test results

- **156 automated tests** pass (`pytest`). They cover the data model, date parsing, communication analysis and dedupe, briefing ranking, proactive alerts, business and quality logic, reports, calendar, the AI provider layer (Claude and OpenAI), **real-browser QA runs** against a test site (Production safety, evidence, regressions, auto-verify), every web page for founder and member, permissions, Safe Mode, encrypted settings, the hashed password, and the email/WhatsApp/Todoist connectors with fakes.
- **Packaged-program smoke test** (`packaging/smoke_test.py`): starts the built program in a clean folder, completes the first-run page, signs in, opens every page, writes a report, creates a task, and confirms the password is in neither `.env` nor the log.
- **Windows CI** (`.github/workflows/windows.yml`, on `windows-latest`): runs all tests on Windows, builds the program, runs the smoke test, builds the installer, **silently installs it, starts it, runs the smoke test against the installed copy and uninstalls it**, then publishes the installer and ZIP.

## Recommended next improvements

1. **Host it on a small cloud server** (or keep the laptop on) so WhatsApp two-way chat and overnight checks run 24/7.
2. **Google Calendar API** (write access) so meetings can be scheduled from the PA, not just read.
3. **Record your real NeuraNova workflows** in Settings → Applications (for example "Teacher: create class", "Student: join class") so Development tests cover what matters most.
4. **Lead sources:** a form or website webhook so enquiries from neuranova.in arrive as leads automatically.
5. **Payments:** connect your payment gateway's reports so "payment pending" closes itself when money arrives.
6. **Mobile:** add the console to your phone's home screen (it's a web app) when hosted on a server.
7. **Signed installer:** a code-signing certificate removes Windows SmartScreen's "unknown publisher" warning.

---

## For developers

```
pip install -e ".[dev]"
pytest -q                                   # all tests (QA tests use Chromium if available)
neuranova-pa --demo                         # sample data at http://localhost:8080
neuranova report weekly                     # write a report now
neuranova qa development                    # run application checks now
pyinstaller packaging/neuranova-pa.spec     # build the Windows program (on Windows)
python packaging/smoke_test.py "dist/NeuraNova PA/NeuraNova PA.exe"
```

Code map: `src/neuranova/pa/` holds the PA brain (items, communication analysis, briefing, business, quality, QA, calendar, reports, preferences). `pa_web.py` and `pa_templates.py` are the pages, `launcher.py` is the desktop program, `jobs.py` is the scheduled work, `ai.py` is Claude/OpenAI, and `connectors/` holds email, Gmail, Outlook and Todoist. More detail on each automation: [docs/AGENT-DETAILS.md](docs/AGENT-DETAILS.md).
