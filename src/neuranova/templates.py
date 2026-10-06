"""HTML templates for the dashboard (Jinja2, autoescaped)."""

from jinja2 import DictLoader, Environment, select_autoescape

# --- templates -----------------------------------------------------------------

BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ brand.name }}</title>
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/brand/logo">
<link rel="apple-touch-icon" href="/brand/logo">
<meta name="theme-color" content="{{ brand.accent }}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
/* NeuraNova: calm, lightly violet-tinted surfaces for scanning; the brand lives in the logo, the
   purple accent (taken from the logo's "N") and the logo's orange-to-blue gradient as a strip on top. */
:root {
  color-scheme: light;
  --page: #f7f5fa; --surface: #ffffff; --ink: #1a1426; --ink-2: #4f4760; --muted: #877f96;
  --grid: #e8e4ef; --axis: #cbc4d8; --border: rgba(26,20,38,0.10);
  --accent: {{ brand.accent }}; --accent-ink: #ffffff; --series-1: {{ brand.accent }};
  --brand-gradient: linear-gradient(90deg, #ee6e1c, #f04818 18%, #b43c46 34%, #a50f81 50%, #780090 66%, #2d5baf 84%, #3683c2);
  --good: #0ca30c; --good-ink: #006300; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --font-display: "Sora", "Segoe UI", system-ui, sans-serif;
  --font-body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #110d19; --surface: #1a1426; --ink: #f5f2fa; --ink-2: #c9c1d8; --muted: #8f87a0;
    --grid: #2d2639; --axis: #3d3550; --border: rgba(245,242,250,0.10);
    --accent: {{ brand.accent_dark }}; --accent-ink: #110d19; --series-1: {{ brand.accent_dark }};
    --good-ink: #0ca30c;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #110d19; --surface: #1a1426; --ink: #f5f2fa; --ink-2: #c9c1d8; --muted: #8f87a0;
  --grid: #2d2639; --axis: #3d3550; --border: rgba(245,242,250,0.10);
  --accent: {{ brand.accent_dark }}; --accent-ink: #110d19; --series-1: {{ brand.accent_dark }};
  --good-ink: #0ca30c;
}
* { box-sizing: border-box; }
/* app shell: fixed sidebar on wide screens, a scrolling bar on phones */
nav.side { position: fixed; inset: 0 auto 0 0; width: 236px; background: var(--surface); border-right: 1px solid var(--border);
           display: flex; flex-direction: column; gap: 14px; padding: calc(16px + env(safe-area-inset-top, 0px)) 14px 16px; z-index: 5; }
main:has(> nav.side) { margin-left: 236px; max-width: 1240px; }
nav.side .brand img { width: 36px; height: 36px; }
.pa-tag { font: 700 11px var(--font-display); color: var(--accent-ink); background: var(--accent); border-radius: 6px; padding: 1px 6px; vertical-align: middle; }
.nav-links { display: flex; flex-direction: column; gap: 2px; flex: 1; overflow-y: auto; }
.nav-links a { color: var(--ink-2); text-decoration: none; padding: 8px 10px; border-radius: 8px; font-weight: 550; font-size: 14px; }
.nav-links a:hover { background: var(--page); color: var(--ink); }
.nav-links a.on { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--ink); }
.me { border-top: 1px solid var(--grid); padding-top: 10px; display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 14px; }
header.pagehead { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
header.pagehead h1 { font-size: 24px; }
form.quick input { width: min(320px, 100%); }
@media (max-width: 900px) {
  nav.side { position: static; width: auto; flex-direction: row; flex-wrap: wrap; align-items: center; padding: 10px 0; border-right: 0;
             border-bottom: 1px solid var(--border); background: transparent; margin-bottom: 12px; gap: 8px; }
  main:has(> nav.side) { margin-left: auto; }
  .nav-links { flex-direction: row; overflow-x: auto; flex-basis: 100%; order: 3; padding-bottom: 4px; }
  .nav-links a { white-space: nowrap; }
  .me { border: 0; padding: 0; margin-left: auto; }
  nav.side .brand-tag { display: none; }
}
body { margin: 0; background: var(--page); color: var(--ink); font: 15px/1.5 var(--font-body); }
h1, h2, .hero, .brand-name { font-family: var(--font-display); text-wrap: balance; }
h2 { letter-spacing: -0.005em; }
.brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--ink); }
.brand img { width: 40px; height: 40px; flex: none; object-fit: contain; }
.brand-strip { height: 4px; background: var(--brand-gradient); }
.brand-name { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; line-height: 1.1; }
.brand-name .nova { color: var(--accent); }
.brand-tag { color: var(--muted); font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; }
main { max-width: 1080px; margin: 0 auto; padding: 16px 16px 48px; }
header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
h1 { font-size: 20px; margin: 0; }
h2 { font-size: 16px; margin: 0 0 12px; }
.sub { color: var(--ink-2); font-size: 13px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; min-width: 0; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: 16px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: 16px; }
.grid3 .card, .grid2 .card { margin-bottom: 0; }
.row { margin-bottom: 16px; }
.hero { font-size: 32px; font-weight: 650; line-height: 1.1; margin: 8px 0 4px; font-variant-numeric: tabular-nums; }
.kv { display: flex; justify-content: space-between; border-top: 1px solid var(--grid); padding: 6px 0; font-size: 14px; }
.kv span:last-child { font-variant-numeric: tabular-nums; font-weight: 550; }
.pill { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--ink-2); }
.dot { width: 18px; height: 18px; border-radius: 50%; display: inline-grid; place-items: center; color: #fff; font-size: 11px; font-weight: 700; }
.s-good .dot { background: var(--good); } .s-warning .dot { background: var(--warning); color: #0b0b0b; }
.s-critical .dot { background: var(--critical); } .s-none .dot { background: var(--muted); }
.tabs a { color: var(--ink-2); text-decoration: none; padding: 4px 10px; border-radius: 999px; font-size: 13px; border: 1px solid var(--border); }
.tabs a.on { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
svg text { fill: var(--muted); font-size: 11px; }
svg .val { fill: var(--ink-2); font-weight: 600; }
svg .gridline { stroke: var(--grid); stroke-width: 1; }
svg .baseline { stroke: var(--axis); stroke-width: 1; }
svg .bar { fill: var(--series-1); }
svg .hit:hover + .bar, svg .bar:hover { opacity: 0.8; }
svg .hit { fill: transparent; }
details summary { cursor: pointer; color: var(--ink-2); font-size: 13px; margin-top: 4px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
td, th { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--grid); overflow-wrap: anywhere; }
.scroll { overflow-x: auto; }
a { color: var(--accent); }
main, .card { min-width: 0; }
body { overflow-wrap: break-word; }
th { color: var(--ink-2); font-weight: 600; }
ul.list { list-style: none; padding: 0; margin: 0; }
ul.list li { border-top: 1px solid var(--grid); padding: 8px 0; }
ul.list li:first-child { border-top: 0; }
.meta { color: var(--ink-2); font-size: 13px; }
.over { color: var(--critical); font-weight: 600; }
.draft textarea { width: 100%; min-height: 120px; resize: vertical; font: inherit; color: var(--ink); background: var(--page);
                  border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
.needs { background: color-mix(in srgb, var(--warning) 18%, transparent); border-radius: 8px; padding: 6px 10px; margin: 8px 0; font-size: 13px; }
a.btn { display: inline-block; text-decoration: none; }
button, .btn { font: inherit; font-size: 14px; border-radius: 8px; padding: 6px 12px; cursor: pointer;
               border: 1px solid var(--border); background: var(--surface); color: var(--ink); }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
button.link { border: 0; background: none; color: var(--muted); padding: 0 4px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
form.inline { display: inline; }
.event-form input, .event-form select { width: 100%; }
input, select { font: inherit; color: var(--ink); background: var(--page); border: 1px solid var(--border); border-radius: 8px; padding: 6px 8px; max-width: 100%; }
.event-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(140px, 100%), 1fr)); gap: 8px; align-items: end; }
.flash { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 8px; padding: 10px 12px; margin-bottom: 16px; }
.login { max-width: 360px; margin: 12vh auto; }
.login input { width: 100%; margin: 8px 0 12px; }
.empty { color: var(--muted); font-size: 14px; }
nav.top { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
nav.top a { color: var(--ink-2); text-decoration: none; padding: 4px 10px; border-radius: 8px; font-weight: 550; }
nav.top a.on { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--ink); }
.who { color: var(--muted); font-size: 13px; margin-left: 4px; }
.badge { display: inline-block; font-size: 11px; font-weight: 650; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--border); color: var(--ink-2); }
.badge.blocked { border-color: var(--serious); color: var(--ink); }
.badge.over { border-color: var(--critical); }
.task-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; align-items: center; }
.task-actions input, .task-actions select { padding: 3px 6px; font-size: 13px; }
.task-actions button { padding: 3px 10px; font-size: 13px; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr)); gap: 8px; align-items: end; }
.form-grid input, .form-grid select { width: 100%; }
.copy { width: 100%; font-family: ui-monospace, monospace; font-size: 13px; }
.muted-row td { color: var(--muted); }
/* integrations */
.int-summary { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.meter { flex: 1 1 220px; height: 8px; border-radius: 999px; background: var(--grid); overflow: hidden; min-width: 0; }
.meter span { display: block; height: 100%; background: var(--brand-gradient); border-radius: 999px; }
.int-group { font-family: var(--font-display); font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase;
             color: var(--muted); margin: 24px 0 8px; }
.int-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(420px, 100%), 1fr)); gap: 16px; }
.int-card { display: flex; flex-direction: column; gap: 12px; margin: 0; }
.int-head { display: flex; gap: 12px; align-items: flex-start; }
.int-badge { width: 40px; height: 40px; border-radius: 10px; flex: none; display: grid; place-items: center;
             font-family: var(--font-display); font-weight: 700; color: var(--accent);
             background: color-mix(in srgb, var(--accent) 12%, var(--surface)); border: 1px solid var(--border); }
.int-head h2 { margin: 0; }
.int-head p { margin: 2px 0 0; color: var(--ink-2); font-size: 14px; }
.int-head .pill { margin-left: auto; white-space: nowrap; }
.s-ready .dot { background: var(--accent); }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--page); border: 1px solid var(--border); color: var(--ink-2); }
.int-status { font-size: 14px; border-radius: 8px; padding: 8px 10px; background: var(--page); }
.int-status.error { background: color-mix(in srgb, var(--critical) 10%, var(--surface)); }
.int-fields { display: grid; gap: 10px; }
.int-fields label { display: grid; gap: 4px; font-size: 14px; font-weight: 550; }
.int-fields input { width: 100%; font-weight: 400; }
input::placeholder { color: var(--muted); font-weight: 400; opacity: 1; }
.setup-nudge { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; justify-content: space-between; }
.int-fields small { color: var(--muted); font-weight: 400; }
.locked { color: var(--muted); font-size: 13px; font-weight: 400; }
ol.steps { margin: 6px 0 0 18px; padding: 0; display: grid; gap: 4px; font-size: 14px; color: var(--ink-2); }
.copyrow { display: flex; gap: 6px; align-items: center; margin-top: 6px; }
.copyrow input { flex: 1 1 auto; min-width: 0; font-family: ui-monospace, monospace; font-size: 12px; }
.ext-links { display: flex; gap: 12px; flex-wrap: wrap; font-size: 14px; margin-top: 8px; }
.email-card { grid-column: 1 / -1; }
.chip.rec { background: color-mix(in srgb, var(--accent) 12%, var(--surface)); color: var(--accent); border-color: transparent; font-weight: 600; }
ol.wizard { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; counter-reset: w; }
ol.wizard > li { position: relative; padding: 4px 0 16px 40px; counter-increment: w; }
ol.wizard > li::before { content: counter(w); position: absolute; left: 0; top: 0; width: 26px; height: 26px; border-radius: 50%;
  display: grid; place-items: center; font: 600 13px var(--font-display); background: var(--grid); color: var(--ink-2); }
ol.wizard > li:not(:last-child)::after { content: ""; position: absolute; left: 12px; top: 30px; bottom: 2px; width: 2px; background: var(--grid); }
ol.wizard > li.now::before { background: var(--accent); color: var(--accent-ink); }
ol.wizard > li.done::before { content: "✓"; background: var(--good); color: #fff; }
ol.wizard > li.off { opacity: 0.55; }
.w-title { font-weight: 600; margin-bottom: 6px; }
.w-row { display: flex; gap: 8px; flex-wrap: wrap; }
.w-row input { flex: 1 1 240px; min-width: 0; }
ul.w-steps { margin: 0 0 8px 18px; padding: 0; color: var(--ink-2); font-size: 14px; display: grid; gap: 2px; }
.server-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr)); gap: 8px; margin-top: 8px; }
.server-grid input { width: 100%; }
details.advanced { margin-top: 24px; }
.ai-switch { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; padding: 10px 16px; margin-bottom: 12px; }
.radio { display: inline-flex; gap: 6px; align-items: center; cursor: pointer; }
details.advanced > summary { cursor: pointer; }
</style>
</head>
<body><div class="brand-strip" aria-hidden="true"></div><main>{% block body %}{% endblock %}</main></body>
</html>"""

LOGIN = """{% extends "base" %}{% from "nav" import brand_logo, brand_wordmark with context %}{% block body %}
<div class="card login">
  <div class="brand" style="margin-bottom:12px">{{ brand_logo() }}<div><div class="brand-name">{{ brand_wordmark() }}</div><div class="brand-tag">{{ brand.tagline }}</div></div></div>
  <p class="sub">Sign in to your personal assistant.</p>
  {% if error %}<p class="over">{{ error }}</p>{% endif %}
  <form method="post" action="/login">
    <label for="em">Email</label>
    <input id="em" name="email" type="text" autocomplete="username" required autofocus value="{{ email or '' }}">
    <label for="pw">Password</label>
    <input id="pw" name="password" type="password" autocomplete="current-password" required>
    <button class="primary" type="submit">Sign in</button>
  </form>
</div>
{% endblock %}"""

NAV = """{% macro brand_logo() %}<img src="/brand/logo" alt="{{ brand.name }} logo" width="40" height="40">{% endmacro %}
{% macro brand_wordmark() %}{% if brand.name == 'NeuraNova' %}Neura<span class="nova">Nova</span>{% else %}{{ brand.name }}{% endif %}{% endmacro %}
{% macro top(page, user, csrf, today, title='') %}
{% set founder = user.id == owner_id %}
{% set nav = [('home', '/', 'Dashboard', True), ('today', '/today', 'Today', True), ('tasks', '/tasks', 'Tasks', True),
              ('business', '/business', 'Business', True), ('communications', '/communications', 'Communications', founder),
              ('qa', '/qa', 'Application QA', True), ('quality', '/quality', 'Quality', True),
              ('reports', '/reports', 'Reports', user.role == 'admin'), ('assistant', '/assistant', 'AI Assistant', True),
              ('settings', '/settings', 'Settings', user.role == 'admin')] %}
<nav class="side" aria-label="Main">
  <a class="brand" href="/" aria-label="{{ brand.name }} PA home">{{ brand_logo() }}
    <div><div class="brand-name">{{ brand_wordmark() }} <span class="pa-tag">PA</span></div><div class="brand-tag">Personal Assistant</div></div></a>
  <div class="nav-links">
  {% for key, href, label, show in nav if show %}<a href="{{ href }}" class="{{ 'on' if page == key else '' }}" {{ 'aria-current=page' if page == key else '' }}>{{ label }}</a>{% endfor %}
  </div>
  <div class="me">
    <div><strong>{{ user.name }}</strong><div class="meta">{{ 'Founder' if founder else user.role|capitalize }}{% if safe_mode %} · <span title="Outgoing messages wait for approval">Safe Mode on</span>{% endif %}</div></div>
    <form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="link" type="submit">Sign out</button></form>
  </div>
</nav>
<header class="pagehead">
  {% set titles = {'home': 'Dashboard', 'today': 'Today', 'tasks': 'Tasks', 'business': 'Business',
                   'communications': 'Communications', 'qa': 'Application QA', 'quality': 'Quality', 'reports': 'Reports',
                   'assistant': 'AI Assistant', 'settings': 'Settings', 'team': 'Team', 'integrations': 'Integrations'} %}
  <div><h1>{{ title or titles.get(page, '') }}</h1>
  <div class="sub">{{ today }}</div></div>
  <form class="quick" method="get" action="/search" role="search"><input name="q" type="search" placeholder="Search tasks, people, leads…" aria-label="Search"></form>
</header>
{% endmacro %}

{% macro task_row(t, me, members, csrf, back) %}
<li>
  <div><strong>#{{ t.id }}</strong> {{ t.title }}
    {% if t.status == 'blocked' %}<span class="badge blocked">🚧 blocked</span>{% endif %}
    {% if t.status == 'done' %}<span class="badge">✓ done</span>{% endif %}
    {% if t.overdue %}<span class="badge over">overdue</span>{% endif %}</div>
  <div class="meta">{{ t.assignee_name }}{% if t.due %} · due {{ t.due }}{% endif %}{% if t.notes %} · {{ t.notes }}{% endif %}</div>
  {% if t.status == 'blocked' %}<div class="meta">Blocked: {{ t.blocked_reason }}</div>{% endif %}
  {% if t.can_change %}
  <div class="task-actions">
    {% if t.status != 'done' %}
    <form class="inline" method="post" action="/team/tasks/{{ t.id }}/done"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}"><button type="submit">✓ Done</button></form>
    {% if t.status != 'blocked' %}
    <form class="inline" method="post" action="/team/tasks/{{ t.id }}/blocked"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}"><input name="reason" placeholder="What's blocking it?" maxlength="300" required aria-label="Blocked reason"><button type="submit">Blocked</button></form>
    {% endif %}
    <form class="inline" method="post" action="/team/tasks/{{ t.id }}/reassign"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}"><select name="assignee" aria-label="Hand to">{% for m in members %}<option value="{{ m.id }}" {{ 'selected' if m.id == t.assignee_id else '' }}>{{ m.name }}</option>{% endfor %}</select><button type="submit">Hand over</button></form>
    {% endif %}
    {% if t.status != 'open' %}
    <form class="inline" method="post" action="/team/tasks/{{ t.id }}/reopen"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}"><button type="submit">Reopen</button></form>
    {% endif %}
  </div>
  {% endif %}
</li>
{% endmacro %}"""

CHART = """{% macro chart(c, title, table_label, note="") %}
<svg viewBox="0 0 {{ c.w }} {{ c.h }}" width="100%" role="img" aria-label="{{ title }}">
  {% for g in c.grid %}
  <line class="{{ 'baseline' if loop.first else 'gridline' }}" x1="{{ c.left }}" x2="{{ c.right }}" y1="{{ g.y }}" y2="{{ g.y }}"/>
  <text x="{{ c.left - 6 }}" y="{{ g.y + 4 }}" text-anchor="end">{{ g.label }}</text>
  {% endfor %}
  {% for b in c.bars %}
  <g>
    <rect class="hit" x="{{ b.x - 6 }}" y="0" width="{{ b.w + 12 }}" height="{{ c.base_y }}"><title>{{ b.tip }}</title></rect>
    {% if b.path %}<path class="bar" d="{{ b.path }}"><title>{{ b.tip }}</title></path>
    {% elif b.value is none %}<text x="{{ b.x + b.w / 2 }}" y="{{ c.base_y - 5 }}" text-anchor="middle">–</text>{% endif %}
    <text x="{{ b.x + b.w / 2 }}" y="{{ c.h - 8 }}" text-anchor="middle">{{ b.label }}</text>
  </g>
  {% endfor %}
  {% if c.last %}<text class="val" x="{{ c.last.x + c.last.w / 2 }}" y="{{ c.last.y - 6 }}" text-anchor="middle">{{ '%g' % c.last.value }}{{ '%' if c.percent else '' }}</text>{% endif %}
</svg>
<details><summary>Show as table{% if note %} <span class="sub">({{ note }})</span>{% endif %}</summary>
<table><tr><th>Week of</th><th>{{ table_label }}</th></tr>
{% for b in c.bars %}<tr><td>{{ b.label }}</td><td>{{ '–' if b.value is none else ('%g' % b.value) ~ ('%' if c.percent else '') }}</td></tr>{% endfor %}
</table></details>
{% endmacro %}"""

DASHBOARD = """{% extends "base" %}{% from "chart" import chart %}{% from "nav" import top, task_row with context %}{% from "pa" import briefing with context %}{% block body %}
{% macro mytasks() %}
<section class="card" id="mytasks">
  <h2>My team tasks ({{ my_tasks|length }})</h2>
  <ul class="list">
  {% for t in my_tasks %}{{ task_row(t, me, members, csrf, '/#mytasks') }}
  {% else %}<li class="empty">Nothing assigned to you. <a href="/team#new">Add a task</a></li>{% endfor %}
  </ul>
</section>
{% endmacro %}
{{ top('home', me, csrf, today) }}
{% if msg %}<div class="flash" role="status">{{ msg }}</div>{% endif %}
{% if is_owner and not setup_done %}
<section class="card setup-nudge">
  <div><h2 style="margin:0">Welcome to NeuraNova PA</h2><div class="sub">A 10-step setup connects email, WhatsApp, calendar, AI and your applications. Every step can be skipped.</div></div>
  <a class="btn" href="/setup">Start setup</a>
</section>
{% endif %}
{% if b %}{{ briefing(b, True) }}{% endif %}
{% if not is_owner %}{{ mytasks() }}{% endif %}
{% if is_owner and setup and setup.connected < setup.total and setup_done %}
<section class="card setup-nudge">
  <div><h2 style="margin:0">Finish connecting your accounts</h2>
    <div class="sub">{{ setup.connected }} of {{ setup.total }} connected{% if setup.missing %}. Still to do: {{ setup.missing|join(', ') }}{% endif %}.</div></div>
  <a class="btn" href="/integrations" style="text-decoration:none">Open Integrations</a>
</section>
{% endif %}
<div class="tabs row">{% for d in [7, 30, 90] %}<a href="/?days={{ d }}" class="{{ 'on' if d == days else '' }}">{{ d }} days</a> {% endfor %}</div>

<div class="grid3 row">
  {% set b = p.business %}
  <section class="card">
    <h2>Develop the business</h2>
    <span class="pill s-{{ b.status }}"><span class="dot" aria-hidden="true">{{ labels_for[b.status][0] }}</span>{{ labels_for[b.status][1] }}</span>
    <div class="hero">{{ b.new_leads }}</div><div class="sub">new leads in {{ days }} days</div>
    <div class="kv"><span>Meetings</span><span>{{ b.meetings }}</span></div>
    <div class="kv"><span>Proposals sent</span><span>{{ b.proposals_sent }}</span></div>
    <div class="kv"><span>Deals won / lost</span><span>{{ b.deals_won }} / {{ b.deals_lost }}</span></div>
    <div class="kv"><span>Won value</span><span>{{ '{:,.0f}'.format(b.won_value) }}</span></div>
  </section>
  {% set r = p.responses %}
  <section class="card">
    <h2>Give proper responses</h2>
    <span class="pill s-{{ r.status }}"><span class="dot" aria-hidden="true">{{ labels_for[r.status][0] }}</span>{{ labels_for[r.status][1] }}</span>
    <div class="hero">{{ '–' if r.on_time_pct is none else r.on_time_pct ~ '%' }}</div><div class="sub">replied within {{ sla_hours }} business hours</div>
    <div class="kv"><span>On time / late</span><span>{{ r.on_time }} / {{ r.late }}</span></div>
    <div class="kv"><span>Overdue right now</span><span class="{{ 'over' if r.overdue_now else '' }}">{{ r.overdue_now }}</span></div>
    <div class="kv"><span>Waiting (not yet due)</span><span>{{ r.open }}</span></div>
    <div class="kv"><span>Median time to reply</span><span>{{ '–' if r.median_reply_hours is none else r.median_reply_hours ~ ' h' }}</span></div>
  </section>
  {% set q = p.quality %}
  <section class="card">
    <h2>Deliver high quality</h2>
    <span class="pill s-{{ q.status }}"><span class="dot" aria-hidden="true">{{ labels_for[q.status][0] }}</span>{{ labels_for[q.status][1] }}</span>
    <div class="hero">{{ '–' if q.overall_on_time_pct is none else q.overall_on_time_pct ~ '%' }}</div><div class="sub">on time (deliveries &amp; team deadlines, whichever is lower)</div>
    <div class="kv"><span>Delivered on time / late</span><span>{{ q.deliveries_on_time }} / {{ q.deliveries_late }}</span></div>
    <div class="kv"><span>Team deadlines met</span><span>{{ '–' if q.team_tasks_on_time_pct is none else q.team_tasks_on_time_pct ~ '%' }}</span></div>
    <div class="kv"><span>Rework requests</span><span>{{ q.rework }}</span></div>
    <div class="kv"><span>Feedback 👍 / 👎</span><span>{{ q.feedback_positive }} / {{ q.feedback_negative }}</span></div>
  </section>
</div>

<div class="grid2 row">
  <section class="card"><h2>Replies on time, by week</h2>{{ chart(chart_ontime, "Replies on time by week, percent", "Replies on time", "– = no replies were due that week") }}</section>
  <section class="card"><h2>New leads, by week</h2>{{ chart(chart_leads, "New leads by week", "New leads") }}</section>
</div>

{% if is_owner %}{{ mytasks() }}
<section class="card" id="drafts">
  <h2>Drafts to approve ({{ drafts|length }})</h2>
  {% for d in drafts %}
  <div class="draft" style="margin-bottom:20px">
    <div><strong>#{{ d.id }} → {{ d.to }}</strong> <span class="meta">· {{ d.subject }}{% if d.deadline %} · reply by {{ d.deadline }}{% endif %}</span></div>
    <div class="meta">{{ d.summary }}</div>
    {% for q in d.needs %}{% if loop.first %}<div class="needs"><strong>Needs you:</strong><ul style="margin:4px 0 0 18px;padding:0">{% endif %}<li>{{ q }}</li>{% if loop.last %}</ul></div>{% endif %}{% endfor %}
    <form method="post" action="/drafts/{{ d.id }}/edit">
      <input type="hidden" name="csrf" value="{{ csrf }}">
      <label class="sr" for="body{{ d.id }}" hidden>Reply text</label>
      <textarea id="body{{ d.id }}" name="body" rows="{{ [d.body.count('\n') + 4, 6]|max }}">{{ d.body }}</textarea>
      <div class="actions">
        <button type="submit">Save changes</button>
        <button class="primary" type="submit" formaction="/drafts/{{ d.id }}/send">Save &amp; send</button>
        <button type="submit" formaction="/drafts/{{ d.id }}/skip">Skip</button>
      </div>
    </form>
  </div>
  {% else %}<p class="empty">No drafts waiting. 🎉</p>{% endfor %}
</section>

<div class="grid2 row">
  <section class="card">
    <h2>Waiting for your reply ({{ waiting|length }})</h2>
    <ul class="list">
    {% for w in waiting %}
      <li><strong>{{ w.from }}</strong> · {{ w.subject }}<div class="meta">{{ w.summary }}</div>
        <div class="meta {{ 'over' if w.overdue else '' }}">{{ 'Overdue since' if w.overdue else 'Reply by' }} {{ w.deadline }}{% if w.link %} · <a href="{{ w.link }}" target="_blank" rel="noopener">open email</a>{% endif %}</div>
        {% if members|length > 1 %}
        <form class="task-actions" method="post" action="/team/tasks/from-email/{{ w.id }}">
          <input type="hidden" name="csrf" value="{{ csrf }}">
          <select name="assignee" aria-label="Delegate to">{% for m in members if m.id != me.id %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select>
          <input name="due_date" type="date" aria-label="Due date"><button type="submit">Delegate</button>
        </form>{% endif %}</li>
    {% else %}<li class="empty">Nothing waiting. 🎉</li>{% endfor %}
    </ul>
  </section>
  <section class="card">
    <h2>Tasks today &amp; overdue ({{ tasks|length }})</h2>
    {% if tasks_error %}<p class="empty">{{ tasks_error }}</p>{% endif %}
    <ul class="list">
    {% for t in tasks %}
      <li><strong>{{ t.label }}</strong> {{ t.content }}<div class="meta {{ 'over' if t.overdue else '' }}">{{ t.when }} · <a href="{{ t.url }}" target="_blank" rel="noopener">open</a></div></li>
    {% else %}{% if not tasks_error %}<li class="empty">No tasks due.</li>{% endif %}{% endfor %}
    </ul>
  </section>
</div>

{% endif %}

<section class="card" id="events">
  <h2>Log progress</h2>
  <p class="sub">Record what happened so the goal cards stay accurate. You can also just tell the bot on WhatsApp, e.g. "delivered the Acme site on time".</p>
  <form class="event-form" method="post" action="/events">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label>What<br><select name="kind">{% for k, v in kinds.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select></label>
    <label>Client<br><input name="client" maxlength="120"></label>
    <label>Value<br><input name="value" inputmode="decimal" maxlength="20"></label>
    <label>Date<br><input name="on_date" type="date" value="{{ today_iso }}"></label>
    <label>Note<br><input name="note" maxlength="300"></label>
    <button class="primary" type="submit">Add</button>
  </form>
  <div class="scroll"><table style="margin-top:12px">
    <tr><th>Date</th><th>What</th><th>Client</th><th>Value</th><th>Note</th><th></th></tr>
    {% for e in events %}
    <tr><td>{{ e.on_date }}</td><td>{{ kinds.get(e.kind, e.kind) }}</td><td>{{ e.client }}</td><td>{{ '' if e.value is none else '{:,.0f}'.format(e.value) }}</td><td>{{ e.note }}</td>
      <td>{% if me.role == 'admin' %}<form class="inline" method="post" action="/events/{{ e.id }}/delete"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="link" type="submit" aria-label="Delete event">✕</button></form>{% endif %}</td></tr>
    {% else %}<tr><td colspan="6" class="empty">Nothing logged yet.</td></tr>{% endfor %}
  </table></div>
</section>

{% endblock %}"""

def manifest(brand) -> dict:
    return {
        "name": brand["name"], "short_name": brand["name"], "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": brand["accent"],
        "icons": [{"src": "/brand/logo", "sizes": "256x256", "type": "image/png", "purpose": "any"}],
    }






JOIN = """{% extends "base" %}{% from "nav" import brand_logo, brand_wordmark with context %}{% block body %}
<div class="card login">
  <div class="brand" style="margin-bottom:12px">{{ brand_logo() }}<div class="brand-name">{{ brand_wordmark() }}</div></div>
  <h1>Join the team</h1>
  {% if error %}<p class="over">{{ error }}</p>{% endif %}
  {% if invite %}
  <p class="sub">Hi {{ invite.name }} - choose a password for <strong>{{ invite.email }}</strong>.</p>
  <form method="post" action="/join/{{ token }}">
    <label for="pw">Password (at least 10 characters)</label>
    <input id="pw" name="password" type="password" autocomplete="new-password" minlength="10" required autofocus>
    <button class="primary" type="submit">{{ 'Set password' if invite.user_id else 'Join the team' }}</button>
  </form>
  {% endif %}
</div>
{% endblock %}"""

LINK = """{% extends "base" %}{% from "nav" import top with context %}{% block body %}
{{ top('team', me, csrf, today) }}
<section class="card">
  <h2>{{ title }}</h2>
  <p>Send this link to <strong>{{ name }}</strong> ({{ email }}) yourself, e.g. on WhatsApp. It works once and expires in 7 days.
  It's shown only now, so copy it before leaving this page.</p>
  <input class="copy" readonly value="{{ link }}" onclick="this.select()" aria-label="Invite link">
  <p><a href="/team#people">Back to the team</a></p>
</section>
{% endblock %}"""

TEAM = """{% extends "base" %}{% from "nav" import top, task_row with context %}{% block body %}
{{ top('team', me, csrf, today) }}
{% if msg %}<div class="flash" role="status">{{ msg }}</div>{% endif %}

<section class="card">
  <h2>Who's working on what (last 7 days)</h2>
  <div class="scroll"><table>
    <tr><th>Person</th><th>Open</th><th>Blocked</th><th>Overdue</th><th>Done</th><th>On time</th></tr>
    {% for s in stats %}
    <tr><td>{{ s.name }}</td><td>{{ s.open }}</td><td>{{ s.blocked }}</td><td class="{{ 'over' if s.overdue else '' }}">{{ s.overdue }}</td><td>{{ s.done }}</td><td>{{ '–' if s.on_time_pct is none else s.on_time_pct ~ '%' }}</td></tr>
    {% endfor %}
  </table></div>
</section>

<section class="card" id="new">
  <h2>New team task</h2>
  <form class="form-grid" method="post" action="/team/tasks">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label>Task<br><input name="title" maxlength="200" required placeholder="Send banner drafts to Acme"></label>
    <label>Who<br><select name="assignee">{% for m in members %}<option value="{{ m.id }}" {{ 'selected' if m.id == me.id else '' }}>{{ m.name }}</option>{% endfor %}</select></label>
    <label>Due date<br><input name="due_date" type="date"></label>
    <label>Time<br><input name="due_time" type="time"></label>
    <label>Notes<br><input name="notes" maxlength="500"></label>
    <button class="primary" type="submit">Add task</button>
  </form>
</section>

<section class="card" id="board">
  <h2>Team board</h2>
  <div class="tabs" style="margin-bottom:12px">
    {% for key, label in [('open', 'Open'), ('mine', 'Mine'), ('blocked', 'Blocked'), ('done', 'Done')] %}<a href="/team?view={{ key }}#board" class="{{ 'on' if view == key else '' }}">{{ label }}</a> {% endfor %}
  </div>
  <ul class="list">
  {% for t in tasks %}{{ task_row(t, me, members, csrf, '/team?view=' ~ view ~ '#board') }}
  {% else %}<li class="empty">Nothing here.</li>{% endfor %}
  </ul>
</section>

{% if me.role == 'admin' %}
<section class="card" id="people">
  <h2>People</h2>
  <div class="scroll"><table>
    <tr><th>Name</th><th>Email</th><th>Role</th><th>WhatsApp</th><th></th></tr>
    {% for u in people %}
    <tr class="{{ '' if u.active else 'muted-row' }}">
      <td>{{ u.name }}{% if not u.active %} (inactive){% endif %}</td><td>{{ u.email }}</td>
      {% if u.id == me.id or u.id == owner_id %}
      <td>{{ u.role }}</td><td>{{ u.whatsapp or '–' }}</td><td class="meta">{{ 'you' if u.id == me.id else 'founder' }}</td>
      {% else %}
      <td colspan="2"><form class="task-actions" method="post" action="/team/people/{{ u.id }}/update" style="margin:0">
        <input type="hidden" name="csrf" value="{{ csrf }}">
        <select name="role" aria-label="Role">{% for r in ['member', 'admin'] %}<option {{ 'selected' if u.role == r else '' }}>{{ r }}</option>{% endfor %}</select>
        <input name="whatsapp" value="{{ u.whatsapp }}" placeholder="919876543210" inputmode="tel" maxlength="20" aria-label="WhatsApp number">
        <button type="submit">Save</button></form></td>
      <td><div class="task-actions" style="margin:0">
        <form class="inline" method="post" action="/team/people/{{ u.id }}/reset"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Reset link</button></form>
        <form class="inline" method="post" action="/team/people/{{ u.id }}/{{ 'deactivate' if u.active else 'activate' }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">{{ 'Deactivate' if u.active else 'Activate' }}</button></form>
      </div></td>
      {% endif %}
    </tr>
    {% endfor %}
  </table></div>

  <h2 style="margin-top:20px">Invite someone</h2>
  <form class="form-grid" method="post" action="/team/invite">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label>Name<br><input name="name" maxlength="80" required></label>
    <label>Email<br><input name="email" type="email" maxlength="160" required></label>
    <label>Role<br><select name="role"><option>member</option><option>admin</option></select></label>
    <label>WhatsApp (optional)<br><input name="whatsapp" inputmode="tel" maxlength="20" placeholder="919876543210"></label>
    <button class="primary" type="submit">Create invite link</button>
  </form>
  {% if invites %}
  <h2 style="margin-top:20px">Waiting to join</h2>
  <ul class="list">{% for i in invites %}
    <li>{{ i.name }} · {{ i.email }} · {{ i.role }}{% if i.user_id %} (password reset){% endif %} <span class="meta">· expires {{ i.expires }}</span>
      <form class="inline" method="post" action="/team/invites/{{ i.token_hash }}/revoke"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="link" type="submit">Revoke</button></form></li>
  {% endfor %}</ul>
  {% endif %}
</section>
{% endif %}
{% endblock %}"""

INTEGRATIONS = """{% extends "base" %}{% from "nav" import top with context %}{% block body %}
{% macro status_pill(c) %}{% set st = {'connected': ('good', '✓', 'Connected'), 'error': ('critical', '✕', 'Needs attention'),
   'ready': ('ready', '…', 'Not tested'), 'not_connected': ('none', '–', 'Not connected'),
   'disabled': ('none', '⏸', 'Disabled'), 'expired': ('warning', '!', 'Expired — reconnect')}[c.status] %}
<span class="pill s-{{ st[0] }}"><span class="dot" aria-hidden="true">{{ st[1] }}</span>{{ st[2] }}</span>{% endmacro %}
{% macro email_card(c) %}
{% set f = {} %}{% for x in c.fields %}{% set _ = f.update({x.key: x}) %}{% endfor %}
<section class="card int-card email-card" id="email">
  <div class="int-head">
    <div class="int-badge" aria-hidden="true">@</div>
    <div style="min-width:0"><h2>Email</h2><p>{{ c.summary }}</p></div>
    {{ status_pill(c) }}
  </div>
  <div class="chips">{% for u in c.unlocks %}<span class="chip">{{ u }}</span>{% endfor %}<span class="chip rec">Recommended</span></div>
  {% if c.message %}<div class="int-status {{ 'error' if c.status == 'error' else '' }}">{% if c.account %}<strong>{{ c.account }}</strong> · {% endif %}{{ c.message }}{% if c.checked %}<span class="meta"> · checked {{ c.checked }}</span>{% endif %}</div>{% endif %}

  <ol class="wizard">
    <li class="{{ 'done' if f.EMAIL_ADDRESS.has_value else 'now' }}">
      <div class="w-title">Your email address</div>
      <form class="w-row" method="post" action="/integrations/email/detect">
        <input type="hidden" name="csrf" value="{{ csrf }}">
        <input id="email-address" name="address" type="email" required autocomplete="email" aria-label="Email address"
               value="{{ f.EMAIL_ADDRESS.shown }}" placeholder="you@neuranova.in" {{ 'disabled' if f.EMAIL_ADDRESS.env else '' }}>
        <button class="{{ '' if f.EMAIL_ADDRESS.has_value else 'primary' }}" type="submit">{{ 'Change' if f.EMAIL_ADDRESS.has_value else 'Next' }}</button>
      </form>
      {% if c.provider %}<div class="meta">Detected: <strong>{{ c.provider.name }}</strong></div>{% endif %}
    </li>
    <li class="{{ 'off' if not f.EMAIL_ADDRESS.has_value else ('done' if f.EMAIL_APP_PASSWORD.has_value else 'now') }}">
      <div class="w-title">Create an app password</div>
      {% if c.provider %}
        <ul class="w-steps">{% for step in c.provider.steps %}<li>{{ step }}</li>{% endfor %}</ul>
        {% if c.provider.url %}<a class="btn" href="{{ c.provider.url }}" target="_blank" rel="noopener">Open {{ c.provider.name.split(' (')[0] }} app passwords ↗</a>{% endif %}
        <div class="meta" style="margin-top:6px">An app password is a separate password just for NeuraNova. You can delete it any time, and your normal password stays private.</div>
      {% else %}<div class="meta">Enter your address first.</div>{% endif %}
    </li>
    <li class="{{ 'off' if not f.EMAIL_ADDRESS.has_value else ('done' if c.status == 'connected' else 'now') }}">
      <div class="w-title">Paste it and connect</div>
      {% if f.EMAIL_ADDRESS.has_value %}
      <form class="int-fields" method="post" action="/integrations/email/save" autocomplete="off">
        <input type="hidden" name="csrf" value="{{ csrf }}">
        <input type="hidden" name="EMAIL_ADDRESS" value="{{ f.EMAIL_ADDRESS.shown }}">
        <input type="hidden" name="EMAIL_PROVIDER" value="{{ f.EMAIL_PROVIDER.shown }}">
        <label for="email-pw">App password
          <input id="email-pw" name="EMAIL_APP_PASSWORD" type="password" autocomplete="new-password"
                 placeholder="{{ ('Saved ' ~ f.EMAIL_APP_PASSWORD.shown ~ ' - leave blank to keep') if f.EMAIL_APP_PASSWORD.has_value else 'abcd efgh ijkl mnop' }}"></label>
        <details {{ 'open' if c.provider and not c.provider.known else '' }}>
          <summary>Server settings{% if c.provider and c.provider.known %} (filled in for you){% endif %}</summary>
          <div class="server-grid">
            {% for key in ['EMAIL_IMAP_HOST', 'EMAIL_IMAP_PORT', 'EMAIL_SMTP_HOST', 'EMAIL_SMTP_PORT'] %}{% set x = f[key] %}
            <label for="email-{{ key }}">{{ x.label }}<input id="email-{{ key }}" name="{{ key }}" value="{{ x.shown }}" placeholder="{{ x.placeholder }}"></label>
            {% endfor %}
          </div>
        </details>
        <div class="actions">
          <button class="primary" type="submit">{{ 'Save & test' if c.status == 'connected' else 'Connect' }}</button>
          {% if c.configured %}<button type="submit" formaction="/integrations/email/test">Test</button>
          <button class="link" type="submit" formaction="/integrations/email/disconnect">Disconnect</button>
          <button class="link" type="submit" formaction="/integrations/email/disable">Disable</button>{% endif %}
          {% if c.status == 'disabled' %}<button type="submit" formaction="/integrations/email/enable">Enable</button>{% endif %}
        </div>
      </form>
      {% endif %}
    </li>
  </ol>
</section>
{% endmacro %}
{{ top('integrations', me, csrf, today) }}
{% if msg %}<div class="flash" role="status">{{ msg }}</div>{% endif %}

<section class="card">
  <h2>Integrations</h2>
  <div class="int-summary">
    <strong>{{ progress.connected }} of {{ progress.total }} connected</strong>
    <div class="meter" role="img" aria-label="{{ progress.connected }} of {{ progress.total }} connected"><span style="width: {{ (100 * progress.connected / progress.total)|round|int }}%"></span></div>
    {% if progress.missing %}<span class="meta">Still to do: {{ progress.missing|join(', ') }}</span>{% endif %}
    <form class="inline" method="post" action="/integrations/test-all"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Test all</button></form>
  </div>
  <p class="sub" style="margin-bottom:0">Keys and sign-ins are stored encrypted on your own server and are checked every morning. If one stops working, you get a WhatsApp alert.</p>
</section>

{% for group in ['Email', 'AI', 'Messaging', 'Calendar & documents', 'Tasks', 'Email (advanced)'] %}
{% if group == 'Email (advanced)' %}<details class="advanced"><summary class="int-group">Advanced: connect email with Google or Microsoft sign-in instead</summary>{% else %}
<div class="int-group" {{ 'id=ai' if group == 'AI' else '' }}>{{ group }}</div>{% endif %}
{% if group == 'AI' %}
<form class="ai-switch card" method="post" action="/integrations/ai/provider">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <span>The PA uses</span>
  {% for key, label in [('claude', 'Claude'), ('openai', 'OpenAI')] %}
  <label class="radio"><input type="radio" name="provider" value="{{ key }}" {{ 'checked' if ai.current == key else '' }}
    {{ 'disabled' if ai.locked else '' }} onchange="this.form.submit()"> {{ label }}{% if not ai.have[key] %} <small class="meta">(not connected)</small>{% endif %}</label>
  {% endfor %}
  {% if ai.locked %}<span class="meta">Set in the .env file</span>{% endif %}
  <noscript><button type="submit">Save</button></noscript>
</form>
{% endif %}
<div class="int-grid">
{% for c in cards if c.category == group %}
  {% if c.wizard %}{{ email_card(c) }}{% else %}
  <section class="card int-card" id="{{ c.name }}">
    <div class="int-head">
      <div class="int-badge" aria-hidden="true">{{ c.title[0] }}</div>
      <div style="min-width:0"><h2>{{ c.title }}</h2><p>{{ c.summary }}</p></div>
      {{ status_pill(c) }}
    </div>
    <div class="chips" aria-label="Unlocks">{% for u in c.unlocks %}<span class="chip">{{ u }}</span>{% endfor %}</div>

    {% if c.message or c.account %}
    <div class="int-status {{ 'error' if c.status == 'error' else '' }}">
      {% if c.account %}<strong>{{ c.account }}</strong> · {% endif %}{{ c.message }}
      {% if c.checked %}<span class="meta"> · checked {{ c.checked }}</span>{% endif %}
    </div>
    {% endif %}

    <form class="int-fields" method="post" action="/integrations/{{ c.name }}/save" autocomplete="off">
      <input type="hidden" name="csrf" value="{{ csrf }}">
      {% for f in c.fields %}
      <label for="{{ c.name }}-{{ f.key }}">{{ f.label }}{% if not f.required %} <small>(optional)</small>{% endif %}
        {% if f.env %}
          <span class="locked">Set in the .env file{% if not f.secret %}: {{ f.shown }}{% endif %}</span>
        {% else %}
          <input id="{{ c.name }}-{{ f.key }}" name="{{ f.key }}" {{ 'type=password' if f.secret else '' }}
                 value="{{ '' if f.secret else f.shown }}"
                 placeholder="{{ ('Saved ' ~ f.shown ~ ' - leave blank to keep') if (f.secret and f.has_value) else f.placeholder }}">
        {% endif %}
        {% if f.help %}<small>{{ f.help }}</small>{% endif %}
      </label>
      {% endfor %}
      <div class="actions">
        {% if c.fields %}<button class="{{ '' if c.oauth else 'primary' }}" type="submit">Save &amp; test</button>{% endif %}
        {% if c.oauth %}
        <button class="primary" type="submit" formaction="/integrations/{{ c.oauth }}/connect">{{ 'Reconnect' if c.signed_in else 'Connect' }} with {{ 'Microsoft' if c.oauth == 'microsoft' else 'Google' }}</button>
        {% endif %}
        {% if c.configured %}<button type="submit" formaction="/integrations/{{ c.name }}/test">Test</button>{% endif %}
        {% if c.name == 'whatsapp' and c.configured %}<button type="submit" formaction="/integrations/whatsapp/send-test">Send me a test message</button>{% endif %}
        {% if c.configured or c.signed_in %}<button class="link" type="submit" formaction="/integrations/{{ c.name }}/disconnect">Disconnect</button>{% endif %}
        {% if c.status == 'disabled' %}<button type="submit" formaction="/integrations/{{ c.name }}/enable">Enable</button>
        {% elif c.configured or c.signed_in %}<button class="link" type="submit" formaction="/integrations/{{ c.name }}/disable">Disable</button>{% endif %}
      </div>
    </form>

    <details {{ 'open' if c.status == 'not_connected' else '' }}>
      <summary>How to set up {{ c.title }}</summary>
      <ol class="steps">{% for step in c.steps %}<li>{{ step }}</li>{% endfor %}</ol>
      {% if c.redirect_uri %}
      <div class="copyrow"><input readonly value="{{ c.redirect_uri }}" aria-label="Redirect URI" onclick="this.select()"><button type="button" data-copy="{{ c.redirect_uri }}">Copy</button></div>
      <small class="meta">Redirect URI: paste this into the {{ 'Microsoft' if c.oauth == 'microsoft' else 'Google' }} app settings.</small>
      {% endif %}
      {% if c.webhook_url %}
      <div class="copyrow"><input readonly value="{{ c.webhook_url }}" aria-label="Webhook URL" onclick="this.select()"><button type="button" data-copy="{{ c.webhook_url }}">Copy</button></div>
      <small class="meta">Webhook URL for Meta (must be a public https address).</small>
      {% if c.verify_token %}<div class="copyrow"><input readonly value="{{ c.verify_token }}" aria-label="Verify token" onclick="this.select()"><button type="button" data-copy="{{ c.verify_token }}">Copy</button></div>
      <small class="meta">Verify token for Meta.</small>{% endif %}
      {% endif %}
      <div class="ext-links">{% for label, url in c.links %}<a href="{{ url }}" target="_blank" rel="noopener">{{ label }} ↗</a>{% endfor %}</div>
    </details>
  </section>
  {% endif %}
{% endfor %}
</div>
{% if group == 'Email (advanced)' %}</details>{% endif %}
{% endfor %}
<script>
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-copy]'); if (!b) return;
  var done = function () { var t = b.textContent; b.textContent = 'Copied'; setTimeout(function () { b.textContent = t; }, 1500); };
  if (navigator.clipboard) navigator.clipboard.writeText(b.dataset.copy).then(done, function () { b.previousElementSibling.select(); });
  else b.previousElementSibling.select();
});
</script>
{% endblock %}"""

RETURN = """<!doctype html><html><head><meta charset="utf-8"><title>Connecting...</title>
<meta http-equiv="refresh" content="0;url={{ url }}"></head>
<body style="font-family: system-ui; padding: 24px">Finishing sign-in... <a href="{{ url }}">Continue</a></body></html>"""


env = Environment(
    loader=DictLoader({"base": BASE, "login": LOGIN, "dashboard": DASHBOARD, "chart": CHART, "nav": NAV,
                       "join": JOIN, "link": LINK, "team": TEAM, "integrations": INTEGRATIONS, "return": RETURN}),
    autoescape=select_autoescape(default=True, default_for_string=True),
)
env.globals["brand"] = {"name": "NeuraNova", "tagline": "Personal Assistant", "accent": "#8705a1",
                        "accent_dark": "#a06ad9"}

from .pa_templates import register as _register_pa  # noqa: E402

_register_pa(env)
