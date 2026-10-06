"""Command line: `neuranova <command>`. Run `neuranova --help` for the list."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys

from .config import Settings, load_settings

log = logging.getLogger("neuranova")


def build_agent(settings: Settings):
    from .brain import Brain
    from .connectors.gmail import GmailConnector
    from .connectors.outlook import OutlookConnector, access_token, token_from_cache
    from .connectors.todoist import TodoistConnector
    from .db import Store
    from .integrations import save_values, with_integrations
    from .jobs import Agent
    from .notify import build_notifier
    from .team import ensure_owner

    store = Store(settings.db_path, settings.workspace_id, settings.owner_id)
    base_settings = settings
    settings = with_integrations(settings, store)  # keys and sign-ins connected in the console
    from .pa import prefs
    settings = prefs.apply(settings, store)        # company, hours and schedules set in Settings
    ensure_owner(store, settings)

    mail = []
    gmail_json = settings.secret("GMAIL_TOKEN_JSON")
    token_file = settings.secret("GMAIL_TOKEN_FILE") or "secrets/gmail_token.json"
    token_file = token_file if Path(token_file).exists() else ""
    if gmail_json or token_file:
        try:
            mail.append(GmailConnector(
                token_file or None, token_json=gmail_json or None,
                on_refresh=lambda t: save_values(store, base_settings, "gmail", {"GMAIL_TOKEN_JSON": t}, "agent")))
        except Exception as exc:
            log.warning("Gmail disabled: %s", exc)
    from .integrations import email_connector
    quick = email_connector(settings)
    if quick is not None:
        mail.append(quick)
    client_id = settings.secret("OUTLOOK_CLIENT_ID")
    if client_id:
        try:
            tenant = settings.secret("OUTLOOK_TENANT") or "common"
            if settings.secret("OUTLOOK_TOKEN_CACHE_JSON"):
                token, _ = token_from_cache(
                    client_id, tenant, settings.secret("OUTLOOK_TOKEN_CACHE_JSON"),
                    settings.secret("OUTLOOK_CLIENT_SECRET"),
                    on_change=lambda c: save_values(store, base_settings, "outlook",
                                                    {"OUTLOOK_TOKEN_CACHE_JSON": c}, "agent"))
            else:
                token = access_token(client_id, tenant,
                                     settings.secret("OUTLOOK_TOKEN_CACHE") or "secrets/outlook_token_cache.json")
            mail.append(OutlookConnector(token))
        except Exception as exc:
            log.warning("Outlook disabled: %s", exc)

    from .ai import build_llm

    todoist_token = settings.secret("TODOIST_API_TOKEN")
    return Agent(
        settings=settings,
        store=store,
        brain=Brain(settings.model, settings.goals, llm=build_llm(settings),
                    tone=settings.reply_tone, signature=settings.reply_signature),
        notifier=build_notifier(settings, store),
        mail=mail,
        todoist=TodoistConnector(todoist_token) if todoist_token else None,
        notifier_factory=lambda number: build_notifier(settings, store, recipient=number),
    )


def run_forever(settings: Settings) -> None:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.schedulers.blocking import BlockingScheduler

    from .db import Store
    from .integrations import with_integrations
    from .pa import prefs
    _store = Store(settings.db_path, settings.workspace_id, settings.owner_id)
    settings = prefs.apply(settings, _store)       # schedule times set in Settings
    settings_now = with_integrations(settings, _store)
    webhook = bool(settings_now.secret("WHATSAPP_VERIFY_TOKEN"))
    if webhook and not settings_now.secret("WHATSAPP_APP_SECRET"):
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
    def qa(environment):
        def run():
            try:
                agent = build_agent(settings)
                from .integrations import qa_config
                if qa_config(settings, agent.store).get(environment):
                    agent.run_qa(environment)
            except Exception:
                log.exception("QA %s failed", environment)
        return run

    sched.add_job(qa("production"), "cron", minute=20, hour=f"{settings.working_hours.start.hour}-"
                  f"{max(settings.working_hours.end.hour - 1, settings.working_hours.start.hour)}",
                  id="qa_prod", max_instances=1, coalesce=True)
    sched.add_job(qa("development"), "cron", hour=7, minute=30, id="qa_dev", max_instances=1, coalesce=True)
    sched.add_job(job("proactive"), "interval", minutes=settings.sla_check_minutes, id="proactive",
                  max_instances=1, coalesce=True)
    sched.add_job(job("team_reminders"), "interval", minutes=settings.task_reminder_minutes, id="team",
                  max_instances=1, coalesce=True)
    def integrations_health():
        try:
            from .integrations import health_check
            agent = build_agent(settings)
            health_check(settings, agent.store, agent.notifier.send)
        except Exception:
            log.exception("Integration health check failed")

    sched.add_job(integrations_health, "cron", hour=max(settings.morning_brief.hour - 1, 0), minute=5,
                  id="integrations", max_instances=1, coalesce=True)
    sched.add_job(job("morning_brief"), "cron", hour=settings.morning_brief.hour,
                  minute=settings.morning_brief.minute, id="brief", max_instances=1, coalesce=True)
    sched.add_job(job("eod_summary"), "cron", day_of_week=",".join(
        ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][d] for d in sorted(settings.working_hours.days)),
        hour=settings.working_hours.end.hour, minute=settings.working_hours.end.minute, id="eod",
        max_instances=1, coalesce=True)
    sched.add_job(job("monthly_report"), "cron", day=1, hour=settings.weekly_report_time.hour,
                  minute=settings.weekly_report_time.minute + 10 if settings.weekly_report_time.minute < 50 else 0,
                  id="monthly", max_instances=1, coalesce=True)
    sched.add_job(job("weekly_report"), "cron", day_of_week=settings.weekly_report_day,
                  hour=settings.weekly_report_time.hour, minute=settings.weekly_report_time.minute,
                  id="weekly", max_instances=1, coalesce=True)
    def backup_if_due():
        try:
            from .pa import backup
            if backup.due(settings):
                backup.make(Store(settings.db_path, settings.workspace_id, settings.owner_id), settings)
        except Exception:
            log.exception("Backup failed")

    def update_check():
        try:
            from .pa import updates
            updates.check(Store(settings.db_path, settings.workspace_id, settings.owner_id))
        except Exception:
            log.exception("Update check failed")

    sched.add_job(update_check, "interval", hours=12, id="updates", max_instances=1, coalesce=True,
                  next_run_time=datetime.now(settings.tz) + timedelta(minutes=1))
    sched.add_job(backup_if_due, "interval", hours=1, id="backup", max_instances=1, coalesce=True,
                  next_run_time=datetime.now(settings.tz) + timedelta(minutes=2))
    # first inbox check right away, in the background, so the console opens without waiting for the mailbox
    sched.get_job("inbox").modify(next_run_time=datetime.now(settings.tz) + timedelta(seconds=5))
    log.info("NeuraNova agent running. Morning brief at %s (%s). Ctrl+C to stop.",
             settings.morning_brief.strftime("%H:%M"), settings.tz.key)
    if not web:
        job("check_inbox")()
    sched.start()
    if web:
        import uvicorn

        from .server import create_app

        port = int(settings.secret("WEBHOOK_PORT") or 8080)
        host = settings.secret("WEB_HOST") or ("0.0.0.0" if prefs.get(_store).get("lan_access") else "127.0.0.1")
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
    rep = sub.add_parser("report", help="write a report now and print it")
    rep.add_argument("kind", choices=["morning", "eod", "weekly", "monthly", "sales", "quality", "qa"])
    qa_cmd = sub.add_parser("qa", help="run the application checks now")
    qa_cmd.add_argument("environment", choices=["production", "development"])
    sub.add_parser("progress", help="print goal progress numbers (no Claude call, nothing sent)")
    sub.add_parser("facts", help="print the data the brief is built from (no Claude call, nothing sent)")
    sub.add_parser("test-notify", help="send a test message on the configured channel")
    cmd = sub.add_parser("cmd", help='talk to the agent locally, e.g. neuranova cmd "send 12" or "remind me ..."')
    cmd.add_argument("text", nargs="+")
    sub.add_parser("run", help="run the scheduler (keep this running on the server)")
    sub.add_parser("setup", help="create your console login and settings in a few questions")
    demo = sub.add_parser("demo", help="open the console on this computer with sample data (no accounts needed)")
    demo.add_argument("--port", type=int, default=8080)
    demo.add_argument("--no-browser", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.command == "setup":
        from .setup_wizard import run_interactive
        try:
            run_interactive()
        except KeyboardInterrupt:
            print("\nSetup cancelled. Nothing was changed.")
            return 1
        try:
            start = input("\nStart the console now? [Y/n]: ").strip().lower() in ("", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            start = False
        if start:
            run_forever(load_settings(args.config))
        return 0

    if args.command == "demo":
        from .demo import run_demo
        run_demo(args.port, open_browser=not args.no_browser, config_path=args.config)
        return 0

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
        from dotenv import find_dotenv
        from .setup_wizard import protect_env
        if (found := find_dotenv(usecwd=True)) and protect_env(Path(found)):
            log.info("Your console password in .env is now stored as a secure hash (the password itself is unchanged).")
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
    elif args.command == "report":
        print(agent.report(args.kind)["text"])
    elif args.command == "qa":
        print(json.dumps(agent.run_qa(args.environment), indent=2))
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
