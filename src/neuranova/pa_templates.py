"""Templates for the NeuraNova PA pages (Jinja2, autoescaped). Registered into templates.env."""

PA_CSS = """
/* PA */
.brief { border-left: 4px solid var(--accent); }
.brief h2 { font-size: 20px; margin-bottom: 4px; }
.headline { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 4px; }
.headline a { text-decoration: none; color: var(--ink); background: var(--page); border: 1px solid var(--border); border-radius: 999px;
              padding: 3px 10px; font-size: 13px; }
.headline a strong { font-variant-numeric: tabular-nums; }
ol.next { margin: 8px 0 0; padding-left: 22px; display: grid; gap: 6px; }
ol.next li .meta { display: block; }
.k { display: inline-block; font-size: 11px; font-weight: 650; padding: 1px 7px; border-radius: 6px; background: var(--page);
     border: 1px solid var(--border); color: var(--ink-2); margin-right: 4px; vertical-align: 1px; }
.k.urgent { border-color: var(--critical); color: var(--critical); }
.k.high { border-color: var(--serious); }
.k.sig { background: color-mix(in srgb, var(--accent) 12%, var(--surface)); border-color: transparent; color: var(--accent); }
.item-title { font-weight: 600; text-decoration: none; color: var(--ink); }
.item-title:hover { text-decoration: underline; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: end; }
.filters label { display: grid; gap: 2px; font-size: 12px; color: var(--ink-2); }
.cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(230px, 100%), 1fr)); gap: 12px; }
.col { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px; min-width: 0; }
.col h3 { font: 600 13px var(--font-display); margin: 0 0 8px; color: var(--ink-2); text-transform: uppercase; letter-spacing: .04em; }
.col ul.list li { font-size: 14px; }
.stat { display: flex; gap: 16px; flex-wrap: wrap; }
.stat div { min-width: 110px; }
.stat .hero { font-size: 26px; margin: 0; }
.chat { display: grid; gap: 10px; max-height: 60vh; overflow-y: auto; padding: 4px; }
.bubble { max-width: 85%; padding: 8px 12px; border-radius: 12px; white-space: pre-wrap; font-size: 14px; }
.bubble.you { justify-self: end; background: var(--accent); color: var(--accent-ink); }
.bubble.pa { justify-self: start; background: var(--page); border: 1px solid var(--border); }
.chat-form { display: flex; gap: 8px; margin-top: 12px; }
.chat-form textarea { flex: 1; min-height: 44px; font: inherit; color: var(--ink); background: var(--page); border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
.suggest { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.suggest button { font-size: 13px; padding: 3px 10px; border-radius: 999px; }
.report-text { white-space: pre-wrap; font-size: 15px; line-height: 1.6; }
.settings-wrap { display: grid; grid-template-columns: 210px 1fr; gap: 16px; align-items: start; }
.settings-nav { display: grid; gap: 2px; }
.settings-nav a { text-decoration: none; color: var(--ink-2); padding: 6px 10px; border-radius: 8px; font-size: 14px; }
.settings-nav a.on { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--ink); font-weight: 600; }
@media (max-width: 700px) { .settings-wrap { grid-template-columns: 1fr; } .settings-nav { display: flex; flex-wrap: wrap; } }
.fields { display: grid; gap: 12px; max-width: 640px; }
.fields label { display: grid; gap: 4px; font-size: 14px; font-weight: 550; }
.fields label small, .fields .hint { color: var(--muted); font-weight: 400; font-size: 13px; }
.fields input:not([type=checkbox]):not([type=radio]), .fields select, .fields textarea { width: 100%; font-weight: 400; }
.fields textarea { font: 13px/1.5 ui-monospace, monospace; color: var(--ink); background: var(--page); border: 1px solid var(--border); border-radius: 8px; padding: 8px; min-height: 140px; }
.check { display: flex !important; grid-template-columns: none; gap: 8px; align-items: center; font-weight: 400 !important; }
.days { display: flex; gap: 10px; flex-wrap: wrap; }
.safe-on { color: var(--good-ink); font-weight: 650; }
.safe-off { color: var(--critical); font-weight: 650; }
.steps-bar { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 16px; }
.steps-bar a { font-size: 12px; text-decoration: none; padding: 3px 9px; border-radius: 999px; border: 1px solid var(--border); color: var(--ink-2); }
.steps-bar a.on { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
.steps-bar a.done { color: var(--good-ink); }
.evidence img { max-width: 100%; border: 1px solid var(--border); border-radius: 8px; }
textarea.body { width: 100%; min-height: 110px; font: inherit; color: var(--ink); background: var(--page); border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
/* ===== NeuraNova theme: like the logo - white, with soft see-through petals; the "N" gradient for action ===== */
:root {
  --petal-coral: rgba(246,72,72,.62); --petal-orange: rgba(255,92,52,.62); --petal-pink: rgba(236,74,110,.55);
  --petal-orchid: rgba(150,40,160,.55); --petal-violet: rgba(98,26,150,.62); --petal-periwinkle: rgba(80,70,200,.58);
  --petal-blue: rgba(40,110,185,.62); --petal-sky: rgba(70,140,200,.55);
  --nn-n: linear-gradient(120deg, #f26a1b 0%, #f2293f 22%, #e70c63 38%, #8705a1 62%, #4b129a 82%, #33449e 100%);
  --nn-grad: var(--nn-n);
  --nn-grad-soft: linear-gradient(120deg, rgba(255,92,52,.10), rgba(236,74,110,.10) 30%, rgba(150,40,160,.10) 60%, rgba(70,140,200,.12));
  --nn-title: #3b0d6b; --nn-crimson: #e70c63; --nn-magenta: #8705a1;
  --page: #fdfbff; --surface: #ffffff; --accent: #8705a1; --series-1: #8a3fb8;
  --shadow: 0 1px 2px rgba(59,13,107,.05), 0 8px 28px rgba(59,13,107,.07);
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --page: #120d1c; --surface: #1b1428; --nn-title: #f1e4ff; --accent: #d08cf2; --series-1: #c58af0;
  --shadow: 0 1px 2px rgba(0,0,0,.4); } }
:root[data-theme="dark"] { --page: #120d1c; --surface: #1b1428; --nn-title: #f1e4ff; --accent: #d08cf2; --series-1: #c58af0; --shadow: 0 1px 2px rgba(0,0,0,.4); }

/* page backdrop: big soft petals in the corners, overlapping like the logo */
body { background: var(--page); }
body::before { content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: .16;
  background:
    radial-gradient(circle 260px at 104% -6%, var(--petal-sky) 99%, transparent 100%),
    radial-gradient(circle 260px at 90% -14%, var(--petal-blue) 99%, transparent 100%),
    radial-gradient(circle 240px at 100% 108%, var(--petal-periwinkle) 99%, transparent 100%),
    radial-gradient(circle 240px at 88% 116%, var(--petal-orchid) 99%, transparent 100%),
    radial-gradient(circle 220px at 20% 112%, var(--petal-pink) 99%, transparent 100%); }
main { position: relative; z-index: 1; }
.brand-strip { height: 4px; background: var(--nn-n); position: relative; z-index: 6; }

/* sidebar: white, like the logo's centre */
nav.side { background: var(--surface); border-right: 1px solid rgba(59,13,107,.08); box-shadow: 2px 0 24px rgba(59,13,107,.05); }
nav.side .brand-name { white-space: nowrap; font-size: 19px; color: var(--nn-title); }
.brand-name .nova { background: var(--nn-n); -webkit-background-clip: text; background-clip: text; color: transparent; }
nav.side .brand img { width: 44px; height: 44px; }
nav.side .pa-tag, .pa-tag { background: var(--nn-n); color: #fff; }
.nav-links a { position: relative; color: var(--ink-2); }
.nav-links a:hover { background: var(--nn-grad-soft); color: var(--ink); }
.nav-links a.on { background: var(--nn-grad-soft); color: var(--nn-title); font-weight: 650; }
.nav-links a.on::before { content: ""; position: absolute; left: 0; top: 7px; bottom: 7px; width: 3px; border-radius: 3px; background: var(--nn-n); }
@media (max-width: 900px) { nav.side { background: var(--surface); border-radius: 0 0 16px 16px; padding: 12px 14px; margin: -16px -16px 16px; box-shadow: var(--shadow); } }

/* page header */
header.pagehead h1 { color: var(--nn-title); font-size: 26px; letter-spacing: -.01em; }
header.pagehead h1::after { content: ""; display: block; width: 44px; height: 4px; border-radius: 4px; background: var(--nn-n); margin-top: 6px; }
form.quick input { background: var(--surface); border-radius: 999px; padding: 8px 14px; box-shadow: var(--shadow); border-color: transparent; }

/* cards */
.card, .col { border-radius: 18px; border-color: transparent; box-shadow: var(--shadow); }
.card h2, .col h3 { color: var(--nn-title); }
.hero { color: var(--nn-title); }
.stat .hero { background: var(--nn-n); -webkit-background-clip: text; background-clip: text; color: transparent; }
.brief { border-left: 0; position: relative; overflow: hidden; background: var(--surface); }
.brief::after { content: ""; position: absolute; right: -60px; top: -60px; width: 240px; height: 240px; pointer-events: none; opacity: .22;
  background:
    radial-gradient(circle 44px at 50% 24%, var(--petal-sky) 99%, transparent 100%),
    radial-gradient(circle 44px at 68% 32%, var(--petal-blue) 99%, transparent 100%),
    radial-gradient(circle 44px at 76% 50%, var(--petal-periwinkle) 99%, transparent 100%),
    radial-gradient(circle 44px at 68% 68%, var(--petal-violet) 99%, transparent 100%),
    radial-gradient(circle 44px at 50% 76%, var(--petal-orchid) 99%, transparent 100%),
    radial-gradient(circle 44px at 32% 68%, var(--petal-pink) 99%, transparent 100%),
    radial-gradient(circle 44px at 24% 50%, var(--petal-orange) 99%, transparent 100%),
    radial-gradient(circle 44px at 32% 32%, var(--petal-coral) 99%, transparent 100%); }
.brief::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 4px; background: var(--nn-n); }
.brief h2 { font-size: 22px; }
.headline a { background: var(--nn-grad-soft); border-color: transparent; }
.headline a strong { color: var(--nn-crimson); }
ol.next li::marker { color: var(--nn-magenta); font-weight: 700; }
.setup-nudge { background: var(--nn-n); color: #fff; }
.setup-nudge h2, .setup-nudge .sub { color: #fff; }
.setup-nudge .btn { background: #fff; color: var(--nn-magenta); border: 0; font-weight: 600; }

/* controls */
button, .btn { border-radius: 10px; }
button.primary { background: var(--nn-n); border: 0; color: #fff; font-weight: 600; box-shadow: 0 4px 14px rgba(135,5,161,.25); }
button.primary:hover { filter: brightness(1.06); }
.tabs a.on, .steps-bar a.on { background: var(--nn-n); border-color: transparent; color: #fff; }
.k.sig { background: rgba(231,12,99,.09); color: var(--nn-crimson); }
.k.urgent { background: rgba(242,41,63,.08); }
.chip.rec { background: rgba(135,5,161,.09); color: var(--nn-magenta); }
.meter span { background: var(--nn-n); }
.bubble.you { background: var(--nn-n); }
.flash { border-left: 0; position: relative; overflow: hidden; padding-left: 16px; }
.flash::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--nn-n); }
input:focus, select:focus, textarea:focus { outline: 2px solid rgba(135,5,161,.30); outline-offset: 1px; }
.int-badge { background: var(--nn-grad-soft), var(--surface); color: var(--nn-magenta); }

/* sign-in and join: the logo's petal flower behind a white card */
body:has(.login)::before { opacity: 1; background:
    radial-gradient(circle 190px at calc(50% - 0px) calc(50% - 250px), var(--petal-sky) 99%, transparent 100%),
    radial-gradient(circle 190px at calc(50% + 177px) calc(50% - 177px), var(--petal-blue) 99%, transparent 100%),
    radial-gradient(circle 190px at calc(50% + 250px) 50%, var(--petal-periwinkle) 99%, transparent 100%),
    radial-gradient(circle 190px at calc(50% + 177px) calc(50% + 177px), var(--petal-violet) 99%, transparent 100%),
    radial-gradient(circle 190px at 50% calc(50% + 250px), var(--petal-orchid) 99%, transparent 100%),
    radial-gradient(circle 190px at calc(50% - 177px) calc(50% + 177px), var(--petal-pink) 99%, transparent 100%),
    radial-gradient(circle 190px at calc(50% - 250px) 50%, var(--petal-orange) 99%, transparent 100%),
    radial-gradient(circle 190px at calc(50% - 177px) calc(50% - 177px), var(--petal-coral) 99%, transparent 100%); }
body:has(.login) main { display: grid; place-items: center; min-height: calc(100vh - 4px); padding: 16px; }
.login { position: relative; margin: 0 auto; border-radius: 50%; width: min(420px, 92vw); max-width: none; aspect-ratio: 1; padding: 48px 56px;
         display: flex; flex-direction: column; justify-content: center; box-shadow: 0 10px 40px rgba(59,13,107,.18); }
.login .brand { flex-direction: column; text-align: center; gap: 4px; margin-bottom: 4px !important; }
.login .brand img { width: 64px; height: 64px; }
.login .brand-name { font-size: 22px; color: var(--nn-title); }
.login > .sub { text-align: center; margin: 2px 0 6px; }
.login input { margin: 4px 0 8px; }
.login label { font-size: 13px; font-weight: 600; color: var(--ink-2); }
.login button.primary { width: 100%; padding: 10px; font-size: 15px; margin-top: 4px; }
@media (max-width: 520px) { body:has(.login)::before { opacity: .5; } .login { border-radius: 24px; aspect-ratio: auto; padding: 28px; } }
/* friendlier shell: icons, quick add, page help */
.ico { fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: none; }
.nav-links a { display: flex; align-items: center; gap: 10px; }
.nav-links a .ico { opacity: .75; }
.nav-links a.on .ico { opacity: 1; color: var(--nn-magenta); }
header.pagehead .sub { max-width: 640px; }
.head-actions { display: flex; gap: 10px; align-items: center; position: relative; }
.quickadd > summary { list-style: none; display: inline-flex; align-items: center; gap: 6px; background: var(--nn-n); color: #fff; border: 0;
  font-weight: 600; padding: 8px 14px; border-radius: 999px; box-shadow: 0 4px 14px rgba(135,5,161,.25); cursor: pointer; }
.quickadd > summary::-webkit-details-marker { display: none; }
.quickadd-pop { position: absolute; right: 0; top: calc(100% + 8px); width: min(380px, 90vw); background: var(--surface); border-radius: 16px;
  padding: 16px; box-shadow: 0 16px 40px rgba(59,13,107,.22); display: grid; gap: 8px; z-index: 20; }
.quickadd-pop label { font-weight: 600; color: var(--nn-title); }
.quickadd-pop input[name=text] { width: 100%; font-size: 15px; padding: 10px; }
.quickadd-row { display: flex; gap: 8px; } .quickadd-row select { flex: 1; }
.flash { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.flash-x { border: 0; background: none; font-size: 20px; line-height: 1; color: var(--muted); padding: 0 4px; cursor: pointer; }
@media (max-width: 900px) { .head-actions { width: 100%; } .head-actions form.quick { flex: 1; } form.quick input { width: 100%; } }
/* compact item rows */
ul.rows li.row-item, ul.list li.row-item { display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; }
.row-main { flex: 1; min-width: 0; }
.row-main .k { margin: 0 0 0 6px; }
.tick { width: 26px; height: 26px; border-radius: 50%; border: 2px solid rgba(135,5,161,.35); background: var(--surface); color: transparent;
  display: inline-grid; place-items: center; padding: 0; font-size: 14px; font-weight: 700; flex: none; cursor: pointer; transition: all .15s; }
.tick:hover { background: var(--nn-n); color: #fff; border-color: transparent; }
.tick.ghost { border: 0; background: var(--nn-grad-soft); color: var(--nn-magenta); cursor: default; font-size: 13px; }
.snooze { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: var(--nn-grad-soft); border: 0; color: var(--nn-title); white-space: nowrap; }
.meta .due { color: var(--nn-title); font-weight: 600; }
h3.group-h { font: 600 13px var(--font-display); text-transform: uppercase; letter-spacing: .05em; color: var(--nn-title); margin: 18px 0 2px; }
h3.group-h.over { color: var(--critical); }
.quickbar-form { display: flex; gap: 8px; flex-wrap: wrap; }
.quickbar-form input { flex: 1 1 320px; font-size: 15px; padding: 10px 12px; }
.quickbar-form select { flex: 0 0 auto; }
.backlink { display: inline-block; margin-bottom: 10px; text-decoration: none; font-weight: 600; }
.form-grid .check input, .fields .check input { width: auto !important; }
.fields .form-grid { align-items: start; }
.repeat { color: var(--nn-magenta); font-weight: 600; }
.update-pill { display: grid; gap: 2px; text-decoration: none; background: var(--nn-grad-soft); border-radius: 12px; padding: 8px 12px;
  font-weight: 650; color: var(--nn-title); font-size: 13px; }
.update-pill span { font-weight: 400; color: var(--nn-magenta); text-decoration: underline; }
.gs-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
ul.gs-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); }
ul.gs-list li { display: grid; grid-template-columns: 22px 1fr; column-gap: 10px; align-items: start; }
ul.gs-list li .meta { grid-column: 2; display: block; }
ul.gs-list li a { font-weight: 600; }
ul.gs-list li.done { color: var(--muted); }
.gs-dot { width: 22px; height: 22px; border-radius: 50%; display: inline-grid; place-items: center; font-size: 12px; font-weight: 700; flex: none;
  background: var(--nn-grad-soft); color: var(--nn-magenta); }
li.done .gs-dot { background: var(--good); color: #fff; }
.acct { display: grid; grid-template-columns: 130px 1fr 1fr auto; gap: 6px; align-items: center; }
@media (max-width: 700px) { .acct { grid-template-columns: 1fr; } }
"""

PA_MACROS = """
{% macro flash(msg) %}{% if msg %}<div class="flash" role="status">{{ msg }}</div>{% endif %}{% endmacro %}

{% macro item_line(i, csrf, back) %}
{% set live = i.can_change and i.kind not in ('email', 'whatsapp') and i.status not in ('Closed', 'Verified') %}
<li class="row-item">
  {% if live %}<form class="inline" method="post" action="/tasks/{{ i.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}">
    <button class="tick" type="submit" name="action" value="done" title="{{ 'Mark fixed (goes to retest)' if i.kind == 'qa_issue' else 'Mark done' }}" aria-label="{{ 'Mark fixed' if i.kind == 'qa_issue' else 'Mark done' }}: {{ i.title }}">✓</button></form>
  {% else %}<span class="tick ghost" aria-hidden="true">{{ '✉' if i.kind == 'email' else ('💬' if i.kind == 'whatsapp' else '•') }}</span>{% endif %}
  <div class="row-main">
    <div>{% if i.link %}<a class="item-title" href="{{ i.link }}">{{ i.title }}</a>{% else %}<strong>{{ i.title }}</strong>{% endif %}
      <span class="k">{{ i.kind_label }}</span>{% if i.priority in ('urgent', 'high') %}<span class="k {{ i.priority }}">{{ i.priority }}</span>{% endif %}
      {% for sg in i.signals %}<span class="k sig">{{ sg.replace('_', ' ') }}</span>{% endfor %}</div>
    <div class="meta">{% set bits = [] %}
      {% if i.owner %}{% set _ = bits.append(i.owner) %}{% elif i.kind not in ('email', 'whatsapp') %}{% set _ = bits.append('no owner yet') %}{% endif %}
      {% if i.who and i.who != i.owner %}{% set _ = bits.append(i.who) %}{% endif %}
      {% if i.stage and i.kind == 'lead' %}{% set _ = bits.append(labels.lead_stages.get(i.stage, i.stage)) %}{% elif i.status and i.status not in ('Open',) %}{% set _ = bits.append(i.status) %}{% endif %}
      {{ bits|join(' · ') }}{% if i.due %}{{ ' · ' if bits }}<span class="{{ 'over' if i.overdue else 'due' }}">{% if i.kind == 'whatsapp' %}waiting {{ i.due }}{% elif i.overdue %}was due {{ i.due }}{% else %}due {{ i.due }}{% endif %}</span>{% endif %}
      {% if i.repeat %} · <span class="repeat" title="Repeats">↻ {{ i.repeat }}</span>{% endif %}
      {% if i.next_action %} · next: {{ i.next_action }}{% endif %}</div>
  </div>
  {% if live and (i.overdue or i.bucket == 'today') %}<form class="inline" method="post" action="/tasks/{{ i.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}">
    <button class="snooze" type="submit" name="action" value="snooze" title="Move it to tomorrow">→ Tomorrow</button></form>{% endif %}
</li>
{% endmacro %}

{% macro new_item(members, csrf, back, kind='task', title='Add', show_kind=True) %}
<form method="post" action="/tasks" class="form-grid">
  <input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="{{ back }}">
  <label style="grid-column: span 2">What<br><input name="title" maxlength="200" required placeholder="e.g. Send fee structure to Ravi's parents"></label>
  {% if show_kind %}<label>Type<br><select name="kind">{% for k, v in labels.kinds.items() %}<option value="{{ k }}" {{ 'selected' if k == kind else '' }}>{{ v }}</option>{% endfor %}</select></label>
  {% else %}<input type="hidden" name="kind" value="{{ kind }}">{% endif %}
  <label>Owner<br><select name="owner"><option value="">No owner yet</option>{% for m in members %}<option value="{{ m.id }}">{{ m.name }}</option>{% endfor %}</select></label>
  <label>Due<br><input name="due" placeholder="tomorrow 3pm, Friday, 12 Oct"></label>
  <label>Priority<br><select name="priority">{% for p in labels.priorities %}<option {{ 'selected' if p == 'medium' else '' }}>{{ p }}</option>{% endfor %}</select></label>
  <label>Department<br><select name="department"><option value="">—</option>{% for d in labels.departments %}<option>{{ d }}</option>{% endfor %}</select></label>
  <label>Person / contact<br><input name="related_person" maxlength="120"></label>
  <label>Repeats<br><select name="repeat">{% for k, v in labels.repeats %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select></label>
  {% if kind == 'quality' %}<label>Category<br><select name="category">{% for c in labels.quality %}<option>{{ c }}</option>{% endfor %}</select></label>{% endif %}
  {% if kind == 'lead' %}<label>Value (₹)<br><input name="value" inputmode="decimal" maxlength="20"></label>{% endif %}
  <button class="primary" type="submit">{{ title }}</button>
</form>
{% endmacro %}

{% macro briefing(b, compact=False) %}
<section class="card brief" id="brief">
  <h2>{{ b.greeting }}.</h2>
  {% if b.all_clear %}<p>Nothing needs your attention right now. 🎉 Everything is on track.</p>
  {% else %}
  <div class="sub">Here's what needs attention now.</div>
  <div class="headline">{% for h in b.headline %}<a href="/today#{{ h.anchor }}"><strong>{{ h.count }}</strong> {{ h.text }}</a>{% endfor %}</div>
  {% if b.actions %}<h2 style="margin-top:14px;font-size:15px">Do next</h2>
  <ol class="next">{% for a in b.actions[:(5 if compact else 8)] %}<li><a href="{{ a.link }}">{{ a.text }}</a><span class="meta">{{ a.why }}</span></li>{% endfor %}</ol>{% endif %}
  {% endif %}
</section>
{% endmacro %}
"""

SETUP = """{% extends "base" %}{% from "forms" import notify_fields, account_fields %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% block body %}
{{ top('settings', me, csrf, today, 'Set up NeuraNova PA') }}
{{ flash(msg) }}
<div class="steps-bar">{% for k, label in steps %}<a href="/setup?step={{ loop.index }}" class="{{ 'on' if loop.index == step else ('done' if loop.index < step else '') }}">{{ loop.index }}. {{ label }}</a>{% endfor %}</div>
<section class="card">
  <h2>Step {{ step }} of {{ steps|length }} · {{ steps[step - 1][1] }}</h2>
  <form method="post" action="/setup/{{ step }}" class="fields">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    {% set s = settings_view %}
    {% if key == 'company' %}
      <p class="hint">Tell the PA about your business hours. Every step can be skipped and changed later in Settings.</p>
      <label>Company name<input name="company_name" value="{{ s.company_name }}" maxlength="60"></label>
      <label>Timezone <small>(pick from the list or type, e.g. Asia/Kolkata for India)</small><input name="timezone" value="{{ s.timezone }}" placeholder="Asia/Kolkata" list="tzlist" autocomplete="off"><datalist id="tzlist"><option value="Asia/Kolkata"><option value="Asia/Dubai"><option value="Asia/Riyadh"><option value="Asia/Qatar"><option value="Asia/Singapore"><option value="Asia/Kuala_Lumpur"><option value="Asia/Tokyo"><option value="Australia/Sydney"><option value="Europe/London"><option value="Europe/Berlin"><option value="Africa/Nairobi"><option value="America/New_York"><option value="America/Chicago"><option value="America/Los_Angeles"><option value="UTC"></datalist></label>
      <div class="form-grid"><label>Work starts<input name="work_start" type="time" value="{{ s.work_start }}"></label><label>Work ends<input name="work_end" type="time" value="{{ s.work_end }}"></label>
      <label>Reply promise (business hours)<input name="reply_hours" inputmode="decimal" value="{{ s.reply_hours }}"></label></div>
      <div class="days">{% for d in ['mon','tue','wed','thu','fri','sat','sun'] %}<label class="check"><input type="checkbox" name="day_{{ d }}" {{ 'checked' if d in s.work_days else '' }}>{{ d|capitalize }}</label>{% endfor %}</div>
    {% elif key == 'apps' %}
      <p class="hint">Where your NeuraNova applications run. Production is only monitored safely (open pages, check they load, no changes). Development gets deeper workflow tests.</p>
      <label>Production address<input name="NEURANOVA_PROD_URL" value="{{ qa_cfg.production }}" placeholder="https://app.neuranovaedu.com"></label>
      <label>Development address<input name="NEURANOVA_DEV_URL" value="{{ qa_cfg.development }}" placeholder="https://dev.neuranovaedu.com/classroom"></label>
      <label>Login page path <small>(optional)</small><input name="NEURANOVA_LOGIN_PATH" value="{{ qa_cfg.login_path }}" placeholder="/login"></label>
      <label class="check"><input type="checkbox" name="QA_ALLOW_PROD_LOGIN" {{ 'checked' if qa_cfg.allow_prod_login else '' }}> Allow signing in to Production with test accounts (read-only checks)</label>
      <input type="hidden" name="QA_WORKFLOWS" value="{{ qa_cfg.workflows }}">
    {% elif key in ('email', 'whatsapp', 'calendar', 'drive') %}
      {% set c = cards.get(key) %}
      {% if c %}
      <p class="hint">{{ c.summary }}{% if c.status == 'connected' %} <strong class="safe-on">✓ Connected{% if c.account %} as {{ c.account }}{% endif %}</strong>{% endif %}</p>
      {% if c.steps %}<ol class="steps">{% for st in c.steps %}<li>{{ st }}</li>{% endfor %}</ol>{% endif %}
      {% if key == 'email' %}<label>Your email address<input name="address" value="{{ (c.fields|selectattr('key', 'equalto', 'EMAIL_ADDRESS')|first).shown if c.fields else '' }}" placeholder="you@neuranova.in"><small>We fill in the server settings for you.</small></label>{% endif %}
      {% for f in c.fields if not f.env and f.key != 'EMAIL_ADDRESS' %}
        <label>{{ f.label }}{% if not f.required %} <small>(optional)</small>{% endif %}
          <input name="{{ f.key }}" {{ 'type=password autocomplete=new-password' if f.secret else '' }} placeholder="{{ ('saved ' ~ f.shown) if (f.secret and f.has_value) else f.placeholder }}" value="{{ '' if f.secret else f.shown }}">
          {% if f.help %}<small>{{ f.help }}</small>{% endif %}</label>
      {% endfor %}
      {% if c.oauth %}<p class="hint">After saving, finish with <a href="/integrations#{{ key }}">Sign in with Google on the Integrations page</a>.</p>{% endif %}
      {% endif %}
    {% elif key == 'ai' %}
      <p class="hint">The AI reads important messages, drafts replies and writes reports. Claude is recommended; OpenAI also works. Keys are stored encrypted.</p>
      <div class="days"><label class="check"><input type="radio" name="provider" value="claude" {{ 'checked' if ai.current == 'claude' else '' }}> Claude{% if ai.have.claude %} ✓{% endif %}</label>
      <label class="check"><input type="radio" name="provider" value="openai" {{ 'checked' if ai.current == 'openai' else '' }}> OpenAI{% if ai.have.openai %} ✓{% endif %}</label></div>
      <label>Claude API key <small>(console.anthropic.com → API keys)</small><input name="ANTHROPIC_API_KEY" type="password" autocomplete="new-password" placeholder="{{ 'saved' if ai.have.claude else 'sk-ant-...' }}"></label>
      <label>OpenAI API key <small>(platform.openai.com → API keys)</small><input name="OPENAI_API_KEY" type="password" autocomplete="new-password" placeholder="{{ 'saved' if ai.have.openai else 'sk-...' }}"></label>
    {% elif key == 'notifications' %}
      {{ notify_fields(prefs) }}
    {% elif key == 'accounts' %}
      <p class="hint">Test accounts per role, used only by Application QA. Passwords are stored encrypted and never shown again.</p>
      {{ account_fields(qa_cfg, roles, {'development': 'Development', 'production': 'Production'}) }}
    {% elif key == 'review' %}
      <p>{{ progress.connected }} of {{ progress.total }} essentials connected{% if progress.missing %} (still to do: {{ progress.missing|join(', ') }}){% endif %}.</p>
      <p>Safe Mode is <strong class="safe-on">ON</strong>: emails and WhatsApp messages are drafted for your approval and nothing is sent, deleted or changed in Production without you.</p>
      <p class="hint">You can change anything later under Settings.</p>
    {% endif %}
    <div class="actions">
      <button class="primary" type="submit">{{ 'Finish' if key == 'review' else 'Save & continue' }}</button>
      {% if key != 'review' %}<button type="submit" name="action" value="skip">Skip for now</button>{% endif %}
      {% if step > 1 %}<a class="btn" href="/setup?step={{ step - 1 }}">Back</a>{% endif %}
    </div>
  </form>
</section>
{% endblock %}"""

FORM_MACROS = """
{% macro notify_fields(prefs) %}
  <p class="hint">What the PA sends you on WhatsApp (and keeps on the Reports page). It stays quiet outside work hours unless something is urgent.</p>
  {% for k, label in [('notify_digest', 'Attention alerts during the day (grouped, at most hourly)'), ('notify_morning', 'Morning Brief'),
                      ('notify_eod', 'End-of-Day Summary'), ('notify_weekly', 'Weekly Management Summary'),
                      ('notify_monthly', 'Monthly Business Summary'), ('notify_qa', 'Application QA failures'),
                      ('auto_draft_followups', 'Draft polite follow-ups when someone misses a promised date (they wait for approval)')] %}
  <label class="check"><input type="checkbox" name="{{ k }}" {{ 'checked' if prefs[k] else '' }}> {{ label }}</label>
  {% endfor %}
{% endmacro %}
{% macro account_fields(qa_cfg, roles, envs) %}
  {% for env_key, env_label in envs.items() %}
  <h3 style="margin:8px 0 0">{{ env_label }}</h3>
  {% for role in roles %}{% set slug = env_key ~ '__' ~ role.replace(' ', '_') %}{% set a = qa_cfg.accounts.get(env_key, {}).get(role, {}) %}
  <div class="acct"><strong>{{ role }}</strong>
    <input name="{{ slug }}__user" value="{{ a.username or '' }}" placeholder="username or email" aria-label="{{ role }} username" autocomplete="off">
    <input name="{{ slug }}__pass" type="password" placeholder="{{ 'password saved' if a.password else 'password' }}" aria-label="{{ role }} password" autocomplete="new-password">
    {% if a.username %}<label class="check"><input type="checkbox" name="{{ slug }}__clear"> remove</label>{% else %}<span></span>{% endif %}</div>
  {% endfor %}{% endfor %}
{% endmacro %}
"""

TODAY = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash, item_line, briefing, new_item with context %}{% block body %}
{{ top('today', me, csrf, today) }}
{{ flash(msg) }}
{% if b %}{{ briefing(b) }}
{% for key, label in labels.focus.items() if key != 'meetings' and b.focus[key] %}
<section class="card" id="{{ key }}"><h2>{{ label }} ({{ b.focus[key]|length }})</h2>
  <ul class="list">{% for i in b.focus[key][:15] %}{{ item_line(i, csrf, '/today#' ~ key) }}{% endfor %}</ul>
  {% if b.focus[key]|length > 15 %}<a href="/tasks">See all</a>{% endif %}</section>
{% endfor %}
{% endif %}
<section class="card" id="meetings"><h2>Meetings</h2>
  {% for m in meetings.today %}
  <div style="margin-bottom:12px"><strong>{{ m.when }}</strong> {{ m.title }}{% if m.location %} <span class="meta">· {{ m.location }}</span>{% endif %}
    {% if m.attendees %}<div class="meta">With {{ m.attendees[:5]|join(', ') }}</div>{% endif %}
    {% if m.prep %}<div class="meta">Prepare: {% for p in m.prep %}<a href="/tasks/{{ p.id }}">{{ p.title }}</a>{{ ', ' if not loop.last }}{% endfor %}</div>{% endif %}</div>
  {% else %}<p class="empty">No meetings today{% if not meetings.upcoming %} (connect your calendar in Settings → Integrations){% endif %}.</p>{% endfor %}
  {% for m in meetings.needs_capture %}
  <details class="card" style="margin-top:8px"><summary>Capture actions from “{{ m.title }}”</summary>
    <form method="post" action="/meetings/capture" class="fields" style="margin-top:8px">
      <input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="uid" value="{{ m.uid }}"><input type="hidden" name="title" value="{{ m.title }}">
      <label>Promised actions, one per line<textarea name="actions" class="body" placeholder="Send revised timetable to Mrs. Iyer"></textarea></label>
      <div class="form-grid"><label>Owner<select name="owner"><option value="">Me</option>{% for u in members %}<option value="{{ u.id }}">{{ u.name }}</option>{% endfor %}</select></label>
      <label>Due<input name="due" placeholder="Friday"></label><button class="primary" type="submit">Save actions</button></div>
    </form></details>
  {% endfor %}
  {% if meetings.upcoming %}<h2 style="margin-top:12px;font-size:14px">Coming up</h2>
  <ul class="list">{% for m in meetings.upcoming[:8] %}<li>{{ m.day }} {{ m.when }} · {{ m.title }}</li>{% endfor %}</ul>{% endif %}
</section>
<section class="card" id="mine"><h2>Assigned to me ({{ mine|length }})</h2>
  <ul class="list">{% for i in mine %}{{ item_line(i, csrf, '/today#mine') }}{% else %}<li class="empty">Nothing assigned to you.</li>{% endfor %}</ul>
  <details><summary>Add something</summary>{{ new_item(members, csrf, '/today#mine') }}</details>
</section>
{% if is_owner %}<section class="card"><h2>Todoist today &amp; overdue</h2>
  {% if todoist_error %}<p class="empty">{{ todoist_error }}</p>{% endif %}
  <ul class="list">{% for t in todoist %}<li><strong>{{ t.label }}</strong> {{ t.content }} <span class="meta">{{ t.due }} · <a href="{{ t.url }}" target="_blank" rel="noopener">open</a></span></li>{% else %}<li class="empty">Nothing due{% if not todoist_error %}{% endif %}.</li>{% endfor %}</ul></section>{% endif %}
{% endblock %}"""

TASKS = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash, item_line, new_item with context %}{% block body %}
{{ top('tasks', me, csrf, today) }}
{{ flash(msg) }}
<section class="card quickbar" id="new">
  <form method="post" action="/tasks/quick" class="quickbar-form"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="back" value="/tasks">
    <input name="text" required maxlength="200" placeholder="Add something… e.g. Send fee structure to Mr. Kumar by Friday · Publish timetable every Friday" aria-label="New item" autocomplete="off">
    <select name="kind" aria-label="Type">{% for k, v in labels.kinds.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select>
    <button class="primary" type="submit">Add</button></form>
  <details style="margin-top:8px"><summary>Add with owner, priority and more details</summary><div style="margin-top:10px">{{ new_item(members, csrf, '/tasks') }}</div></details>
</section>
<section class="card">
  <form class="filters" method="get" action="/tasks">
    <label>Type<select name="kind"><option value="">All</option>{% for k, v in labels.kinds.items() %}<option value="{{ k }}" {{ 'selected' if f.kind == k else '' }}>{{ v }}</option>{% endfor %}</select></label>
    <label>Status<select name="status">{% for k, v in [('active', 'Active'), ('all', 'All'), ('closed', 'Closed / verified')] + labels.statuses.items()|list %}<option value="{{ k }}" {{ 'selected' if f.status == k else '' }}>{{ v }}</option>{% endfor %}</select></label>
    <label>Owner<select name="owner"><option value="">Anyone</option><option value="me" {{ 'selected' if f.owner == 'me' else '' }}>Me</option><option value="__none__" {{ 'selected' if f.owner == '__none__' else '' }}>No owner</option>{% for m in members %}<option value="{{ m.id }}" {{ 'selected' if f.owner == m.id else '' }}>{{ m.name }}</option>{% endfor %}</select></label>
    <label>Department<select name="department"><option value="">All</option>{% for d in labels.departments %}<option {{ 'selected' if f.department == d else '' }}>{{ d }}</option>{% endfor %}</select></label>
    <label>When<select name="when"><option value="">Any time</option>{% for k, v in [('overdue', 'Overdue'), ('today', 'Today'), ('tomorrow', 'Tomorrow'), ('this_week', 'This week'), ('later', 'Later'), ('none', 'No date')] %}<option value="{{ k }}" {{ 'selected' if f.when == k else '' }}>{{ v }}</option>{% endfor %}</select></label>
    <label>Search<input name="q" value="{{ f.q }}"></label>
    <button type="submit">Filter</button>{% if f.kind or f.owner or f.department or f.when or f.q or f.status != 'active' %} <a href="/tasks">Clear</a>{% endif %}
  </form>
  <p class="meta" style="margin:10px 0 0">{{ items|length }} item{{ 's' if items|length != 1 }} · tick ✓ when done ·
    <a href="/export/tasks.csv?kind={{ f.kind|urlencode }}&status={{ f.status|urlencode }}&owner={{ f.owner|urlencode }}&department={{ f.department|urlencode }}&q={{ f.q|urlencode }}">Download for Excel</a></p>
  {% set groups = [('overdue', 'Overdue'), ('today', 'Today'), ('tomorrow', 'Tomorrow'), ('this_week', 'This week'), ('later', 'Later'), ('none', 'No date')] %}
  {% for key, label in groups %}{% set rows = items|selectattr('bucket', 'equalto', key)|list %}{% if rows %}
  <h3 class="group-h {{ 'over' if key == 'overdue' else '' }}">{{ label }} <span class="meta">({{ rows|length }})</span></h3>
  <ul class="list rows">{% for i in rows %}{{ item_line(i, csrf, '/tasks') }}{% endfor %}</ul>
  {% endif %}{% endfor %}
  {% if not items %}<p class="empty">Nothing here. {% if f.status == 'active' and not f.q %}Add your first item above, or type it in the <strong>+ New</strong> button at the top of any page.{% endif %}</p>{% endif %}
</section>
<section class="card" id="team"><h2>Who owns what</h2>
  <p class="sub">A neutral view of open work, to spot overload and help early — not to blame.</p>
  <div class="scroll"><table><tr><th>Person</th><th>Open</th><th>Overdue</th><th>Due this week</th><th>Waiting</th><th>Blocked</th><th>Done (7 days)</th></tr>
  {% for name, o in by_owner|dictsort %}<tr><td><a href="/tasks?owner={{ o.id }}">{{ name }}</a></td><td>{{ o.open }}</td><td class="{{ 'over' if o.overdue else '' }}">{{ o.overdue }}</td><td>{{ o.week }}</td><td>{{ o.waiting }}</td><td>{{ o.blocked }}</td><td>{{ o.done }}</td></tr>
  {% else %}<tr><td colspan="7" class="empty">No open work.</td></tr>{% endfor %}</table></div>
</section>
{% endblock %}"""

TASK = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% block body %}
{{ top('tasks', me, csrf, today, i.kind_label ~ ' #' ~ i.id) }}
{{ flash(msg) }}
<a class="backlink" href="/tasks">← All tasks</a>
<section class="card">
  <h2>{{ i.title }}</h2>
  <div class="meta"><span class="k">{{ i.kind_label }}</span>{{ i.status }}{% if i.stage %} · {{ (labels.lead_stages if i.kind == 'lead' else labels.qa_stages).get(i.stage, i.stage) }}{% endif %}
    · {{ i.owner or 'no owner' }}{% if i.due %} · <span class="{{ 'over' if i.overdue else '' }}">due {{ i.due }}</span>{% endif %} · created {{ i.created }} · source {{ i.source or 'manual' }}{% if i.repeat %} · <span class="repeat">↻ repeats {{ i.repeat }}</span>{% endif %}</div>
  {% if i.description %}<p style="white-space:pre-wrap">{{ i.description }}</p>{% endif %}
  {% if contact %}<p class="meta">Contact: {{ contact.name }}{% if contact.phone %} · {{ contact.phone }}{% endif %}{% if contact.email %} · {{ contact.email }}{% endif %}{% if contact.role %} · {{ contact.role }}{% endif %}</p>{% endif %}
  {% if i.can_change %}
  <div class="actions">
    {% if i.status not in ('Closed', 'Verified') %}
    <form class="inline" method="post" action="/tasks/{{ i.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="primary" name="action" value="done">{{ 'Mark fixed (send to retest)' if i.kind == 'qa_issue' else '✓ Done' }}</button></form>
    <form class="inline" method="post" action="/tasks/{{ i.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><input name="reason" placeholder="What's blocking it?" maxlength="300" aria-label="Blocked reason"><button name="action" value="block">Blocked</button></form>
    {% else %}
    <form class="inline" method="post" action="/tasks/{{ i.id }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button name="action" value="reopen">Reopen</button></form>
    {% endif %}
  </div>{% endif %}
</section>
{% if evidence %}<section class="card evidence"><h2>Evidence from QA checks</h2>
  <p class="meta">{{ evidence.environment }} · {{ evidence.role }} · {{ evidence.workflow }} · seen {{ evidence.occurrences }} time(s){% if evidence.url %} · <a href="{{ evidence.url }}" target="_blank" rel="noopener">page</a>{% endif %}</p>
  {% if evidence.error %}<p class="over">{{ evidence.error }}</p>{% endif %}
  {% for e in evidence.console_errors or [] %}<div class="meta">Console: {{ e }}</div>{% endfor %}
  {% for e in evidence.failed_requests or [] %}<div class="meta">Request failed: {{ e }}</div>{% endfor %}
  {% if evidence.screenshot_url %}<img src="{{ evidence.screenshot_url }}" alt="Screenshot when the check failed" loading="lazy">{% endif %}
</section>{% endif %}
{% if i.can_change %}
{% if i.kind == 'qa_issue' %}<section class="card"><h2>QA lifecycle</h2>
  <form method="post" action="/tasks/{{ i.id }}" class="form-grid"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="action" value="qa_stage">
    <label>Move to<select name="stage">{% for k, v in labels.qa_stages.items() %}<option value="{{ k }}" {{ 'selected' if k == i.stage else '' }}>{{ v }}</option>{% endfor %}</select></label>
    <label style="grid-column: span 2">Note<input name="note" maxlength="500"></label><button type="submit">Update</button></form>
  <p class="sub">New → Assigned → In progress → Ready for test → Testing → Failed / Fix required → Retest → Verified → Closed. Fixes are verified by a retest before they close.</p></section>{% endif %}
<section class="card"><h2>Edit</h2>
  <form method="post" action="/tasks/{{ i.id }}" class="fields"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="action" value="save">
    <label>Title<input name="title" value="{{ i.title }}" maxlength="200"></label>
    <label>Details<textarea class="body" name="description" maxlength="2000">{{ i.description }}</textarea></label>
    <div class="form-grid">
      <label>Owner<select name="owner"><option value="">No owner</option>{% for m in members %}<option value="{{ m.id }}" {{ 'selected' if m.id == i.owner_id else '' }}>{{ m.name }}</option>{% endfor %}</select></label>
      <label>Status<select name="status">{% for k, v in labels.statuses.items() %}<option value="{{ k }}" {{ 'selected' if v == i.status else '' }}>{{ v }}</option>{% endfor %}</select></label>
      <label>Priority<select name="priority">{% for p in labels.priorities %}<option {{ 'selected' if p == i.priority else '' }}>{{ p }}</option>{% endfor %}</select></label>
      <label>Department<select name="department"><option value="">—</option>{% for d in labels.departments %}<option {{ 'selected' if d == i.department else '' }}>{{ d }}</option>{% endfor %}</select></label>
      <label>Repeats<select name="repeat">{% set cur = i.data.repeat or '' %}{% for k, v in labels.repeats %}<option value="{{ k }}" {{ 'selected' if k == cur else '' }}>{{ v }}</option>{% endfor %}
        {% if cur and cur not in labels.repeats|map('first')|list %}<option value="{{ cur }}" selected>{{ i.repeat|capitalize }}</option>{% endif %}</select></label>
      <div><label>{{ 'Change due date' if i.due else 'Due date' }} <small>{% if i.due %}(now {{ i.due }}){% endif %}</small><input name="due" placeholder="tomorrow 3pm, Friday, 12 Oct"></label>
        {% if i.due %}<label class="check" style="margin-top:4px"><input type="checkbox" name="clear_due"> no due date</label>{% endif %}</div>
    </div>
    <div class="form-grid">
      <label>Person / contact<input name="related_person" value="{{ i.who }}" maxlength="120"></label>
      <label>Waiting on<input name="waiting_on" value="{{ i.waiting_on }}" maxlength="120"></label>
      <label>Project<input name="related_project" value="{{ i.related_project }}" maxlength="120"></label>
      <label>Next action<input name="next_action" value="{{ i.next_action }}" maxlength="200"></label>
    </div>
    {% if i.kind == 'lead' %}<div class="form-grid">
      <label>Stage<select name="stage">{% for k, v in labels.lead_stages.items() %}<option value="{{ k }}" {{ 'selected' if k == i.stage else '' }}>{{ v }}</option>{% endfor %}</select></label>
      <label>Value (₹)<input name="value" value="{{ '' if i.value is none else '%g' % i.value }}" inputmode="decimal"></label>
      <label>Lost reason<input name="lost_reason" value="{{ i.data.lost_reason or '' }}" maxlength="120"></label></div>{% endif %}
    {% if i.kind == 'quality' %}<label>Category<select name="category">{% for c in labels.quality %}<option {{ 'selected' if c == i.data.category else '' }}>{{ c }}</option>{% endfor %}</select></label>{% endif %}
    <label>Add a note to the history<input name="note" maxlength="1000"></label>
    <div class="actions"><button class="primary" type="submit">Save</button></div>
  </form>
</section>
{% if is_owner %}<section class="card"><h2>Message about this</h2>
  <form method="post" action="/tasks/{{ i.id }}" class="form-grid"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="action" value="followup">
    <label>Channel<select name="channel"><option value="whatsapp">WhatsApp</option><option value="email">Email</option></select></label>
    <label>To<input name="recipient" placeholder="{{ 'from contact' if contact else 'number or email' }}"></label>
    <label style="grid-column: span 2">What should it say?<input name="purpose" placeholder="Polite reminder about {{ i.title }}"></label>
    <button type="submit">Draft for approval</button></form>
  <p class="sub">The PA writes the message; it waits in Communications for your approval before it is sent.</p></section>{% endif %}
{% endif %}
<section class="card"><h2>History</h2>
  <div class="scroll"><table>{% for e in events|reverse %}<tr><td class="meta" style="white-space:nowrap">{{ e.at }}</td><td>{{ e.actor }}</td><td>{{ e.event.replace('_', ' ') }}</td><td class="meta">{{ e.detail }}</td></tr>{% endfor %}</table></div>
</section>
{% endblock %}"""

BUSINESS = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash, item_line, new_item with context %}{% block body %}
{{ top('business', me, csrf, today) }}
{{ flash(msg) }}
<div class="tabs row">{% for d in [7, 30, 90] %}<a href="/business?days={{ d }}" class="{{ 'on' if d == days else '' }}">{{ d }} days</a> {% endfor %}</div>
<section class="card"><div class="stat">
  <div><div class="hero">{{ p.new_leads }}</div><div class="sub">new leads</div></div>
  <div><div class="hero">{{ p.hot|length }}</div><div class="sub">hot leads</div></div>
  <div><div class="hero">{{ p.stalled|length }}</div><div class="sub">stalled</div></div>
  <div><div class="hero">{{ p.converted|length }}</div><div class="sub">converted</div></div>
  <div><div class="hero">{{ '–' if p.conversion_pct is none else p.conversion_pct ~ '%' }}</div><div class="sub">conversion</div></div>
  <div><div class="hero">₹{{ '{:,.0f}'.format(p.won_value or 0) }}</div><div class="sub">won value</div></div>
</div>
{% if p.conversion_pct is none %}<p class="sub">Conversion appears once leads are marked converted or lost — the PA doesn't guess.</p>{% endif %}
{% if p.lost_reasons %}<p class="meta">Lost because: {% for r, n in p.lost_reasons.items() %}{{ r }} ({{ n }}){{ ', ' if not loop.last }}{% endfor %}</p>{% endif %}</section>
<div class="grid2 row">
  <section class="card"><h2>Hot leads ({{ hot|length }})</h2><ul class="list">{% for i in hot %}{{ item_line(i, csrf, '/business') }}{% else %}<li class="empty">None right now.</li>{% endfor %}</ul></section>
  <section class="card"><h2>Follow-ups due ({{ follow|length }})</h2><ul class="list">{% for i in follow %}{{ item_line(i, csrf, '/business') }}{% else %}<li class="empty">None due.</li>{% endfor %}</ul></section>
  <section class="card"><h2>Stalled ({{ stalled|length }})</h2><ul class="list">{% for i in stalled %}{{ item_line(i, csrf, '/business') }}{% else %}<li class="empty">Nothing stalled.</li>{% endfor %}</ul></section>
  <section class="card"><h2>Payment pending ({{ pay|length }})</h2><ul class="list">{% for i in pay %}{{ item_line(i, csrf, '/business') }}{% else %}<li class="empty">No payments pending.</li>{% endfor %}</ul></section>
</div>
<h2>Pipeline</h2>
<div class="cols row">{% for key, label, rows in stages %}<div class="col"><h3>{{ label }} · {{ rows|length }}</h3>
  <ul class="list">{% for i in rows[:12] %}<li><a class="item-title" href="{{ i.link }}">{{ i.title }}</a><div class="meta">{{ i.who or i.owner }}{% if i.due %} · {{ i.due }}{% endif %}{% if i.value %} · ₹{{ '{:,.0f}'.format(i.value) }}{% endif %}</div></li>{% else %}<li class="empty">—</li>{% endfor %}</ul></div>{% endfor %}</div>
<p class="meta"><a href="/export/leads.csv">Download all leads for Excel</a></p>
<section class="card" id="newlead"><h2>Add a lead</h2>{{ new_item(members, csrf, '/business', 'lead', 'Add lead', False) }}</section>
<section class="card" id="events"><h2>Log progress</h2>
  <form class="event-form" method="post" action="/events"><input type="hidden" name="csrf" value="{{ csrf }}">
    <label>What<br><select name="kind">{% for k, v in kinds.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select></label>
    <label>Client<br><input name="client" maxlength="120"></label><label>Value<br><input name="value" inputmode="decimal" maxlength="20"></label>
    <label>Note<br><input name="note" maxlength="300"></label><button class="primary" type="submit">Add</button></form>
  <div class="scroll"><table style="margin-top:12px">{% for e in events %}<tr><td>{{ e.on_date }}</td><td>{{ kinds.get(e.kind, e.kind) }}</td><td>{{ e.client }}</td><td>{{ '' if e.value is none else '{:,.0f}'.format(e.value) }}</td><td>{{ e.note }}</td></tr>{% endfor %}</table></div>
</section>
{% endblock %}"""

COMMUNICATIONS = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% block body %}
{{ top('communications', me, csrf, today) }}
{{ flash(msg) }}
<section class="card" id="approvals"><h2>Waiting for your approval ({{ outbox|length + drafts|length }})</h2>
  <p class="sub">{% if safe_mode %}<span class="safe-on">Safe Mode is on</span>: nothing is sent until you approve it.{% else %}<span class="safe-off">Safe Mode is off</span>: trusted kinds are sent automatically; everything else still waits here.{% endif %}</p>
  {% for o in outbox %}
  <div class="draft" style="margin-bottom:18px">
    <div><strong>{{ 'WhatsApp' if o.channel == 'whatsapp' else 'Email' }} → {{ o.recipient_name or o.recipient }}</strong> <span class="meta">{{ o.recipient }}{% if o.subject %} · {{ o.subject }}{% endif %}{% if o.reason %} · {{ o.reason }}{% endif %}</span></div>
    <form method="post" action="/outbox/{{ o.id }}/send"><input type="hidden" name="csrf" value="{{ csrf }}">
      <textarea class="body" name="body" aria-label="Message text">{{ o.body }}</textarea>
      <div class="actions"><button class="primary" type="submit">Approve &amp; send</button><button type="submit" formaction="/outbox/{{ o.id }}/reject">Don't send</button></div></form>
  </div>{% endfor %}
  {% for d in drafts %}
  <div class="draft" style="margin-bottom:18px">
    <div><strong>Email reply → {{ d.to }}</strong> <span class="meta">· {{ d.subject }}</span></div><div class="meta">{{ d.summary }}</div>
    {% for q in d.needs %}{% if loop.first %}<div class="needs"><strong>Needs you:</strong><ul style="margin:4px 0 0 18px;padding:0">{% endif %}<li>{{ q }}</li>{% if loop.last %}</ul></div>{% endif %}{% endfor %}
    <form method="post" action="/drafts/{{ d.id }}/edit"><input type="hidden" name="csrf" value="{{ csrf }}">
      <textarea class="body" name="body" aria-label="Reply text">{{ d.body }}</textarea>
      <div class="actions"><button type="submit">Save changes</button><button class="primary" type="submit" formaction="/drafts/{{ d.id }}/send">Save &amp; send</button><button type="submit" formaction="/drafts/{{ d.id }}/skip">Skip</button></div></form>
  </div>{% endfor %}
  {% if not outbox and not drafts %}<p class="empty">Nothing waiting. 🎉</p>{% endif %}
</section>
<section class="card" id="compose"><h2>Ask the PA to write a message</h2>
  <form method="post" action="/outbox/compose" class="form-grid"><input type="hidden" name="csrf" value="{{ csrf }}">
    <label>Channel<select name="channel"><option value="whatsapp">WhatsApp</option><option value="email">Email</option></select></label>
    <label>To<input name="recipient" required placeholder="name, number or email" list="contact-list"></label>
    <label>Subject (email)<input name="subject" maxlength="120"></label>
    <label style="grid-column: 1 / -1">What should it say?<input name="purpose" required maxlength="500" placeholder="Remind Ravi's parents that the term fee is due on Friday, politely"></label>
    <button class="primary" type="submit">Draft it</button></form>
  <datalist id="contact-list">{% for c in contacts %}<option value="{{ c.name or c.phone or c.email }}">{% endfor %}</datalist>
</section>
<div class="grid2 row">
<section class="card" id="email"><h2>Emails waiting for your reply ({{ waiting_email|length }})</h2>
  <ul class="list">{% for e in waiting_email %}<li><strong>{{ e.from }}</strong> · {{ e.subject }}<div class="meta">{{ e.summary }}</div>
    <div class="meta {{ 'over' if e.overdue else '' }}">{{ 'Overdue since' if e.overdue else 'Reply by' }} {{ e.deadline }}{% if e.link %} · <a href="{{ e.link }}" target="_blank" rel="noopener">open</a>{% endif %}</div></li>
  {% else %}<li class="empty">Nothing waiting.</li>{% endfor %}</ul></section>
<section class="card" id="whatsapp"><h2>WhatsApp (14 days){% if contact_filter %} · <a href="/communications#whatsapp">show all</a>{% endif %}</h2>
  <ul class="list">{% for m in wa %}<li><strong>{{ '→ ' if m.direction == 'out' else '' }}{{ m.who }}</strong> <span class="meta">{{ m.at }}{% if m.importance == 'high' %} · important{% endif %}{% if m.direction != 'out' and not m.replied %} · not answered{% endif %}</span>
    <div>{{ m.summary or m.body[:200] }}</div></li>{% else %}<li class="empty">No WhatsApp messages yet.</li>{% endfor %}</ul></section>
</div>
<section class="card"><h2>Recent emails (7 days)</h2>
  <div class="scroll"><table><tr><th>When</th><th>From</th><th>Subject</th><th>Type</th><th></th></tr>
  {% for e in emails %}<tr><td class="meta" style="white-space:nowrap">{{ e.at }}</td><td>{{ e.from }}</td><td>{{ e.subject }}<div class="meta">{{ e.summary }}</div></td><td>{{ e.category or '' }}{% if e.priority == 'high' %} · high{% endif %}</td><td>{{ '✓ replied' if e.replied else '' }}</td></tr>
  {% else %}<tr><td colspan="5" class="empty">No emails yet. Connect your mailbox under Settings → Integrations.</td></tr>{% endfor %}</table></div></section>
<section class="card" id="contacts"><h2>Contacts ({{ contacts|length }}) <a class="meta" style="font-weight:400" href="/export/contacts.csv">Download</a></h2>
  <p class="sub">People the PA has met through WhatsApp and email. Setting the role (parent, teacher…) helps it judge what matters.</p>
  {% for c in contacts[:100] %}<details><summary><strong>{{ c.name or c.phone or c.email }}</strong> <span class="meta">{{ c.role }}{% if c.organization %} · {{ c.organization }}{% endif %}</span></summary>
    <form method="post" action="/contacts/{{ c.id }}" class="form-grid" style="margin:8px 0 12px"><input type="hidden" name="csrf" value="{{ csrf }}">
      <label>Name<input name="name" value="{{ c.name }}"></label><label>Phone<input name="phone" value="{{ c.phone }}"></label><label>Email<input name="email" value="{{ c.email }}"></label>
      <label>Organisation<input name="organization" value="{{ c.organization }}"></label>
      <label>Role<select name="role">{% for r in roles %}<option {{ 'selected' if r == c.role else '' }}>{{ r }}</option>{% endfor %}</select></label>
      <label>Notes<input name="notes" value="{{ c.notes }}"></label><button type="submit">Save</button>
      <a href="/communications?contact={{ c.id }}#whatsapp">Messages</a></form></details>
  {% else %}<p class="empty">No contacts yet.</p>{% endfor %}
</section>
{% if sent %}<section class="card"><h2>Recently sent</h2><ul class="list">{% for o in sent %}<li>{{ 'WhatsApp' if o.channel == 'whatsapp' else 'Email' }} → {{ o.recipient_name or o.recipient }}<div class="meta">{{ o.body[:160] }}</div></li>{% endfor %}</ul></section>{% endif %}
{% endblock %}"""

QA = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash, item_line with context %}{% block body %}
{{ top('qa', me, csrf, today) }}
{{ flash(msg) }}
<div class="grid2 row">
{% for env_key, env_label in envs.items() %}{% set url = cfg[env_key] %}
<section class="card"><h2>{{ env_label }}</h2>
  {% if url %}<p class="meta"><a href="{{ url }}" target="_blank" rel="noopener">{{ url }}</a></p>
  <p class="sub">{% if env_key == 'production' %}Safe monitoring only: pages load, sign-in works, no errors. Nothing is clicked that changes data.{% else %}Full workflow tests for each role, including clicks and forms.{% endif %}
    {{ cfg.accounts[env_key]|length }} test account(s).</p>
  {% if running.get(env_key) %}<p><strong>Checks are running…</strong> refresh in a minute.</p>
  {% else %}<form method="post" action="/qa/run/{{ env_key }}"><input type="hidden" name="csrf" value="{{ csrf }}"><button class="primary" type="submit">Run checks now</button></form>{% endif %}
  {% else %}<p class="empty">Not set up. {% if me.role == 'admin' %}<a href="/settings?section=apps">Add the address</a>.{% endif %}</p>{% endif %}
</section>{% endfor %}
</div>
<h2>Open issues ({{ open_count }})</h2>
<div class="cols row">{% for key, label, rows in by_stage if rows or key in ('new', 'fix_required', 'ready_for_test') %}<div class="col"><h3>{{ label }} · {{ rows|length }}</h3>
  <ul class="list">{% for i in rows %}<li><a class="item-title" href="{{ i.link }}">{{ i.title }}</a><div class="meta">{{ i.owner or 'no owner' }}{% if i.data.environment %} · {{ i.data.environment }}{% endif %}{% if i.data.occurrences and i.data.occurrences > 1 %} · seen {{ i.data.occurrences }}×{% endif %}</div></li>{% else %}<li class="empty">—</li>{% endfor %}</ul></div>{% endfor %}</div>
<section class="card"><h2>Recent check runs</h2>
  {% for r in runs %}<details {{ 'open' if loop.first else '' }}><summary><strong>{{ envs.get(r.environment, r.environment) }}</strong> · {{ r.started }} · <span class="{{ 'over' if r.status in ('failed', 'error') else 'safe-on' }}">{{ r.status }}</span> {% if r.summary %}<span class="meta">· {{ r.summary }}</span>{% endif %}</summary>
    <div class="scroll"><table><tr><th>Role</th><th>Check</th><th>Result</th><th>Time</th></tr>
    {% for x in r.results %}<tr><td>{{ x.role }}</td><td>{{ x.workflow }}</td><td>{% if x.ok %}✓ passed{% else %}<span class="over">✕ {{ x.error[:160] }}</span>{% endif %}</td><td>{{ (x.duration_ms / 1000)|round(1) }} s</td></tr>{% endfor %}</table></div></details>
  {% else %}<p class="empty">No checks have run yet.</p>{% endfor %}
</section>
{% endblock %}"""

QUALITY = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash, item_line, new_item with context %}{% block body %}
{{ top('quality', me, csrf, today) }}
{{ flash(msg) }}
<div class="tabs row">{% for d in [14, 30, 90] %}<a href="/quality?days={{ d }}" class="{{ 'on' if d == days else '' }}">{{ d }} days</a> {% endfor %}</div>
<section class="card"><div class="stat">
  <div><div class="hero">{{ q.raised }}</div><div class="sub">concerns raised</div></div>
  <div><div class="hero">{{ q.resolved }}</div><div class="sub">resolved</div></div>
  <div><div class="hero">{{ q.open|length }}</div><div class="sub">open now</div></div>
  <div><div class="hero">{{ '–' if q.avg_days_to_resolve is none else q.avg_days_to_resolve }}</div><div class="sub">days to resolve (avg)</div></div></div>
  {% if q.by_category %}<p class="meta">By area: {% for k, v in q.by_category.items() %}{{ k }} {{ v }}{{ ', ' if not loop.last }}{% endfor %}</p>{% endif %}</section>
{% if q.patterns %}<section class="card brief"><h2>Recurring patterns</h2><ul class="list">{% for p in q.patterns %}<li>{{ p.text }}</li>{% endfor %}</ul>
  <p class="sub">The same kind of issue keeps coming back. Worth fixing the cause, not just each case.</p></section>{% endif %}
{% for cat, rows in by_cat|dictsort %}<section class="card"><h2>{{ cat }} ({{ rows|length }})</h2><ul class="list">{% for i in rows %}{{ item_line(i, csrf, '/quality') }}{% endfor %}</ul></section>
{% else %}<section class="card"><p class="empty">No open quality concerns.</p></section>{% endfor %}
<section class="card"><h2>Record a concern</h2>{{ new_item(members, csrf, '/quality', 'quality', 'Add concern', False) }}</section>
{% endblock %}"""

REPORTS = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% from "chart" import chart %}{% block body %}
{{ top('reports', me, csrf, today) }}
{{ flash(msg) }}
<section class="card"><h2>Create a report now</h2>
  <form method="post" action="/reports/generate" class="filters"><input type="hidden" name="csrf" value="{{ csrf }}">
    <label>Report<select name="kind">{% for k, v in kinds.items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}</select></label>
    <button class="primary" type="submit">Create</button></form>
  <p class="sub">Reports are also made on schedule (Settings → Scheduler) and sent to you on WhatsApp if you chose that.</p></section>
<div class="grid2 row">
  <section class="card"><h2>Replies on time, by week</h2>{{ chart(charts.ontime, "Replies on time by week, percent", "Replies on time", "– = no replies were due that week") }}</section>
  <section class="card"><h2>New leads, by week</h2>{{ chart(charts.leads, "New leads by week", "New leads") }}</section>
</div>
<section class="card"><h2>Saved reports</h2>
  <div class="tabs" style="margin-bottom:8px"><a href="/reports" class="{{ 'on' if not kind else '' }}">All</a> {% for k, v in kinds.items() %}<a href="/reports?kind={{ k }}" class="{{ 'on' if kind == k else '' }}">{{ v }}</a> {% endfor %}</div>
  <ul class="list">{% for r in rows %}<li><a href="/reports/{{ r.id }}">{{ r.title }}</a> <span class="meta">· {{ r.created }}</span></li>{% else %}<li class="empty">No reports yet.</li>{% endfor %}</ul></section>
{% endblock %}"""

REPORT = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% block body %}
{{ top('reports', me, csrf, today, r.title) }}
{{ flash(msg) }}
<section class="card"><div class="meta">Created {{ created }} · <a href="/reports">All reports</a></div>
<div class="report-text" style="margin-top:12px">{{ r.text }}</div></section>
{% endblock %}"""

ASSISTANT = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% block body %}
{{ top('assistant', me, csrf, today) }}
{{ flash(msg) }}
<section class="card">
  {% if not (ai.have.claude or ai.have.openai) %}<p class="needs">No AI is connected yet, so only simple commands work. {% if is_owner %}<a href="/settings?section=ai">Connect Claude or OpenAI</a>.{% endif %}</p>{% endif %}
  <div class="chat" id="chat" aria-live="polite">
    {% for h in history %}<div class="bubble {{ h.who }}">{{ h.text }}</div>{% else %}
    <div class="bubble pa">Hi {{ me.name.split()[0] }}, I'm your NeuraNova PA. Ask me what needs attention, who owes us a reply, how admissions are going, or tell me something to track.</div>{% endfor %}
  </div>
  <form class="chat-form" id="ask" method="post" action="/assistant/ask"><input type="hidden" name="csrf" value="{{ csrf }}">
    <textarea name="text" id="q" rows="2" required placeholder="What needs my attention today?" aria-label="Message"></textarea>
    <button class="primary" type="submit">Send</button></form>
  <div class="suggest">{% for s in ['What needs my attention now?', 'Who has not replied to us?', 'Which leads are hot this week?', 'What is overdue for the team?', 'Any application issues waiting for retest?', 'Remind Priya to send the timetable by Friday'] %}<button type="button" data-q="{{ s }}">{{ s }}</button>{% endfor %}</div>
</section>
<script>
(function () {
  var form = document.getElementById('ask'), q = document.getElementById('q'), chat = document.getElementById('chat');
  function bubble(cls, text) { var d = document.createElement('div'); d.className = 'bubble ' + cls; d.textContent = text; chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d; }
  chat.scrollTop = chat.scrollHeight;
  document.querySelectorAll('.suggest button').forEach(function (b) { b.addEventListener('click', function () { q.value = b.dataset.q; q.focus(); }); });
  q.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener('submit', function (e) {
    e.preventDefault(); var text = q.value.trim(); if (!text) return;
    var body = new URLSearchParams(new FormData(form));
    bubble('you', text); q.value = ''; var wait = bubble('pa', 'Thinking…');
    fetch('/assistant/ask', { method: 'POST', body: body })
      .then(function (r) { return r.json(); })
      .then(function (d) { wait.textContent = d.reply || d.error || 'No answer.'; })
      .catch(function () { wait.textContent = 'Could not reach the console. Is it still running?'; });
  });
})();
</script>
{% endblock %}"""

SEARCH = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash, item_line with context %}{% block body %}
{{ top('search', me, csrf, today, 'Search' ~ (': ' ~ q if q else '')) }}
<section class="card"><form method="get" action="/search" class="filters"><input name="q" value="{{ q }}" autofocus aria-label="Search"><button type="submit">Search</button></form></section>
{% if q %}
<section class="card"><h2>Items ({{ items|length }})</h2><ul class="list">{% for i in items %}{{ item_line(i, csrf, '/search?q=' ~ q|urlencode) }}{% else %}<li class="empty">No matching items.</li>{% endfor %}</ul></section>
{% if is_owner %}<section class="card"><h2>Contacts ({{ contacts|length }})</h2><ul class="list">{% for c in contacts %}<li><strong>{{ c.name or c.phone }}</strong> <span class="meta">{{ c.role }} · {{ c.phone }} {{ c.email }}</span> · <a href="/communications?contact={{ c.id }}#whatsapp">messages</a></li>{% else %}<li class="empty">No contacts.</li>{% endfor %}</ul></section>
<section class="card"><h2>Emails ({{ emails|length }})</h2><ul class="list">{% for e in emails %}<li><strong>{{ e.from }}</strong> · {{ e.subject }}<div class="meta">{{ e.summary }}</div></li>{% else %}<li class="empty">No emails.</li>{% endfor %}</ul></section>{% endif %}
{% endif %}
{% endblock %}"""

SETTINGS = """{% extends "base" %}{% from "nav" import top with context %}{% from "pa" import flash with context %}{% from "forms" import notify_fields, account_fields %}{% block body %}
{{ top('settings', me, csrf, today) }}
{{ flash(msg) }}
<div class="settings-wrap">
<nav class="settings-nav card" aria-label="Settings sections">{% for k, label in sections %}{% if is_owner or k == 'audit' %}<a href="{{ '/integrations' if k == 'integrations' else ('/team#people' if k == 'people' else '/settings?section=' ~ k) }}" class="{{ 'on' if section == k else '' }}">{{ label }}</a>{% endif %}{% endfor %}
  {% if is_owner %}<a href="/setup?step=1">Run setup again</a>{% endif %}</nav>
<section class="card">
{% set s = settings_view %}
{% if section == 'audit' %}
  <h2>Audit log</h2><p class="sub">Everything the PA and people did: sign-ins, settings changes, messages sent, approvals. Secrets are never recorded.</p>
  <div class="scroll"><table>{% for a in audit %}<tr><td class="meta" style="white-space:nowrap">{{ a.at }}</td><td>{{ a.action }}</td><td class="meta">{{ a.detail }}</td></tr>{% else %}<tr><td class="empty">Nothing yet.</td></tr>{% endfor %}</table></div>
{% else %}
<form method="post" action="/settings/{{ section }}" class="fields"><input type="hidden" name="csrf" value="{{ csrf }}">
{% if section == 'general' %}
  <h2>General</h2>
  <label>Company name<input name="company_name" value="{{ s.company_name }}" maxlength="60"></label>
  <label>Timezone <small>(pick from the list or type, e.g. Asia/Kolkata for India)</small><input name="timezone" value="{{ s.timezone }}" placeholder="Asia/Kolkata" list="tzlist" autocomplete="off"><datalist id="tzlist"><option value="Asia/Kolkata"><option value="Asia/Dubai"><option value="Asia/Riyadh"><option value="Asia/Qatar"><option value="Asia/Singapore"><option value="Asia/Kuala_Lumpur"><option value="Asia/Tokyo"><option value="Australia/Sydney"><option value="Europe/London"><option value="Europe/Berlin"><option value="Africa/Nairobi"><option value="America/New_York"><option value="America/Chicago"><option value="America/Los_Angeles"><option value="UTC"></datalist></label>
  <div class="form-grid"><label>Work starts<input name="work_start" type="time" value="{{ s.work_start }}"></label><label>Work ends<input name="work_end" type="time" value="{{ s.work_end }}"></label>
  <label>Reply promise (business hours)<input name="reply_hours" inputmode="decimal" value="{{ s.reply_hours }}"></label></div>
  <div class="days">{% for d in ['mon','tue','wed','thu','fri','sat','sun'] %}<label class="check"><input type="checkbox" name="day_{{ d }}" {{ 'checked' if d in s.work_days else '' }}>{{ d|capitalize }}</label>{% endfor %}</div>
{% elif section == 'apps' %}
  <h2>NeuraNova applications</h2>
  <label>Production address<input name="NEURANOVA_PROD_URL" value="{{ qa_cfg.production }}" placeholder="https://app.neuranovaedu.com"><small>Monitored safely: pages load, sign-in works, no errors. Nothing that changes data is clicked.</small></label>
  <label>Development address<input name="NEURANOVA_DEV_URL" value="{{ qa_cfg.development }}"><small>Deeper workflow tests run here.</small></label>
  <label>Login page path <small>(optional)</small><input name="NEURANOVA_LOGIN_PATH" value="{{ qa_cfg.login_path }}" placeholder="/login"></label>
  <label class="check"><input type="checkbox" name="QA_ALLOW_PROD_LOGIN" {{ 'checked' if qa_cfg.allow_prod_login else '' }}> Allow signing in to Production with test accounts (read-only checks)</label>
  <label>Workflows to test <small>(optional)</small><textarea name="QA_WORKFLOWS" placeholder="[Teacher] Open my classes (development)
goto /classes
expect My Classes
[Student] Join class (development)
goto /dashboard
click Join
expect-url /live">{{ qa_cfg.workflows }}</textarea>
  <small class="hint">Steps: goto, expect, expect-url, wait (safe everywhere); click, fill, select, press (Development only).</small></label>
{% elif section == 'accounts' %}
  <h2>Test accounts</h2><p class="hint">One account per role. Passwords are encrypted and never shown again; leave blank to keep the saved one.</p>
  {{ account_fields(qa_cfg, roles, envs) }}
{% elif section == 'ai' %}
  <h2>AI</h2>
  <p class="hint">Used only where it helps: reading important messages, drafting replies, writing reports and answering in AI Assistant. Briefings and alerts work without it.</p>
  <div class="days"><label class="check"><input type="radio" name="provider" value="claude" {{ 'checked' if ai.current == 'claude' else '' }} {{ 'disabled' if ai.locked else '' }}> Claude (recommended){% if ai.have.claude %} ✓ key saved{% endif %}</label>
  <label class="check"><input type="radio" name="provider" value="openai" {{ 'checked' if ai.current == 'openai' else '' }} {{ 'disabled' if ai.locked else '' }}> OpenAI{% if ai.have.openai %} ✓ key saved{% endif %}</label></div>
  <label>Claude API key<input name="ANTHROPIC_API_KEY" type="password" autocomplete="new-password" placeholder="{{ 'saved — leave blank to keep' if ai.have.claude else 'sk-ant-...' }}"></label>
  <label>OpenAI API key<input name="OPENAI_API_KEY" type="password" autocomplete="new-password" placeholder="{{ 'saved — leave blank to keep' if ai.have.openai else 'sk-...' }}"></label>
  <label>OpenAI model <small>(optional)</small><input name="OPENAI_MODEL" placeholder="gpt-4.1"></label>
{% elif section == 'notifications' %}
  <h2>Notifications</h2>{{ notify_fields(prefs) }}
{% elif section == 'scheduler' %}
  <h2>Scheduler</h2>
  <div class="form-grid"><label>Morning Brief at<input name="morning_brief" type="time" value="{{ s.morning_brief }}"></label>
  <label>Weekly summary on<select name="weekly_day">{% for d in ['mon','tue','wed','thu','fri','sat','sun'] %}<option value="{{ d }}" {{ 'selected' if d == s.weekly_day else '' }}>{{ d|capitalize }}</option>{% endfor %}</select></label>
  <label>at<input name="weekly_time" type="time" value="{{ s.weekly_time }}"></label></div>
  <p class="hint">End-of-Day Summary goes out when work ends ({{ s.work_end }}). Inbox checks every few minutes; Production checks hourly in work hours; Development checks daily at {{ qa_cfg.dev_schedule }}. Monthly summary on the 1st.</p>
{% elif section == 'security' %}
  <h2>Security</h2>
  <p>Safe Mode is {% if prefs.safe_mode %}<strong class="safe-on">ON</strong>{% else %}<strong class="safe-off">OFF</strong>{% endif %}.</p>
  <p class="hint">With Safe Mode on, these always wait for your approval: sending email, sending WhatsApp, deleting data, anything that changes Production, changing users or fees. The PA drafts; you decide.</p>
  <label class="check"><input type="checkbox" name="safe_mode" {{ 'checked' if prefs.safe_mode else '' }}> Safe Mode (recommended)</label>
  <fieldset style="border:1px solid var(--border);border-radius:8px;padding:10px"><legend class="hint">Trusted automation — only when Safe Mode is off</legend>
    <label class="check"><input type="checkbox" name="trust_followups" {{ 'checked' if prefs.trust_followups else '' }}> Send polite follow-ups for missed promises automatically</label>
    <label class="check"><input type="checkbox" name="trust_whatsapp_replies" {{ 'checked' if prefs.trust_whatsapp_replies else '' }}> Send routine WhatsApp replies automatically</label></fieldset>
  <label>To turn Safe Mode off, type TURN OFF<input name="confirm" autocomplete="off"></label>
  <p class="hint">Also protecting you: passwords hashed (scrypt), integration keys encrypted at rest, secrets never written to logs, sign-in rate-limited, every form CSRF-protected, Production QA is read-only.</p>
{% elif section == 'backup' %}
  <h2>Backups</h2>
  <p class="hint">Every day the PA saves a copy of all your data (tasks, leads, history, settings and the key that unlocks your connected accounts). The newest 14 are kept in <code>{{ backup_folder }}</code>. Download one now and then and keep it somewhere safe, e.g. Google Drive.</p>
  <div class="scroll"><table><tr><th>Backup</th><th>Made</th><th>Size</th><th></th></tr>
  {% for b in backups %}<tr><td>{{ b.name }}</td><td>{{ b.when }}</td><td>{{ b.size }}</td><td><a href="/backups/{{ b.name }}">Download</a></td></tr>
  {% else %}<tr><td colspan="4" class="empty">No backups yet. The first one is made a few minutes after start, or press the button.</td></tr>{% endfor %}</table></div>
  <details><summary>How to restore a backup</summary><ol class="steps"><li>Close NeuraNova PA.</li><li>Open the PA's folder (Start menu → "Open NeuraNova PA data folder").</li><li>Unzip the backup there and replace the files when asked.</li><li>Start NeuraNova PA again.</li></ol></details>
{% elif section == 'phone' %}
  <h2>Phone access</h2>
  <p class="hint">Open the PA on your phone while you're on the same Wi-Fi as this computer. You sign in with the same email and password.</p>
  <label class="check"><input type="checkbox" name="lan_access" {{ 'checked' if prefs.lan_access else '' }}> Allow phones and other computers on my Wi-Fi to open NeuraNova PA</label>
  {% if lan_url %}<p>On your phone, open: <strong style="font-size:18px">{{ lan_url }}</strong></p>{% else %}<p class="hint">This computer isn't on a network right now.</p>{% endif %}
  <p class="hint">Takes effect after NeuraNova PA restarts. Use it only on your own office or home Wi-Fi (not public Wi-Fi). If Windows asks whether to allow network access, choose <em>Private networks</em>. To use it away from the office, host the PA on a server (see README).</p>
{% endif %}
  <div class="actions"><button class="primary" type="submit">{{ 'Back up now' if section == 'backup' else 'Save' }}</button></div>
</form>
{% endif %}
</section></div>
{% endblock %}"""


ERROR = """{% extends "base" %}{% from "nav" import brand_logo, brand_wordmark with context %}{% block body %}
<div class="card login">
  <div class="brand" style="margin-bottom:12px">{{ brand_logo() }}<div><div class="brand-name">{{ brand_wordmark() }}</div></div></div>
  <p style="text-align:center">{{ message }}</p>
  <div class="actions" style="justify-content:center"><a class="btn" href="/">Go to the dashboard</a><a class="btn" href="/login">Sign in</a></div>
</div>
{% endblock %}"""


def register(env) -> None:
    m = env.loader.mapping
    m["base"] = m["base"].replace("</style>", PA_CSS + "</style>", 1) if PA_CSS not in m["base"] else m["base"]
    m.update({"pa": PA_MACROS, "forms": FORM_MACROS, "setup": SETUP,
              "today": TODAY, "tasks": TASKS, "task": TASK, "business": BUSINESS, "communications": COMMUNICATIONS,
              "qa": QA, "quality": QUALITY, "reports": REPORTS, "report": REPORT, "assistant": ASSISTANT,
              "search": SEARCH, "settings": SETTINGS, "error": ERROR})
