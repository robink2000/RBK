# Setup guide

> **Easiest way:** run `neuranova run` with the dashboard turned on (section 5d), sign in, and open **Integrations**. You enter every key and sign-in on that page, with the steps shown on each card. The sections below explain the same steps in more detail, and the `.env` file still works if you prefer it.

> **Upgrading from Phase 1?** The agent now needs permission to *send* replies you approve. Run `neuranova auth gmail` and `neuranova auth outlook` again (add `Mail.Send` to the Outlook app first), then follow section 5b for the webhook.

Do these once. Each account is optional: if one is left blank in `.env`, that part is simply skipped.

## 1. Claude (required)

1. Go to <https://console.anthropic.com> → **API Keys** → **Create key**.
2. Put it in `.env` as `ANTHROPIC_API_KEY=...`.
3. Add a spending limit under **Billing** so costs can't surprise you.

## 2. Todoist

1. Todoist → **Settings → Integrations → Developer** → copy the **API token**.
2. `.env`: `TODOIST_API_TOKEN=...`
3. Give tasks a **time** ("call investor tomorrow 3pm") to get a WhatsApp reminder 30 minutes before.

## 3. Gmail

1. Open <https://console.cloud.google.com> and create a project called `neuranova-agent`.
2. **APIs & Services → Library → Gmail API → Enable**.
3. **APIs & Services → OAuth consent screen** (Google may call this "Google Auth Platform"):
   - User type **External** for a personal @gmail.com, or **Internal** for Google Workspace.
   - Under **Test users**, add your own Gmail address.
4. **Credentials → Create credentials → OAuth client ID → Desktop app**. Download the JSON and save it as `secrets/gmail_client_secret.json`.
5. On a computer with a browser, run `neuranova auth gmail` and approve. The agent asks to **read** and **send** email (sending is only used for drafts you approve). This creates `secrets/gmail_token.json`. Copy that file to the server's `secrets/` folder.

> ⚠️ **Personal Gmail with an "External" app in testing mode:** Google expires the sign-in **every 7 days**, so you'd need to run `neuranova auth gmail` weekly. To avoid this, use a Google Workspace account with an "Internal" app (no expiry), or publish the app. Publishing an app that reads Gmail requires Google's verification.

## 4. Outlook / Microsoft 365

1. Open <https://entra.microsoft.com> → **App registrations → New registration**.
   - Name `neuranova-agent`.
   - Supported accounts: **Accounts in any organizational directory and personal Microsoft accounts**.
   - No redirect URI.
2. In the new app: **Authentication → Advanced settings → Allow public client flows → Yes → Save**.
3. **API permissions → Add → Microsoft Graph → Delegated → `Mail.Read` and `Mail.Send`**.
4. Copy the **Application (client) ID** into `.env` as `OUTLOOK_CLIENT_ID=...`.
5. Run `neuranova auth outlook`. It prints a code: open the link on your phone, enter the code and approve. This works directly on the server.

## 5. WhatsApp (Meta Cloud API)

Start this early, because approvals can take a few days. Until it's done, keep `NOTIFY_CHANNEL=console`.

1. **New number:** get a phone number that is **not** registered on WhatsApp (a new SIM or a virtual number). This becomes the NeuraNova bot. Your personal WhatsApp receives the messages.
2. Create a **Meta Business** account at <https://business.facebook.com>.
3. At <https://developers.facebook.com> → **My Apps → Create app → Business**, then add the **WhatsApp** product.
4. **WhatsApp → API Setup:** add and verify the new number. Copy the **Phone number ID** into `WHATSAPP_PHONE_NUMBER_ID`.
5. **Permanent token:** Business Settings → **System users** → add an admin system user → **Generate token** for your app with the `whatsapp_business_messaging` and `whatsapp_business_management` permissions. Put it in `WHATSAPP_ACCESS_TOKEN`. (The temporary token on the API Setup page expires in 24 hours.)
6. **Message template:** WhatsApp Manager → **Message templates → Create**:
   - Category: **Utility**
   - Name: `neuranova_update`
   - Language: English (`en`)
   - Body: `NeuraNova update: {{1}}`
   - Sample value: `2 clients waiting for a reply`

   Submit it and wait for approval.
7. `WHATSAPP_RECIPIENT` is **your** personal number in international format without `+`, e.g. `919876543210`.
8. Set `NOTIFY_CHANNEL=whatsapp` and run `neuranova test-notify`.

**Why templates?** WhatsApp only allows free-form messages within 24 hours of *you* messaging the bot. The agent messages you first, so it uses the approved template, and Meta charges a small fee per template message. Once you text the bot, it can reply normally for the next 24 hours.

### 5b. Webhook: so you can reply to the bot (send / edit / skip)

The agent needs a public **HTTPS** address that Meta can call when you message the bot.

1. Point a domain or subdomain at your server, e.g. `agent.yourdomain.com`.
2. Put HTTPS in front of the agent. [Caddy](https://caddyserver.com) is the easiest because it gets the certificate automatically. `/etc/caddy/Caddyfile`:
   ```
   agent.yourdomain.com {
       reverse_proxy localhost:8080
   }
   ```
3. In `.env`:
   - `WHATSAPP_VERIFY_TOKEN`: any long random string you make up
   - `WHATSAPP_APP_SECRET`: Meta app → **App settings → Basic → App secret**
4. Start the agent (`neuranova run`), then go to Meta app → **WhatsApp → Configuration → Webhook → Edit**:
   - Callback URL: `https://agent.yourdomain.com/webhook`
   - Verify token: the same string as `WHATSAPP_VERIFY_TOKEN`
   - Click **Verify and save**, then **subscribe** to the `messages` field.
5. From your phone, send `help` to the bot number. You should get the command list back.

Once you've messaged the bot, WhatsApp lets it send normal messages for 24 hours, so drafts arrive in full with line breaks. Outside that window you get a short template message such as "Draft #12 ready for Asha. Reply 'drafts' to review it". Replying `drafts` opens the window and shows the full text.

### 5c. Your reply style

In `neuranova.toml` under `[replies]`, set your **signature** (replace `[Your name]`) and **tone**. Until you replace `[Your name]`, every draft has a blank and the agent will refuse to send it.

### 5d. Dashboard

1. In `.env`:
   - `OWNER_EMAIL` and `OWNER_NAME`: your sign-in email and the name teammates see
   - `DASHBOARD_PASSWORD`: a long password
   - `DASHBOARD_SECRET`: generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `PUBLIC_URL`: your dashboard address, e.g. `https://agent.yourdomain.com` (used in invite links)
2. The dashboard is served at the same address as the webhook, e.g. `https://agent.yourdomain.com/`. The Caddy setup in 5b already covers it.
3. On your phone, open it and choose **Add to Home screen** to use it like an app.
4. To try it locally without HTTPS, add `DASHBOARD_INSECURE_COOKIE=1` to `.env`, run `neuranova run`, and open `http://localhost:8080`. Never set this on the real server.

Progress for the quality goal and for deals comes from what you log. Either tell the bot on WhatsApp ("delivered the Acme site on time", "won Globex, 80000") or use the **Log progress** form on the dashboard.

### 5e. Add your team

1. Sign in, open **Team → Invite someone**, and enter their name, email, role and (optionally) WhatsApp number.
2. Copy the link that appears and send it to them yourself. It's shown only once, works once, and expires in 7 days.
3. They open it, choose a password, and they're in. They sign in later with their email.
4. If they gave a WhatsApp number, they can text the bot number too (`help` lists their commands).
   - WhatsApp's 24-hour rule applies to each person separately. Until they've texted the bot, their task alerts go out as the `neuranova_update` template, which Meta charges a small fee for.
5. **Forgot password?** Use **Reset link** next to their name. **Someone leaving?** Use **Deactivate**: they're signed out at once, and their tasks stay on the board for you to hand over.

Make someone an **admin** only if they should manage people. Admins still never see your inbox or drafts.

## 6. Run it on a server

Any small Linux server works (1 GB RAM is enough).

**Option A: Docker**
```bash
docker build -t neuranova .
docker run -d --name neuranova --restart unless-stopped -p 127.0.0.1:8080:8080 \
  --env-file .env -v $PWD/data:/app/data -v $PWD/secrets:/app/secrets neuranova
docker logs -f neuranova
```

**Option B: systemd**
```ini
# /etc/systemd/system/neuranova.service
[Service]
WorkingDirectory=/opt/neuranova
ExecStart=/opt/neuranova/.venv/bin/neuranova run
Restart=always
[Install]
WantedBy=multi-user.target
```

Set `timezone` in `neuranova.toml` to your local zone (e.g. `Asia/Kolkata`). Working hours, the reply deadline and the brief time all use it.
