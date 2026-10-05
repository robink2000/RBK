"""Application QA for NeuraNova Production and Development.

Checks run in a headless browser (Playwright) with the role test accounts saved in Settings.

- Production is monitored safely: availability, page load, login per role, console and network errors.
  Workflow steps that could change data (click, fill, select, upload) are refused in Production.
- Development also runs the workflows you describe in plain steps:

      goto /classroom/schedule
      click Create class            (button/link text, or a CSS selector starting with css=)
      fill Title = QA test class    (field label/placeholder, or css=...)
      select Subject = Maths
      expect Class created          (text that must appear)
      expect-url /classroom/schedule

Failures become application issues with evidence. The same failure updates the existing issue instead
of creating a duplicate; a closed issue that fails again is reopened as a regression; an issue waiting
for retest is verified automatically when its check passes.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .store import ACTIVE, PAStore, data_of

log = logging.getLogger(__name__)

ROLES = ("Super Admin", "Mentor", "Teacher", "Student", "Coordinator", "IT Support")
ENVIRONMENTS = {"production": "Production", "development": "Development"}
SAFE_STEPS = {"goto", "expect", "expect-url", "wait"}
ALL_STEPS = SAFE_STEPS | {"click", "fill", "select", "press"}
STAGE_STATUS = {"new": "open", "assigned": "open", "in_progress": "in_progress", "ready_for_test": "ready_for_retest",
                "testing": "in_progress", "failed": "open", "fix_required": "open", "retest": "ready_for_retest",
                "verified": "verified", "closed": "closed"}
IGNORED_CONSOLE = (r"favicon", r"Download the React DevTools", r"\[HMR\]", r"third-party cookie")


@dataclass
class Workflow:
    name: str
    role: str
    steps: list[str]
    environments: tuple[str, ...] = ("development",)


@dataclass
class CheckResult:
    environment: str
    role: str
    workflow: str
    ok: bool
    error: str = ""
    url: str = ""
    duration_ms: int = 0
    console_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    screenshot: str = ""
    at: str = ""

    @property
    def key(self) -> str:
        return f"{self.environment}|{self.role}|{self.workflow}"


def parse_workflows(text: str) -> list[Workflow]:
    """Workflows are written as blocks:

        [Teacher] Schedule a class (development)
        goto /classroom/schedule
        click Create class
        ...
    """
    flows, current = [], None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if m := re.match(r"^\[(?P<role>[^\]]+)\]\s*(?P<name>.+?)(?:\s*\((?P<envs>[a-z, ]+)\))?$", line):
            role = next((r for r in ROLES if r.lower() == m.group("role").strip().lower()), m.group("role").strip())
            envs = tuple(e.strip() for e in (m.group("envs") or "development").split(",") if e.strip() in ENVIRONMENTS)
            current = Workflow(m.group("name").strip(), role, [], envs or ("development",))
            flows.append(current)
        elif current is not None:
            current.steps.append(line)
    return flows


def step_allowed(step: str, environment: str) -> bool:
    verb = step.split(None, 1)[0].lower()
    if verb not in ALL_STEPS:
        return False
    return environment != "production" or verb in SAFE_STEPS


def fingerprint(result: CheckResult) -> str:
    error = re.sub(r"\d+", "#", result.error.lower())
    error = re.sub(r"https?://\S+", "<url>", error)[:200]
    return hashlib.sha1(f"{result.key}|{error}".encode()).hexdigest()[:16]


def severity(result: CheckResult) -> str:
    if result.environment == "production":
        return "urgent" if result.workflow in ("Availability", "Login") else "high"
    return "high" if result.workflow == "Login" else "medium"


# --- browser runner ---------------------------------------------------------------------------

class Runner:
    def __init__(self, base_url: str, environment: str, evidence_dir: Path, timeout_ms: int = 20000, browser=None):
        self.base = base_url.rstrip("/")
        self.environment = environment
        self.evidence_dir = evidence_dir
        self.timeout = timeout_ms
        self._browser = browser

    def _new_page(self, browser):
        context = browser.new_context(ignore_https_errors=False, viewport={"width": 1366, "height": 850})
        page = context.new_page()
        page.set_default_timeout(self.timeout)
        console, failed = [], []
        origin = urlparse(self.base).netloc

        def on_console(msg):
            if msg.type == "error" and not any(re.search(p, msg.text, re.I) for p in IGNORED_CONSOLE):
                console.append(msg.text[:300])

        def on_response(resp):
            if resp.status >= 500 or (resp.status >= 400 and urlparse(resp.url).netloc == origin
                                      and resp.request.resource_type in ("document", "xhr", "fetch")):
                failed.append(f"{resp.status} {resp.request.method} {resp.url[:200]}")

        page.on("console", on_console)
        page.on("pageerror", lambda exc: console.append(f"Page error: {str(exc)[:300]}"))
        page.on("response", on_response)
        page.on("requestfailed", lambda req: failed.append(f"failed {req.method} {req.url[:200]}")
                if req.resource_type in ("document", "xhr", "fetch") else None)
        return context, page, console, failed

    def _evidence(self, page, result: CheckResult) -> None:
        try:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            name = re.sub(r"[^a-z0-9]+", "-", f"{result.environment}-{result.role}-{result.workflow}".lower())
            path = self.evidence_dir / f"{name}-{int(time.time())}.png"
            page.screenshot(path=str(path), full_page=False)
            result.screenshot = str(path)
        except Exception:
            log.debug("Could not save a screenshot", exc_info=True)

    def _finish(self, result: CheckResult, page, console, failed, started: float) -> CheckResult:
        result.duration_ms = int((time.monotonic() - started) * 1000)
        result.console_errors, result.failed_requests = console[:10], failed[:10]
        result.at = datetime.now(timezone.utc).isoformat()
        try:
            result.url = page.url
        except Exception:
            pass
        if result.ok and failed:
            result.ok, result.error = False, f"Request failed: {failed[0]}"
        if not result.ok:
            self._evidence(page, result)
        return result

    def availability(self, browser) -> CheckResult:
        result = CheckResult(self.environment, "Public", "Availability", ok=True)
        context, page, console, failed = self._new_page(browser)
        started = time.monotonic()
        try:
            resp = page.goto(self.base, wait_until="load")
            if resp is None or resp.status >= 400:
                result.ok, result.error = False, f"Home page returned {resp.status if resp else 'no response'}"
        except Exception as exc:
            result.ok, result.error = False, f"Could not open {self.base}: {_short(exc)}"
        out = self._finish(result, page, console, failed, started)
        context.close()
        return out

    def login(self, page, username: str, password: str, login_path: str = "") -> None:
        page.goto(urljoin(self.base + "/", login_path.lstrip("/")) if login_path else self.base, wait_until="load")
        user_box = page.locator("input[type=email], input[name*=user i], input[name*=email i], input[id*=user i], "
                                "input[id*=email i], input[autocomplete=username], input[type=text]").first
        pass_box = page.locator("input[type=password]").first
        user_box.fill(username)
        pass_box.fill(password)
        before = page.url
        submit = page.locator("button[type=submit], input[type=submit], button:has-text('Log in'), "
                              "button:has-text('Login'), button:has-text('Sign in')").first
        # don't tie the click to the navigation it starts: slow servers (and Windows) then fail the click itself
        submit.click(no_wait_after=True)
        error_box = page.locator("text=/invalid|incorrect|wrong password|failed/i")
        deadline = time.monotonic() + self.timeout / 1000
        while time.monotonic() < deadline:   # until we leave the login page or it shows an error
            page.wait_for_timeout(250)
            try:
                if page.url != before or error_box.count() > 0:
                    break
            except Exception:
                pass                         # page mid-navigation
        try:
            page.wait_for_load_state("networkidle", timeout=self.timeout)
        except Exception:
            pass
        still_login = page.locator("input[type=password]").count() > 0 and page.url == before
        error_text = page.locator("text=/invalid|incorrect|wrong password|failed/i").count() > 0
        if still_login or error_text:
            raise RuntimeError("Login did not succeed (still on the login page)")

    def run_role(self, browser, role: str, account: dict, workflows: list[Workflow], login_path: str = "") -> list[CheckResult]:
        results = []
        context, page, console, failed = self._new_page(browser)
        started = time.monotonic()
        login = CheckResult(self.environment, role, "Login", ok=True)
        try:
            self.login(page, account["username"], account["password"], login_path)
        except Exception as exc:
            login.ok, login.error = False, _short(exc)
        results.append(self._finish(login, page, console, failed, started))
        if login.ok:
            for flow in workflows:
                if self.environment not in flow.environments:
                    continue
                console.clear()
                failed.clear()
                results.append(self.run_workflow(page, flow, console, failed))
        context.close()
        return results

    def run_workflow(self, page, flow: Workflow, console, failed) -> CheckResult:
        result = CheckResult(self.environment, flow.role, flow.name, ok=True)
        started = time.monotonic()
        try:
            for step in flow.steps:
                if not step_allowed(step, self.environment):
                    raise RuntimeError(f"Step not allowed in {ENVIRONMENTS[self.environment]}: {step}")
                self._step(page, step)
        except Exception as exc:
            result.ok, result.error = False, _short(exc)
        return self._finish(result, page, console, failed, started)

    def _target(self, page, what: str):
        if what.startswith("css="):
            return page.locator(what[4:]).first
        return page.get_by_role("button", name=what).or_(page.get_by_role("link", name=what)).or_(
            page.get_by_text(what, exact=False)).first

    def _field(self, page, what: str):
        if what.startswith("css="):
            return page.locator(what[4:]).first
        return page.get_by_label(what).or_(page.get_by_placeholder(what)).first

    def _step(self, page, step: str) -> None:
        verb, _, arg = step.partition(" ")
        verb, arg = verb.lower(), arg.strip()
        if verb == "goto":
            resp = page.goto(urljoin(self.base + "/", arg.lstrip("/")), wait_until="load")
            if resp is not None and resp.status >= 400:
                raise RuntimeError(f"{arg} returned {resp.status}")
        elif verb == "click":
            self._target(page, arg).click()
            page.wait_for_load_state("load")
        elif verb in ("fill", "select"):
            name, _, value = arg.partition("=")
            box = self._field(page, name.strip())
            box.select_option(label=value.strip()) if verb == "select" else box.fill(value.strip())
        elif verb == "press":
            page.keyboard.press(arg)
        elif verb == "expect":
            page.get_by_text(arg, exact=False).first.wait_for(state="visible")
        elif verb == "expect-url":
            if arg not in page.url:
                raise RuntimeError(f"Expected to be on {arg}, but was on {page.url}")
        elif verb == "wait":
            page.wait_for_timeout(min(int(float(arg or 1) * 1000), 10000))


def _short(exc: Exception) -> str:
    text = str(exc).split("\n")[0]
    text = re.sub(r"=+ logs =+.*", "", text)
    return text[:300] or exc.__class__.__name__


def launch_browser():
    """Playwright's Chromium if installed; otherwise Microsoft Edge or Google Chrome already on the computer
    (every Windows PC has Edge), so QA works without a separate browser download."""
    import os

    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    attempts = [{"executable_path": os.environ["NEURANOVA_CHROMIUM"]}] if os.environ.get("NEURANOVA_CHROMIUM") else []
    attempts += [{}, {"channel": "msedge"}, {"channel": "chrome"}]
    last = None
    for extra in attempts:
        try:
            return pw, pw.chromium.launch(headless=True, **extra)
        except Exception as exc:  # try the next browser
            last = exc
    pw.stop()
    raise RuntimeError("No browser for QA checks. Install one with: python -m playwright install chromium") from last


def run_environment(environment: str, base_url: str, accounts: dict, workflows: list[Workflow],
                    evidence_dir: Path, login_path: str = "", allow_prod_login: bool = True,
                    browser_factory=None, timeout_ms: int = 20000) -> list[CheckResult]:
    """Run all checks for one environment. Returns results (never raises for check failures)."""
    if browser_factory is None:
        browser_factory = launch_browser
    pw, browser = browser_factory()
    runner = Runner(base_url, environment, evidence_dir, timeout_ms=timeout_ms)
    try:
        results = [runner.availability(browser)]
        if results[0].ok:
            for role in ROLES:
                account = accounts.get(role) or {}
                if not (account.get("username") and account.get("password")):
                    continue
                if environment == "production" and not allow_prod_login:
                    continue
                flows = [w for w in workflows if w.role == role]
                results += runner.run_role(browser, role, account, flows, login_path)
        return results
    finally:
        browser.close()
        if pw is not None:
            pw.stop()


# --- results -> issues -----------------------------------------------------------------------------

def record(pa: PAStore, results: list[CheckResult], actor: str = "QA") -> dict:
    """Turn results into issue updates. Returns counts."""
    counts = {"new": 0, "updated": 0, "regressions": 0, "verified": 0}
    for r in results:
        open_for_check = [row for row in pa.items(kind="qa_issue", status=None, limit=5000)
                          if data_of(row).get("check") == r.key]
        if r.ok:
            for row in open_for_check:
                if row["status"] in ACTIVE and row["stage"] in ("retest", "ready_for_test", "testing"):
                    pa.update_item(row["id"], actor, note=f"Retest passed at {r.at}", stage="verified",
                                   status="verified", verification="passed")
                    counts["verified"] += 1
            continue
        fp = fingerprint(r)
        evidence = {"environment": ENVIRONMENTS[r.environment], "role": r.role, "workflow": r.workflow,
                    "error": r.error, "url": r.url, "at": r.at, "screenshot": r.screenshot,
                    "console": r.console_errors, "network": r.failed_requests, "duration_ms": r.duration_ms}
        existing = pa.find_by_fingerprint(fp)
        if existing is not None:
            data = data_of(existing)
            data["occurrences"] = data.get("occurrences", 1) + 1
            data["last_evidence"] = evidence
            if existing["status"] in ACTIVE:
                stage = "failed" if existing["stage"] in ("retest", "ready_for_test", "testing") else existing["stage"]
                pa.update_item(existing["id"], actor, note=f"Failed again: {r.error}", data=data, stage=stage,
                               status=STAGE_STATUS.get(stage, "open"),
                               verification="failed" if stage == "failed" else existing["verification"])
                counts["updated"] += 1
            else:
                pa.update_item(existing["id"], actor, note=f"Regression: failing again ({r.error})", data=data,
                               stage="new", status="open", verification="", priority=severity(r))
                counts["regressions"] += 1
            continue
        pa.create_item(
            actor, kind="qa_issue", title=f"{ENVIRONMENTS[r.environment]} · {r.role} · {r.workflow}: {r.error[:90]}",
            description=f"Automatic check failed.\n{r.error}", department="Application", priority=severity(r),
            stage="new", status="open", source="qa", fingerprint=fp, related_project=ENVIRONMENTS[r.environment],
            data={"check": r.key, "environment": r.environment, "role": r.role, "workflow": r.workflow,
                  "occurrences": 1, "first_evidence": evidence, "last_evidence": evidence},
        )
        counts["new"] += 1
    return counts


def set_stage(pa: PAStore, item_id: int, stage: str, actor: str, note: str = "") -> bool:
    if stage not in STAGE_STATUS:
        return False
    extra = {}
    if stage in ("ready_for_test", "retest"):
        extra["verification"] = "pending"
    elif stage == "verified":
        extra["verification"] = "passed"
    elif stage == "failed":
        extra["verification"] = "failed"
    return pa.update_item(item_id, actor, note=note, stage=stage, status=STAGE_STATUS[stage], **extra)


def summary_text(results: list[CheckResult], counts: dict) -> str:
    failed = [r for r in results if not r.ok]
    if not results:
        return "No checks ran."
    head = f"{len(results) - len(failed)} of {len(results)} checks passed"
    extras = [f"{v} {k}" for k, v in counts.items() if v]
    return head + (" · " + ", ".join(extras) if extras else "")


def results_json(results: list[CheckResult]) -> list[dict]:
    return [asdict(r) | {"key": r.key} for r in results]
