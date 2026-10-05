"""Command line: `neuranova <command>`. Run `neuranova --help` for the list."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import Settings, load_settings

log = logging.getLogger("neuranova")


def build_agent(settings: Settings):
    from .brain import Brain
    from .connectors.gmail import GmailConnector
    from .connectors.outlook import OutlookConnector, access_token
    from .connectors.todoist import TodoistConnector
    from .db import Store
    from .jobs import Agent
    from .notify import build_notifier

    mail = []
    token_file = settings.secret("GMAIL_TOKEN_FILE")
    if token_file:
        try:
            mail.append(GmailConnector(token_file))
        except Exception as exc:
            log.warning("Gmail disabled: %s", exc)
    client_id = settings.secret("OUTLOOK_CLIENT_ID")
    if client_id:
        try:
            token = access_token(client_id, settings.secret("OUTLOOK_TENANT") or "common",
                                 settings.secret("OUTLOOK_TOKEN_CACHE") or "secrets/outlook_token_cache.json")
            mail.append(OutlookConnector(token))
        except Exception as exc:
            log.warning("Outlook disabled: %s", exc)

    todoist_token = settings.secret("TODOIST_API_TOKEN")
    store = Store(settings.db_path, settings.workspace_id, settings.owner_id)
    from .team import ensure_owner
    ensure_owner(store, settings)
    return Agent(
        settings=settings,
        store=store,
        brain=Brain(settings.model, settings.goals, tone=settings.reply_tone, signature=settings.reply_signature),
        notifier=build_notifier(settings, store),
        mail=mail,
        todoist=TodoistConnector(todoist_token) if todoist_token else None,
        notifier_factory=lambda number: build_notifier(settings, store, recipient=number),
    )


def run_forever(settings: Settings) -> None:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.blocking import BlockingScheduler

    webhook = bool(settings.secret("WHATSAPP_VERIFY_TOKEN"))
    if webhook and not settings.secret("WHATSAPP_APP_SECRET"):
        raise SystemExit("WHATSAPP_APP_SECRET is required when the webhook is enabled (see docs/SETUP.md)")
    dashboard = bool(settings.secret("DASHBOARD_PASSWORD"))
    if dashboard and len(settings.secret("DASHBOARD_SECRET")) < 32:
        raise SystemExit("DASHBOARD_SECRET must be a random string of at least 32 characters (see docs/SETUP.md)")
    web = webhook or dashboard
    sched = (BackgroundScheduler if web else BlockingScheduler)(timezone=settings.tz)

    def job(name):
        def run():
            # Rebuild each run so refreshed Outlook tokens and config edits are picked up.
            try:
                getattr(build_agent(settings), name)()
            except Exception:
                log.exception("Job %s failed", name)
        return run

    sched.add_job(job("check_inbox"), "interval", minutes=settings.inbox_check_minutes, id="inbox",
                  max_instances=1, coalesce=True)
    sched.add_job(job("check_sla"), "interval", minutes=settings.sla_check_minutes, id="sla",
                  max_instances=1, coalesce=True)
    sched.add_job(job("task_reminders"), "interval", minutes=settings.task_reminder_minutes, id="tasks",
                  max_instances=1, coalesce=True)
    sched.add_job(job("team_reminders"), "interval", minutes=settings.task_reminder_minutes, id="team",
                  max_instances=1, coalesce=True)
    sched.add_job(job("morning_brief"), "cron", hour=settings.morning_brief.hour,
                  minute=settings.morning_brief.minute, id="brief", max_instances=1, coalesce=True)
    sched.add_job(job("weekly_report"), "cron", day_of_week=settings.weekly_report_day,
                  hour=settings.weekly_report_time.hour, minute=settings.weekly_report_time.minute,
                  id="weekly", max_instances=1, coalesce=True)
    log.info("NeuraNova agent running. Morning brief at %s (%s). Ctrl+C to stop.",
             settings.morning_brief.strftime("%H:%M"), settings.tz.key)
    job("check_inbox")()
    sched.start()
    if web:
        import uvicorn

        from .server import create_app

        port = int(settings.secret("WEBHOOK_PORT") or 8080)
        host = settings.secret("WEB_HOST") or "127.0.0.1"
        log.info("Web server on %s:%s (webhook: %s, dashboard: %s)", host, port,
                 "on" if webhook else "off", "on" if dashboard else "off")
        uvicorn.run(create_app(settings, lambda: build_agent(settings)), host=host, port=port,
                    log_level="warning")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neuranova", description="NeuraNova operations agent")
    parser.add_argument("--config", help="path to neuranova.toml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="connect an account (one-time)")
    auth.add_argument("service", choices=["gmail", "outlook"])
    sub.add_parser("check", help="fetch and triage new mail, create tasks and drafts now")
    sub.add_parser("sla", help="check reply deadlines now")
    sub.add_parser("reminders", help="send due task reminders now")
    sub.add_parser("brief", help="build and send the morning brief now")
    sub.add_parser("weekly", help="build and send the weekly progress report now")
    sub.add_parser("progress", help="print goal progress numbers (no Claude call, nothing sent)")
    sub.add_parser("facts", help="print the data the brief is built from (no Claude call, nothing sent)")
    sub.add_parser("test-notify", help="send a test message on the configured channel")
    cmd = sub.add_parser("cmd", help='talk to the agent locally, e.g. neuranova cmd "send 12" or "remind me ..."')
    cmd.add_argument("text", nargs="+")
    sub.add_parser("run", help="run the scheduler (keep this running on the server)")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings(args.config)

    if args.command == "auth":
        if args.service == "gmail":
            from .connectors.gmail import authorize
            authorize(settings.secret("GMAIL_CLIENT_SECRET_FILE") or "secrets/gmail_client_secret.json",
                      settings.secret("GMAIL_TOKEN_FILE") or "secrets/gmail_token.json")
        else:
            from .connectors.outlook import authorize
            if not settings.secret("OUTLOOK_CLIENT_ID"):
                parser.error("set OUTLOOK_CLIENT_ID in .env first (see docs/SETUP.md)")
            authorize(settings.secret("OUTLOOK_CLIENT_ID"), settings.secret("OUTLOOK_TENANT") or "common",
                      settings.secret("OUTLOOK_TOKEN_CACHE") or "secrets/outlook_token_cache.json")
        print(f"{args.service} connected.")
        return 0

    if args.command == "test-notify":
        from .notify import build_notifier
        build_notifier(settings).send("✅ NeuraNova agent is connected.\nYou'll get alerts and your morning brief here.")
        return 0

    if args.command == "run":
        run_forever(settings)
        return 0

    agent = build_agent(settings)
    if args.command == "check":
        print(json.dumps(agent.check_inbox()))
    elif args.command == "sla":
        print(json.dumps(agent.check_sla()))
    elif args.command == "reminders":
        print(json.dumps({"sent": agent.task_reminders()}))
    elif args.command == "brief":
        agent.morning_brief()
    elif args.command == "weekly":
        agent.weekly_report()
    elif args.command == "progress":
        from .progress import compute, weekly_series
        print(json.dumps({"last_7_days": compute(agent.store, settings.tz, 7),
                          "last_30_days": compute(agent.store, settings.tz, 30),
                          "by_week": weekly_series(agent.store, settings.tz)}, indent=2))
    elif args.command == "cmd":
        from .assistant import Assistant
        from .commands import handle
        print(handle(agent, " ".join(args.text), chat=Assistant(agent).reply))
    elif args.command == "facts":
        print(json.dumps(agent.gather_brief_facts(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
