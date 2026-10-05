# Setup guide

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
5. On a computer with a browser, run `neuranova auth gmail` and approve. This creates `secrets/gmail_token.json`. Copy that file to the server's `secrets/` folder.

> ⚠️ **Personal Gmail with an "External" app in testing mode:** Google expires the sign-in **every 7 days**, so you'd need to run `neuranova auth gmail` weekly. To avoid this, use a Google Workspace account with an "Internal" app (no expiry), or publish the app. Publishing an app that reads Gmail requires Google's verification.

## 4. Outlook / Microsoft 365

1. Open <https://entra.microsoft.com> → **App registrations → New registration**.
   - Name `neuranova-agent`.
   - Supported accounts: **Accounts in any organizational directory and personal Microsoft accounts**.
   - No redirect URI.
2. In the new app: **Authentication → Advanced settings → Allow public client flows → Yes → Save**.
3. **API permissions → Add → Microsoft Graph → Delegated → `Mail.Read`**.
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

**Why templates?** WhatsApp only allows free-form messages within 24 hours of *you* messaging the bot. The agent messages you first, so it uses the approved template, and Meta charges a small fee per template message. Two-way chat (you text the bot) comes in Phase 3.

## 6. Run it on a server

Any small Linux server works (1 GB RAM is enough).

**Option A: Docker**
```bash
docker build -t neuranova .
docker run -d --name neuranova --restart unless-stopped \
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
